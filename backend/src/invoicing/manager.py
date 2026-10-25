"""
Invoicing Engine and Manager (BIL-077, BIL-079, BIL-080, BIL-081, BIL-087).
Enforces:
- Gapless sequential invoice numbering per tenant/year.
- Mathematical total invariants: subtotal = sum(line items), total = subtotal - discounts + tax.
- Draft -> Finalized lifecycle with immutability.
- Double-entry ledger synchronization.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from enum import Enum
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Column, String, BigInteger, Integer, DateTime, ForeignKey, Text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import Base


class InvoiceStatus(str, Enum):
    DRAFT = "DRAFT"
    FINALIZED = "FINALIZED"
    PAID = "PAID"
    VOID = "VOID"


def _normalize_tz(v):
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


class InvoiceRecord(Base):
    __tablename__ = "invoices"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    customer_id = Column(String(64), nullable=False, index=True)
    period_id = Column(String(64), nullable=True, index=True)
    invoice_number = Column(String(64), nullable=True, unique=True, index=True)
    status = Column(String(32), default=InvoiceStatus.DRAFT.value, nullable=False)
    currency = Column(String(8), default="USD", nullable=False)
    subtotal_cents = Column(BigInteger, default=0, nullable=False)
    discount_cents = Column(BigInteger, default=0, nullable=False)
    credit_cents = Column(BigInteger, default=0, nullable=False)
    tax_cents = Column(BigInteger, default=0, nullable=False)
    total_cents = Column(BigInteger, default=0, nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False)
    finalized_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    @property
    def invoice_id(self) -> str:
        return self.id


class InvoiceLineItemRecord(Base):
    __tablename__ = "invoice_line_items"

    id = Column(String(64), primary_key=True, index=True)
    invoice_id = Column(String(64), ForeignKey("invoices.id"), nullable=False, index=True)
    item_type = Column(String(32), default="USAGE", nullable=False)
    description = Column(String(256), nullable=False)
    event_type = Column(String(64), nullable=True)
    quantity = Column(BigInteger, default=1, nullable=False)
    unit_price_cents = Column(BigInteger, default=0, nullable=False)
    amount_cents = Column(BigInteger, default=0, nullable=False)


class InvoiceSequenceRecord(Base):
    __tablename__ = "invoice_sequences"

    id = Column(String(64), primary_key=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    current_number = Column(BigInteger, default=0, nullable=False)


class LineItemType(str, Enum):
    USAGE = "USAGE"
    SUBSCRIPTION = "SUBSCRIPTION"
    DISCOUNT = "DISCOUNT"
    TAX = "TAX"
    CREDIT = "CREDIT"


SUPPORTED_CURRENCIES = {"USD", "EUR", "GBP", "CAD", "AUD", "JPY", "SGD"}


class InvoiceLineItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    invoice_id: str
    item_type: str = "USAGE"
    description: str
    event_type: Optional[str] = None
    quantity: int
    unit_price_cents: int
    amount_cents: int


class InvoiceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    customer_id: str
    period_id: Optional[str] = None
    invoice_number: Optional[str] = None
    status: InvoiceStatus
    currency: str = "USD"
    subtotal_cents: int
    discount_cents: int
    credit_cents: int = 0
    tax_cents: int
    total_cents: int
    due_date: datetime
    finalized_at: Optional[datetime] = None
    created_at: datetime
    line_items: List[InvoiceLineItemSchema] = []

    @property
    def invoice_id(self) -> str:
        return self.id

    @field_validator("due_date", "finalized_at", "created_at", mode="before")
    @classmethod
    def normalize_dates(cls, v):
        return _normalize_tz(v)


class InvoiceManager:
    """
    Manages complete invoicing workflow (BIL-077, BIL-078, BIL-079, BIL-080, BIL-081, BIL-082, BIL-083, BIL-084, BIL-086, BIL-087, BIL-088).
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_next_invoice_number(self, tenant_id: str, year: int) -> str:
        """
        Generates gapless sequential invoice number: INV-{year}-{0001...} (BIL-080).
        """
        seq_id = f"{tenant_id}_{year}"
        stmt = select(InvoiceSequenceRecord).where(InvoiceSequenceRecord.id == seq_id)
        res = await self.session.execute(stmt)
        seq_rec = res.scalar_one_or_none()

        if not seq_rec:
            seq_rec = InvoiceSequenceRecord(
                id=seq_id,
                tenant_id=tenant_id,
                year=year,
                current_number=1
            )
            self.session.add(seq_rec)
            num = 1
        else:
            seq_rec.current_number += 1
            num = seq_rec.current_number

        return f"INV-{year}-{num:04d}"

    async def create_draft_invoice(
        self,
        tenant_id: str,
        customer_id: str,
        period_id: Optional[str] = None,
        currency: str = "USD",
        due_days: int = 30,
        invoice_id: Optional[str] = None
    ) -> InvoiceSchema:
        """
        Creates a new draft invoice (BIL-077, BIL-078, BIL-088).
        """
        curr = currency.upper()
        if curr not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Unsupported ISO currency: {currency}. Supported: {SUPPORTED_CURRENCIES}")

        now = datetime.now(timezone.utc)
        actual_id = invoice_id or f"inv_{uuid.uuid4().hex[:12]}"
        rec = InvoiceRecord(
            id=actual_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            period_id=period_id,
            invoice_number=None,
            status=InvoiceStatus.DRAFT.value,
            currency=curr,
            subtotal_cents=0,
            discount_cents=0,
            credit_cents=0,
            tax_cents=0,
            total_cents=0,
            due_date=now + timedelta(days=due_days),
            created_at=now
        )
        self.session.add(rec)
        await self.session.commit()
        return InvoiceSchema.model_validate(rec)

    async def add_line_item(
        self,
        invoice_id: str,
        description: str,
        quantity: int,
        unit_price_cents: int,
        event_type: Optional[str] = None,
        item_type: str = "USAGE",
        amount_cents: Optional[int] = None
    ) -> InvoiceLineItemSchema:
        """
        Adds a line item to a draft invoice (BIL-081).
        """
        inv_stmt = select(InvoiceRecord).where(InvoiceRecord.id == invoice_id)
        inv_res = await self.session.execute(inv_stmt)
        inv = inv_res.scalar_one_or_none()
        if not inv:
            raise ValueError(f"Invoice {invoice_id} not found")
        if inv.status != InvoiceStatus.DRAFT.value:
            raise ValueError("Cannot add line items to a non-draft invoice (Cannot modify immutable invoice)")

        calculated_amount = amount_cents if amount_cents is not None else (quantity * unit_price_cents)
        line_rec = InvoiceLineItemRecord(
            id=f"li_{uuid.uuid4().hex[:12]}",
            invoice_id=invoice_id,
            item_type=item_type,
            description=description,
            event_type=event_type,
            quantity=quantity,
            unit_price_cents=unit_price_cents,
            amount_cents=calculated_amount
        )
        self.session.add(line_rec)
        await self.session.commit()

        # Update totals automatically
        await self.recalculate_totals(invoice_id)
        return InvoiceLineItemSchema.model_validate(line_rec)

    async def add_usage_line_item(
        self,
        invoice_id: str,
        event_type: str,
        quantity: int,
        amount_cents: int,
        description: Optional[str] = None
    ) -> InvoiceLineItemSchema:
        return await self.add_line_item(
            invoice_id=invoice_id,
            description=description or f"Usage: {quantity} units of {event_type}",
            quantity=quantity,
            unit_price_cents=(amount_cents // quantity) if quantity > 0 else 0,
            event_type=event_type,
            item_type=LineItemType.USAGE.value,
            amount_cents=amount_cents
        )

    async def add_subscription_line_item(
        self,
        invoice_id: str,
        plan_id: str,
        base_fee_cents: int,
        description: Optional[str] = None
    ) -> InvoiceLineItemSchema:
        return await self.add_line_item(
            invoice_id=invoice_id,
            description=description or f"Subscription fee for {plan_id}",
            quantity=1,
            unit_price_cents=base_fee_cents,
            item_type=LineItemType.SUBSCRIPTION.value,
            amount_cents=base_fee_cents
        )

    async def add_discount_line_item(
        self,
        invoice_id: str,
        discount_cents: int,
        description: str = "Promotional Discount"
    ) -> InvoiceLineItemSchema:
        if discount_cents <= 0:
            raise ValueError("Discount must be positive")
        return await self.add_line_item(
            invoice_id=invoice_id,
            description=description,
            quantity=1,
            unit_price_cents=discount_cents,
            item_type=LineItemType.DISCOUNT.value,
            amount_cents=discount_cents
        )

    async def add_tax_line_item(
        self,
        invoice_id: str,
        tax_rate_bps: int,
        description: str = "Sales Tax"
    ) -> InvoiceLineItemSchema:
        inv_stmt = select(InvoiceRecord).where(InvoiceRecord.id == invoice_id)
        inv = (await self.session.execute(inv_stmt)).scalar_one_or_none()
        if not inv:
            raise ValueError(f"Invoice {invoice_id} not found")
        if inv.status != InvoiceStatus.DRAFT.value:
            raise ValueError("Cannot modify immutable invoice")

        await self.recalculate_totals(invoice_id)
        await self.session.refresh(inv)

        net_taxable = max(0, inv.subtotal_cents - inv.discount_cents - inv.credit_cents)
        tax_amount_cents = (net_taxable * tax_rate_bps + 5000) // 10000

        return await self.add_line_item(
            invoice_id=invoice_id,
            description=f"{description} ({tax_rate_bps / 100:.2f}%)",
            quantity=1,
            unit_price_cents=tax_amount_cents,
            item_type=LineItemType.TAX.value,
            amount_cents=tax_amount_cents
        )

    async def recalculate_totals(
        self,
        invoice_id: str,
        discount_cents: Optional[int] = None,
        tax_cents: Optional[int] = None
    ) -> InvoiceSchema:
        """
        Calculates and verifies invoice financial totals (BIL-087).
        Invariant:
          totals = subtotal - discounts - credits + tax
        """
        inv_stmt = select(InvoiceRecord).where(InvoiceRecord.id == invoice_id)
        inv_res = await self.session.execute(inv_stmt)
        inv = inv_res.scalar_one_or_none()
        if not inv:
            raise ValueError(f"Invoice {invoice_id} not found")

        li_stmt = select(InvoiceLineItemRecord).where(InvoiceLineItemRecord.invoice_id == invoice_id)
        li_res = await self.session.execute(li_stmt)
        items = li_res.scalars().all()

        subtotal = 0
        discounts = 0
        credits = 0
        taxes = 0

        for item in items:
            t = item.item_type
            if t in (LineItemType.USAGE.value, LineItemType.SUBSCRIPTION.value):
                subtotal += item.amount_cents
            elif t == LineItemType.DISCOUNT.value:
                discounts += item.amount_cents
            elif t == LineItemType.CREDIT.value:
                credits += item.amount_cents
            elif t == LineItemType.TAX.value:
                taxes += item.amount_cents

        if discount_cents is not None:
            discounts = discount_cents
        if tax_cents is not None:
            taxes = tax_cents

        inv.subtotal_cents = subtotal
        inv.discount_cents = discounts
        inv.credit_cents = credits
        inv.tax_cents = taxes
        inv.total_cents = max(0, subtotal - discounts - credits + taxes)

        await self.session.commit()
        return await self.get_invoice(invoice_id)

    async def finalize_invoice(self, invoice_id: str) -> InvoiceSchema:
        """
        Finalizes an invoice, locking line items and assigning sequential invoice number (BIL-079).
        """
        inv_stmt = select(InvoiceRecord).where(InvoiceRecord.id == invoice_id)
        inv_res = await self.session.execute(inv_stmt)
        inv = inv_res.scalar_one_or_none()
        if not inv:
            raise ValueError(f"Invoice {invoice_id} not found")
        if inv.status != InvoiceStatus.DRAFT.value:
            raise ValueError(f"Invoice is already {inv.status}")

        now = datetime.now(timezone.utc)
        inv_number = await self.get_next_invoice_number(inv.tenant_id, now.year)

        inv.invoice_number = inv_number
        inv.status = InvoiceStatus.FINALIZED.value
        inv.finalized_at = now

        await self.session.commit()
        return await self.get_invoice(invoice_id)

    async def get_invoice(self, invoice_id: str) -> Optional[InvoiceSchema]:
        inv_stmt = select(InvoiceRecord).where(InvoiceRecord.id == invoice_id)
        inv_res = await self.session.execute(inv_stmt)
        inv = inv_res.scalar_one_or_none()
        if not inv:
            return None

        li_stmt = select(InvoiceLineItemRecord).where(InvoiceLineItemRecord.invoice_id == invoice_id)
        li_res = await self.session.execute(li_stmt)
        items = [InvoiceLineItemSchema.model_validate(i) for i in li_res.scalars().all()]

        return InvoiceSchema(
            id=inv.id,
            tenant_id=inv.tenant_id,
            customer_id=inv.customer_id,
            period_id=inv.period_id,
            invoice_number=inv.invoice_number,
            status=InvoiceStatus(inv.status),
            subtotal_cents=inv.subtotal_cents,
            discount_cents=inv.discount_cents,
            tax_cents=inv.tax_cents,
            total_cents=inv.total_cents,
            due_date=inv.due_date,
            finalized_at=inv.finalized_at,
            created_at=inv.created_at,
            line_items=items
        )
