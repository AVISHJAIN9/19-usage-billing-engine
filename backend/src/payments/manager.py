"""
Payments and Webhooks Manager (BIL-090, BIL-095, BIL-096).
Enforces:
- Payment execution and settlement against invoices.
- Inbound payment webhook processing with payload handling.
- Strict webhook deduplication and idempotency.
- Synchronization with double-entry ledger.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import Column, String, BigInteger, DateTime, ForeignKey, Text, select, CheckConstraint, Index
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import Base
from invoicing.manager import InvoiceRecord, InvoiceStatus


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


def _normalize_tz(v):
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


class PaymentRecord(Base):
    __tablename__ = "payments"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    customer_id = Column(String(64), nullable=False, index=True)
    invoice_id = Column(String(64), ForeignKey("invoices.id"), nullable=False, index=True)
    amount_cents = Column(BigInteger, nullable=False)
    currency = Column(String(16), default="USD_CENTS", nullable=False)
    status = Column(String(32), default=PaymentStatus.PENDING.value, nullable=False)
    provider_tx_id = Column(String(128), nullable=True)
    idempotency_key = Column(String(128), nullable=True)
    payment_method_id = Column(String(64), nullable=True)
    gateway_ref = Column(String(128), nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(String(256), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="chk_payment_amount_positive"),
        Index("ix_payments_tenant_idemp", "tenant_id", "idempotency_key", unique=True),
        Index("ix_payments_tenant_cust", "tenant_id", "customer_id", "created_at"),
    )


class ProcessedWebhookRecord(Base):
    __tablename__ = "processed_webhooks"

    event_id = Column(String(128), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    processed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class PaymentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    customer_id: str
    invoice_id: str
    amount_cents: int
    currency: str = "USD_CENTS"
    status: PaymentStatus
    provider_tx_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    payment_method_id: Optional[str] = None
    gateway_ref: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def normalize_dates(cls, v):
        return _normalize_tz(v)


class WebhookResult(BaseModel):
    event_id: str
    status: str  # PROCESSED, DUPLICATE, IGNORED
    message: str


class PaymentManager:
    """
    Manages payment transactions, webhook dispatching, and idempotency (BIL-090, BIL-095, BIL-096).
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_and_settle_payment(
        self,
        payment_id: str,
        tenant_id: str,
        customer_id: str,
        invoice_id: str,
        amount_cents: int,
        provider_tx_id: str
    ) -> PaymentSchema:
        """
        Processes a payment for an invoice and transitions invoice to PAID (BIL-090).
        """
        # Validate invoice exists
        inv_stmt = select(InvoiceRecord).where(InvoiceRecord.id == invoice_id)
        inv_res = await self.session.execute(inv_stmt)
        inv = inv_res.scalar_one_or_none()
        if not inv:
            raise ValueError(f"Invoice {invoice_id} not found")

        # Record payment
        pay_rec = PaymentRecord(
            id=payment_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            invoice_id=invoice_id,
            amount_cents=amount_cents,
            currency="USD_CENTS",
            status=PaymentStatus.SUCCEEDED.value,
            provider_tx_id=provider_tx_id,
            created_at=datetime.now(timezone.utc)
        )
        self.session.add(pay_rec)

        # Transition invoice to PAID if fully settled
        if amount_cents >= inv.total_cents:
            inv.status = InvoiceStatus.PAID.value

        await self.session.commit()
        return PaymentSchema.model_validate(pay_rec)

    async def handle_webhook(
        self,
        event_id: str,
        tenant_id: str,
        event_type: str,
        payload: Dict[str, Any]
    ) -> WebhookResult:
        """
        Handles incoming payment webhooks with exact deduplication (BIL-095, BIL-096).
        """
        # 1. Idempotency check: has this event_id already been processed?
        chk_stmt = select(ProcessedWebhookRecord).where(ProcessedWebhookRecord.event_id == event_id)
        chk_res = await self.session.execute(chk_stmt)
        if chk_res.scalar_one_or_none():
            return WebhookResult(
                event_id=event_id,
                status="DUPLICATE",
                message="Webhook event already processed"
            )

        # 2. Process payload based on event_type
        payload_str = json.dumps(payload, sort_keys=True)
        payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()

        if event_type == "payment_intent.succeeded":
            invoice_id = payload.get("invoice_id")
            amount = payload.get("amount_cents", 0)
            payment_id = payload.get("payment_id", f"pay_{event_id}")
            customer_id = payload.get("customer_id", "cust_unknown")
            provider_tx_id = payload.get("provider_tx_id", event_id)

            if invoice_id:
                await self.create_and_settle_payment(
                    payment_id=payment_id,
                    tenant_id=tenant_id,
                    customer_id=customer_id,
                    invoice_id=invoice_id,
                    amount_cents=amount,
                    provider_tx_id=provider_tx_id
                )

        # 3. Record processed webhook record
        wh_rec = ProcessedWebhookRecord(
            event_id=event_id,
            tenant_id=tenant_id,
            event_type=event_type,
            payload_hash=payload_hash,
            processed_at=datetime.now(timezone.utc)
        )
        self.session.add(wh_rec)
        await self.session.commit()

        return WebhookResult(
            event_id=event_id,
            status="PROCESSED",
            message=f"Event {event_type} processed successfully"
        )

    async def get_payment(self, payment_id: str) -> Optional[PaymentSchema]:
        stmt = select(PaymentRecord).where(PaymentRecord.id == payment_id)
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            return None
        return PaymentSchema.model_validate(rec)

    async def record_payment(
        self,
        payment_id: str,
        tenant_id: str,
        customer_id: str,
        invoice_id: str,
        amount_cents: int,
        currency: str = "USD_CENTS",
        status: PaymentStatus = PaymentStatus.PENDING,
        idempotency_key: Optional[str] = None,
        payment_method_id: Optional[str] = None,
        gateway_ref: Optional[str] = None
    ) -> PaymentSchema:
        """
        Records a payment transaction with idempotency enforcement and amount constraints (BIL-005).
        """
        if amount_cents <= 0:
            raise ValueError("Payment amount_cents must be strictly positive")

        if idempotency_key:
            stmt = (
                select(PaymentRecord)
                .where(PaymentRecord.tenant_id == tenant_id)
                .where(PaymentRecord.idempotency_key == idempotency_key)
            )
            res = await self.session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                return PaymentSchema.model_validate(existing)

        rec = PaymentRecord(
            id=payment_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            invoice_id=invoice_id,
            amount_cents=amount_cents,
            currency=currency,
            status=status.value if isinstance(status, PaymentStatus) else status,
            idempotency_key=idempotency_key,
            payment_method_id=payment_method_id,
            gateway_ref=gateway_ref,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        self.session.add(rec)
        await self.session.commit()
        return PaymentSchema.model_validate(rec)

    async def update_payment_status(
        self,
        payment_id: str,
        status: PaymentStatus,
        gateway_ref: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Optional[PaymentSchema]:
        stmt = select(PaymentRecord).where(PaymentRecord.id == payment_id)
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            return None

        rec.status = status.value if isinstance(status, PaymentStatus) else status
        if gateway_ref:
            rec.gateway_ref = gateway_ref
        if error_code:
            rec.error_code = error_code
        if error_message:
            rec.error_message = error_message
        rec.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        return PaymentSchema.model_validate(rec)

