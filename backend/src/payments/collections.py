"""
Payments & Collections Engine (BIL-092, BIL-093, BIL-097, BIL-098, BIL-099, BIL-100, BIL-101).
Enforces:
- Payment authorization and two-step capture.
- Idempotent payment retries with attempt logs.
- Failed payment handling and reason recording.
- Dunning schedule driven by manual clock.
- Grace period lifecycle (PAST_DUE -> SUSPENDED).
- Automatic collection of due invoices.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from enum import Enum
import uuid
from sqlalchemy import Column, String, BigInteger, DateTime, ForeignKey, Index, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict
from db.database import Base
from payments.manager import PaymentRecord, PaymentStatus
from invoicing.manager import InvoiceRecord, InvoiceStatus


class DunningStage(str, Enum):
    ATTEMPT_1 = "ATTEMPT_1"  # Day 0
    ATTEMPT_2 = "ATTEMPT_2"  # Day 3
    ATTEMPT_3 = "ATTEMPT_3"  # Day 7
    FINAL_ESCALATION = "FINAL_ESCALATION"  # Day 14
    COMPLETED = "COMPLETED"


class AccountStanding(str, Enum):
    GOOD = "GOOD"
    PAST_DUE = "PAST_DUE"      # Within grace period
    SUSPENDED = "SUSPENDED"    # Grace period breached


class PaymentAttemptRecord(Base):
    __tablename__ = "payment_attempts"

    attempt_id = Column(String(64), primary_key=True, index=True)
    payment_id = Column(String(64), ForeignKey("payments.id"), nullable=False, index=True)
    attempt_number = Column(BigInteger, nullable=False)
    idempotency_key = Column(String(128), nullable=True, unique=True, index=True)
    status = Column(String(32), nullable=False)
    error_code = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class DunningRecord(Base):
    __tablename__ = "dunning_workflows"

    dunning_id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    customer_id = Column(String(64), nullable=False, index=True)
    invoice_id = Column(String(64), nullable=False, index=True)
    stage = Column(String(32), default=DunningStage.ATTEMPT_1.value, nullable=False)
    standing = Column(String(32), default=AccountStanding.PAST_DUE.value, nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=False)
    grace_period_until = Column(DateTime(timezone=True), nullable=False)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class PaymentCollectionsManager:
    """
    Manages payment authorization, captures, retries, dunning, and automatic collections.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def authorize_payment(
        self,
        payment_id: str,
        tenant_id: str,
        customer_id: str,
        invoice_id: str,
        amount_cents: int,
        idempotency_key: Optional[str] = None
    ) -> PaymentRecord:
        """
        BIL-092: Authorizes a payment (places funds hold).
        """
        if amount_cents <= 0:
            raise ValueError("Payment amount must be positive")

        if idempotency_key:
            stmt = select(PaymentRecord).where(
                PaymentRecord.tenant_id == tenant_id,
                PaymentRecord.idempotency_key == idempotency_key
            )
            existing = (await self.session.execute(stmt)).scalar_one_or_none()
            if existing:
                return existing

        now = datetime.now(timezone.utc)
        rec = PaymentRecord(
            id=payment_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            invoice_id=invoice_id,
            amount_cents=amount_cents,
            currency="USD_CENTS",
            status=PaymentStatus.AUTHORIZED.value,
            idempotency_key=idempotency_key,
            gateway_ref=f"auth_{uuid.uuid4().hex[:10]}",
            created_at=now,
            updated_at=now
        )
        self.session.add(rec)
        await self.session.commit()
        return rec

    async def capture_payment(
        self,
        payment_id: str,
        capture_amount_cents: Optional[int] = None
    ) -> PaymentRecord:
        """
        BIL-093: Captures an authorized payment.
        """
        stmt = select(PaymentRecord).where(PaymentRecord.id == payment_id)
        rec = (await self.session.execute(stmt)).scalar_one_or_none()
        if not rec:
            raise ValueError(f"Payment {payment_id} not found")

        if rec.status != PaymentStatus.AUTHORIZED.value:
            raise ValueError(f"Cannot capture payment in status '{rec.status}' (expected AUTHORIZED)")

        amount_to_capture = capture_amount_cents if capture_amount_cents is not None else rec.amount_cents
        if amount_to_capture > rec.amount_cents:
            raise ValueError(
                f"Capture amount ({amount_to_capture}c) exceeds authorized amount ({rec.amount_cents}c)"
            )

        rec.amount_cents = amount_to_capture
        rec.status = PaymentStatus.CAPTURED.value
        rec.updated_at = datetime.now(timezone.utc)

        # Transition invoice to PAID if invoice exists
        inv_stmt = select(InvoiceRecord).where(InvoiceRecord.id == rec.invoice_id)
        inv = (await self.session.execute(inv_stmt)).scalar_one_or_none()
        if inv and rec.amount_cents >= inv.total_cents:
            inv.status = InvoiceStatus.PAID.value

        await self.session.commit()
        return rec

    async def retry_payment(
        self,
        payment_id: str,
        attempt_number: int,
        idempotency_key: Optional[str] = None
    ) -> PaymentAttemptRecord:
        """
        BIL-097: Idempotent payment retries with attempt logs.
        """
        if idempotency_key:
            stmt = select(PaymentAttemptRecord).where(PaymentAttemptRecord.idempotency_key == idempotency_key)
            existing = (await self.session.execute(stmt)).scalar_one_or_none()
            if existing:
                return existing

        stmt_p = select(PaymentRecord).where(PaymentRecord.id == payment_id)
        p = (await self.session.execute(stmt_p)).scalar_one_or_none()
        if not p:
            raise ValueError(f"Payment {payment_id} not found")

        attempt_id = f"att_{payment_id}_{attempt_number}"
        attempt = PaymentAttemptRecord(
            attempt_id=attempt_id,
            payment_id=payment_id,
            attempt_number=attempt_number,
            idempotency_key=idempotency_key,
            status="SUCCESS",
            created_at=datetime.now(timezone.utc)
        )
        self.session.add(attempt)
        await self.session.commit()
        return attempt

    async def handle_payment_failure(
        self,
        payment_id: str,
        error_code: str,
        error_message: str
    ) -> PaymentRecord:
        """
        BIL-098: Records failed payment and error classification.
        """
        stmt = select(PaymentRecord).where(PaymentRecord.id == payment_id)
        rec = (await self.session.execute(stmt)).scalar_one_or_none()
        if not rec:
            raise ValueError(f"Payment {payment_id} not found")

        rec.status = PaymentStatus.FAILED.value
        rec.error_code = error_code
        rec.error_message = error_message
        rec.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        return rec

    async def initiate_dunning(
        self,
        tenant_id: str,
        customer_id: str,
        invoice_id: str,
        due_date: datetime,
        grace_days: int = 7
    ) -> DunningRecord:
        """
        BIL-099 & BIL-100: Initializes dunning schedule and grace period.
        """
        d_id = f"dun_{invoice_id}"
        grace_until = due_date + timedelta(days=grace_days)
        rec = DunningRecord(
            dunning_id=d_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            invoice_id=invoice_id,
            stage=DunningStage.ATTEMPT_1.value,
            standing=AccountStanding.PAST_DUE.value,
            due_date=due_date,
            grace_period_until=grace_until,
            last_attempt_at=due_date,
            created_at=datetime.now(timezone.utc)
        )
        self.session.add(rec)
        await self.session.commit()
        return rec

    async def evaluate_dunning(
        self,
        dunning_id: str,
        current_time: datetime
    ) -> DunningRecord:
        """
        BIL-099: Progresses dunning schedule based on manual clock:
        - Day 0 to 3: ATTEMPT_1
        - Day 3 to 7: ATTEMPT_2
        - Day 7 to 14: ATTEMPT_3
        - Day 14+: FINAL_ESCALATION

        BIL-100: Enforces grace period expiration:
        - If current_time > grace_period_until, standing transitions from PAST_DUE -> SUSPENDED.
        """
        stmt = select(DunningRecord).where(DunningRecord.dunning_id == dunning_id)
        rec = (await self.session.execute(stmt)).scalar_one_or_none()
        if not rec:
            raise ValueError(f"Dunning workflow {dunning_id} not found")

        days_past_due = (current_time - rec.due_date).total_seconds() / 86400.0

        if days_past_due >= 14:
            rec.stage = DunningStage.FINAL_ESCALATION.value
        elif days_past_due >= 7:
            rec.stage = DunningStage.ATTEMPT_3.value
        elif days_past_due >= 3:
            rec.stage = DunningStage.ATTEMPT_2.value
        else:
            rec.stage = DunningStage.ATTEMPT_1.value

        # Grace period check (BIL-100)
        if current_time > rec.grace_period_until:
            rec.standing = AccountStanding.SUSPENDED.value
        else:
            rec.standing = AccountStanding.PAST_DUE.value

        await self.session.commit()
        return rec

    async def execute_automatic_collection(
        self,
        tenant_id: str,
        as_of: datetime
    ) -> List[Dict[str, Any]]:
        """
        BIL-101: Automatically charges finalized invoices that are due.
        Idempotent: skips already paid invoices.
        """
        stmt = (
            select(InvoiceRecord)
            .where(
                InvoiceRecord.tenant_id == tenant_id,
                InvoiceRecord.status == InvoiceStatus.FINALIZED.value,
                InvoiceRecord.due_date <= as_of
            )
        )
        res = await self.session.execute(stmt)
        invoices = res.scalars().all()

        results = []
        for inv in invoices:
            pay_id = f"auto_pay_{inv.invoice_id}"
            idemp_key = f"idemp_{pay_id}"

            # Idempotent collection check
            q_chk = select(PaymentRecord).where(PaymentRecord.idempotency_key == idemp_key)
            existing = (await self.session.execute(q_chk)).scalar_one_or_none()
            if existing:
                results.append({
                    "invoice_id": inv.invoice_id,
                    "payment_id": existing.id,
                    "status": "ALREADY_COLLECTED",
                    "amount_cents": existing.amount_cents
                })
                continue

            pay = PaymentRecord(
                id=pay_id,
                tenant_id=tenant_id,
                customer_id=inv.customer_id,
                invoice_id=inv.invoice_id,
                amount_cents=inv.total_cents,
                currency="USD_CENTS",
                status=PaymentStatus.CAPTURED.value,
                idempotency_key=idemp_key,
                gateway_ref=f"gw_{uuid.uuid4().hex[:10]}",
                created_at=as_of,
                updated_at=as_of
            )
            self.session.add(pay)
            inv.status = InvoiceStatus.PAID.value

            results.append({
                "invoice_id": inv.invoice_id,
                "payment_id": pay_id,
                "status": "COLLECTED",
                "amount_cents": inv.total_cents
            })

        await self.session.commit()
        return results
