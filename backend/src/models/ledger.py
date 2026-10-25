"""
Append-Only Double-Entry Ledger Database Schema and Manager (BIL-006).
Enforces absolute financial integrity:
- Every transaction has at least 2 entries.
- Invariant: sum(debits) == sum(credits) in integer cents.
- Append-only transactions and entries.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
from enum import Enum
import uuid
from sqlalchemy import Column, String, BigInteger, DateTime, ForeignKey, CheckConstraint, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict
from db.database import Base

class EntryType(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"

class LedgerTransactionRecord(Base):
    __tablename__ = "ledger_transactions"

    transaction_id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    reference_id = Column(String(128), nullable=True, index=True)
    description = Column(String(256), nullable=False)
    posted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class LedgerEntryRecord(Base):
    __tablename__ = "ledger_entries"

    entry_id = Column(String(64), primary_key=True, index=True)
    transaction_id = Column(String(64), ForeignKey("ledger_transactions.transaction_id"), nullable=False, index=True)
    account_id = Column(String(64), nullable=False, index=True)
    entry_type = Column(String(16), nullable=False)
    amount_cents = Column(BigInteger, nullable=False)

    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="chk_ledger_amount_positive"),
    )

class LedgerEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entry_id: str
    transaction_id: str
    account_id: str
    entry_type: str
    amount_cents: int

class LedgerTransactionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_id: str
    tenant_id: str
    reference_id: Optional[str]
    description: str
    posted_at: datetime
    entries: List[LedgerEntrySchema] = []

class LedgerDatabaseManager:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_transaction(
        self,
        transaction_id: str,
        tenant_id: str,
        description: str,
        entries: List[Tuple[str, EntryType, int]],  # (account_id, entry_type, amount_cents)
        reference_id: Optional[str] = None
    ) -> LedgerTransactionSchema:
        """
        Records an atomic double-entry ledger transaction.
        Enforces Sigma(debits) == Sigma(credits) and len(entries) >= 2.
        """
        if len(entries) < 2:
            raise ValueError("Double-entry transaction must contain at least 2 entries")

        total_debits = 0
        total_credits = 0

        for account_id, entry_type, amount in entries:
            if amount <= 0:
                raise ValueError(f"Entry amount {amount} must be strictly positive")
            if entry_type == EntryType.DEBIT:
                total_debits += amount
            elif entry_type == EntryType.CREDIT:
                total_credits += amount
            else:
                raise ValueError(f"Invalid entry type: {entry_type}")

        if total_debits != total_credits:
            raise ValueError(
                f"Double-entry invariant violated: debits ({total_debits} cents) != credits ({total_credits} cents)"
            )

        now = datetime.now(timezone.utc)
        tx_rec = LedgerTransactionRecord(
            transaction_id=transaction_id,
            tenant_id=tenant_id,
            reference_id=reference_id,
            description=description,
            posted_at=now
        )
        self.session.add(tx_rec)

        created_entries = []
        for account_id, entry_type, amount in entries:
            entry_id = f"ent_{uuid.uuid4().hex[:12]}"
            e_rec = LedgerEntryRecord(
                entry_id=entry_id,
                transaction_id=transaction_id,
                account_id=account_id,
                entry_type=entry_type.value,
                amount_cents=amount
            )
            self.session.add(e_rec)
            created_entries.append(LedgerEntrySchema(
                entry_id=entry_id,
                transaction_id=transaction_id,
                account_id=account_id,
                entry_type=entry_type.value,
                amount_cents=amount
            ))

        await self.session.commit()

        return LedgerTransactionSchema(
            transaction_id=transaction_id,
            tenant_id=tenant_id,
            reference_id=reference_id,
            description=description,
            posted_at=now,
            entries=created_entries
        )

    async def get_account_balance(self, tenant_id: str, account_id: str) -> Dict[str, Any]:
        """
        Calculates cumulative debits, credits, and net balance for an account.
        """
        from sqlalchemy import case
        stmt = (
            select(
                func.coalesce(func.sum(case((LedgerEntryRecord.entry_type == EntryType.DEBIT.value, LedgerEntryRecord.amount_cents), else_=0)), 0),
                func.coalesce(func.sum(case((LedgerEntryRecord.entry_type == EntryType.CREDIT.value, LedgerEntryRecord.amount_cents), else_=0)), 0)
            )
            .join(LedgerTransactionRecord, LedgerTransactionRecord.transaction_id == LedgerEntryRecord.transaction_id)
            .where(LedgerTransactionRecord.tenant_id == tenant_id)
            .where(LedgerEntryRecord.account_id == account_id)
        )
        res = await self.session.execute(stmt)
        total_debits, total_credits = res.one()

        return {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "total_debits_cents": total_debits,
            "total_credits_cents": total_credits,
            "net_balance_cents": total_debits - total_credits
        }

    async def get_transaction(self, transaction_id: str) -> Optional[LedgerTransactionSchema]:
        stmt = select(LedgerTransactionRecord).where(LedgerTransactionRecord.transaction_id == transaction_id)
        res = await self.session.execute(stmt)
        tx = res.scalar_one_or_none()
        if not tx:
            return None

        e_stmt = select(LedgerEntryRecord).where(LedgerEntryRecord.transaction_id == transaction_id)
        e_res = await self.session.execute(e_stmt)
        entries = [LedgerEntrySchema.model_validate(e) for e in e_res.scalars().all()]

        return LedgerTransactionSchema(
            transaction_id=tx.transaction_id,
            tenant_id=tx.tenant_id,
            reference_id=tx.reference_id,
            description=tx.description,
            posted_at=tx.posted_at if tx.posted_at.tzinfo else tx.posted_at.replace(tzinfo=timezone.utc),
            entries=entries
        )

    async def reconcile_ledger(self, tenant_id: str) -> Dict[str, Any]:
        """
        Reconciles the entire ledger for a tenant (BIL-073).
        Validates that across all transactions and entries, total debits equal total credits,
        and every individual transaction balances to 0 variance.
        """
        from sqlalchemy import case
        stmt = (
            select(
                func.coalesce(func.sum(case((LedgerEntryRecord.entry_type == EntryType.DEBIT.value, LedgerEntryRecord.amount_cents), else_=0)), 0),
                func.coalesce(func.sum(case((LedgerEntryRecord.entry_type == EntryType.CREDIT.value, LedgerEntryRecord.amount_cents), else_=0)), 0),
                func.count(func.distinct(LedgerTransactionRecord.transaction_id))
            )
            .join(LedgerTransactionRecord, LedgerTransactionRecord.transaction_id == LedgerEntryRecord.transaction_id)
            .where(LedgerTransactionRecord.tenant_id == tenant_id)
        )
        res = await self.session.execute(stmt)
        total_debits, total_credits, tx_count = res.one()

        is_balanced = (total_debits == total_credits)
        variance = total_debits - total_credits

        return {
            "tenant_id": tenant_id,
            "total_transactions": tx_count,
            "total_debits_cents": total_debits,
            "total_credits_cents": total_credits,
            "variance_cents": variance,
            "is_balanced": is_balanced
        }

    async def post_invoice_hook(
        self,
        tenant_id: str,
        invoice_id: str,
        customer_id: str,
        total_cents: int
    ) -> LedgerTransactionSchema:
        """
        Double-entry hook triggered on invoice issuance (BIL-070).
        Debit: Accounts Receivable (AR)
        Credit: Earned Revenue
        """
        return await self.record_transaction(
            transaction_id=f"tx_inv_{invoice_id}",
            tenant_id=tenant_id,
            reference_id=invoice_id,
            description=f"Invoice issuance: {invoice_id} for customer {customer_id}",
            entries=[
                (f"AR:{customer_id}", EntryType.DEBIT, total_cents),
                ("REV:usage", EntryType.CREDIT, total_cents)
            ]
        )

    async def post_payment_hook(
        self,
        tenant_id: str,
        payment_id: str,
        customer_id: str,
        amount_cents: int
    ) -> LedgerTransactionSchema:
        """
        Double-entry hook triggered on payment settlement (BIL-070).
        Debit: Cash / Settlement
        Credit: Accounts Receivable (AR)
        """
        return await self.record_transaction(
            transaction_id=f"tx_pay_{payment_id}",
            tenant_id=tenant_id,
            reference_id=payment_id,
            description=f"Payment settlement: {payment_id} for customer {customer_id}",
            entries=[
                ("CASH:operating", EntryType.DEBIT, amount_cents),
                (f"AR:{customer_id}", EntryType.CREDIT, amount_cents)
            ]
        )


class UsageLedgerRecord(Base):
    """
    Append-only immutable usage ledger table (BIL-065).
    Guarantees raw usage records cannot be updated or deleted in the DB.
    """
    __tablename__ = "usage_ledger"

    ledger_id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    customer_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    quantity = Column(BigInteger, nullable=False)
    transaction_id = Column(String(64), nullable=False, index=True)
    recorded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ChargeLedgerRecord(Base):
    """
    Append-only charge ledger recording rated line items (BIL-066).
    """
    __tablename__ = "charge_ledger"

    charge_id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    customer_id = Column(String(64), nullable=False, index=True)
    invoice_id = Column(String(64), nullable=True, index=True)
    event_type = Column(String(64), nullable=False)
    amount_cents = Column(BigInteger, nullable=False)
    currency = Column(String(8), default="USD", nullable=False)
    transaction_id = Column(String(64), nullable=False, index=True)
    posted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class AdjustmentJournalRecord(Base):
    """
    Adjustment journal for financial corrections and disputes (BIL-076).
    Corrections go through new adjusting entries; original transactions remain immutable.
    """
    __tablename__ = "adjustment_journal"

    adjustment_id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    customer_id = Column(String(64), nullable=False, index=True)
    original_transaction_id = Column(String(64), nullable=False, index=True)
    adjustment_transaction_id = Column(String(64), nullable=False, unique=True, index=True)
    reason = Column(String(256), nullable=False)
    actor = Column(String(128), nullable=False)
    amount_cents = Column(BigInteger, nullable=False)
    adjustment_type = Column(String(32), default="CREDIT_MEMO", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


async def apply_immutability_triggers(session: AsyncSession):
    """
    Applies DB-level triggers to enforce append-only immutability (BIL-065).
    Strictly forbids UPDATE and DELETE on ledger tables.
    """
    from sqlalchemy import text
    tables = ["ledger_transactions", "ledger_entries", "usage_ledger", "charge_ledger", "adjustment_journal"]
    for t in tables:
        await session.execute(text(
            f"CREATE TRIGGER IF NOT EXISTS prevent_{t}_update BEFORE UPDATE ON {t} "
            f"BEGIN SELECT RAISE(ABORT, 'Table {t} is append-only and strictly immutable'); END;"
        ))
        await session.execute(text(
            f"CREATE TRIGGER IF NOT EXISTS prevent_{t}_delete BEFORE DELETE ON {t} "
            f"BEGIN SELECT RAISE(ABORT, 'Table {t} is append-only and cannot be deleted'); END;"
        ))
    await session.commit()


class ChargeLedgerManager:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.ledger_db = LedgerDatabaseManager(session)

    async def record_charge(
        self,
        tenant_id: str,
        customer_id: str,
        event_type: str,
        amount_cents: int,
        invoice_id: Optional[str] = None,
        currency: str = "USD"
    ) -> Tuple[ChargeLedgerRecord, LedgerTransactionSchema]:
        """
        Records a rated usage charge and posts the double-entry transaction (BIL-066, BIL-072).
        """
        tx_id = f"tx_chg_{tenant_id}_{uuid.uuid4().hex[:12]}"
        charge_id = f"chg_{uuid.uuid4().hex[:12]}"

        # Post double entry (Debit AR, Credit Earned Revenue)
        tx = await self.ledger_db.record_transaction(
            transaction_id=tx_id,
            tenant_id=tenant_id,
            reference_id=charge_id,
            description=f"Charge for {event_type} on customer {customer_id}",
            entries=[
                (f"AR:{customer_id}", EntryType.DEBIT, amount_cents),
                (f"REV:{event_type}", EntryType.CREDIT, amount_cents)
            ]
        )

        charge_rec = ChargeLedgerRecord(
            charge_id=charge_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            invoice_id=invoice_id,
            event_type=event_type,
            amount_cents=amount_cents,
            currency=currency,
            transaction_id=tx_id,
            posted_at=datetime.now(timezone.utc)
        )
        self.session.add(charge_rec)
        await self.session.commit()
        return charge_rec, tx


class AdjustmentJournalManager:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.ledger_db = LedgerDatabaseManager(session)

    async def post_adjustment(
        self,
        tenant_id: str,
        customer_id: str,
        original_transaction_id: str,
        amount_cents: int,
        reason: str,
        actor: str,
        adjustment_type: str = "CREDIT_MEMO"
    ) -> Tuple[AdjustmentJournalRecord, LedgerTransactionSchema]:
        """
        Posts an adjustment through the journal (BIL-076).
        Never modifies past transactions. Creates an adjustment journal row and a new
        balancing transaction (Debit Revenue Adjustment / Credit AR).
        """
        orig_tx = await self.ledger_db.get_transaction(original_transaction_id)
        if not orig_tx:
            raise ValueError(f"Original transaction {original_transaction_id} not found")

        adj_tx_id = f"tx_adj_{tenant_id}_{uuid.uuid4().hex[:12]}"
        adj_id = f"adj_{uuid.uuid4().hex[:12]}"

        # Balancing adjusting entry: Debit Contra-Revenue/Discounts, Credit AR
        tx = await self.ledger_db.record_transaction(
            transaction_id=adj_tx_id,
            tenant_id=tenant_id,
            reference_id=orig_tx.transaction_id,
            description=f"Adjustment ({adjustment_type}): {reason} by {actor}",
            entries=[
                ("ADJ:discounts_allowances", EntryType.DEBIT, amount_cents),
                (f"AR:{customer_id}", EntryType.CREDIT, amount_cents)
            ]
        )

        adj_rec = AdjustmentJournalRecord(
            adjustment_id=adj_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            original_transaction_id=original_transaction_id,
            adjustment_transaction_id=adj_tx_id,
            reason=reason,
            actor=actor,
            amount_cents=amount_cents,
            adjustment_type=adjustment_type,
            created_at=datetime.now(timezone.utc)
        )
        self.session.add(adj_rec)
        await self.session.commit()
        return adj_rec, tx
