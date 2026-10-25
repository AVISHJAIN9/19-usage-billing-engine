"""
Accounts, Subscriptions, and Plan Assignment (BIL-013, BIL-017, BIL-019).
Provides management of customer accounts, subscription lifecycles, and plan assignments.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
import json
from enum import Enum
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict, Field, field_validator

from db.database import Base


class CustomerStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class SubscriptionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    TRIALING = "TRIALING"
    PAST_DUE = "PAST_DUE"
    CANCELED = "CANCELED"
    PAUSED = "PAUSED"


class PlanRecord(Base):
    __tablename__ = "plans"

    plan_id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(String(256), default="")
    currency = Column(String(16), default="USD_CENTS", nullable=False)
    interval = Column(String(32), default="MONTHLY", nullable=False)  # MONTHLY, ANNUAL
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class PlanAssignmentRecord(Base):
    __tablename__ = "plan_assignments"

    id = Column(String(64), primary_key=True, index=True)
    subscription_id = Column(String(64), ForeignKey("subscriptions_v2.subscription_id"), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    plan_id = Column(String(64), ForeignKey("plans.plan_id"), nullable=False, index=True)
    effective_from = Column(DateTime(timezone=True), nullable=False)
    effective_to = Column(DateTime(timezone=True), nullable=True)  # Null if currently active
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class CustomerAccountRecordV2(Base):
    __tablename__ = "customer_accounts_v2"

    customer_id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    email = Column(String(128), nullable=False)
    currency = Column(String(16), default="USD_CENTS", nullable=False)
    status = Column(String(32), default=CustomerStatus.ACTIVE.value, nullable=False)
    metadata_json = Column(Text, default="{}", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class SubscriptionRecordV2(Base):
    __tablename__ = "subscriptions_v2"

    subscription_id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    customer_id = Column(String(64), ForeignKey("customer_accounts_v2.customer_id"), nullable=False, index=True)
    plan_id = Column(String(64), nullable=False, index=True)
    status = Column(String(32), default=SubscriptionStatus.ACTIVE.value, nullable=False)
    current_period_start = Column(DateTime(timezone=True), nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    paused_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


# Pydantic Schemas

def _normalize_tz(v):
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v

class CustomerAccount(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    customer_id: str
    tenant_id: str
    name: str
    email: str
    currency: str = "USD_CENTS"
    status: str = CustomerStatus.ACTIVE.value
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def normalize_dates(cls, v):
        return _normalize_tz(v)


class Subscription(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subscription_id: str
    tenant_id: str
    customer_id: str
    plan_id: str
    status: str = SubscriptionStatus.ACTIVE.value
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    canceled_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("current_period_start", "current_period_end", "canceled_at", "paused_at", "created_at", "updated_at", mode="before")
    @classmethod
    def normalize_dates(cls, v):
        return _normalize_tz(v)


class Plan(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan_id: str
    tenant_id: str
    name: str
    description: str = ""
    currency: str = "USD_CENTS"
    interval: str = "MONTHLY"
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def normalize_dates(cls, v):
        return _normalize_tz(v)


class PlanAssignment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    subscription_id: str
    tenant_id: str
    plan_id: str
    effective_from: datetime
    effective_to: Optional[datetime] = None
    created_at: datetime

    @field_validator("effective_from", "effective_to", "created_at", mode="before")
    @classmethod
    def normalize_dates(cls, v):
        return _normalize_tz(v)


class AccountManager:
    """
    Manages Customer Accounts (BIL-013).
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_customer(
        self,
        customer_id: str,
        tenant_id: str,
        name: str,
        email: str,
        currency: str = "USD_CENTS",
        metadata: Optional[Dict[str, Any]] = None
    ) -> CustomerAccount:
        now = datetime.now(timezone.utc)
        rec = CustomerAccountRecordV2(
            customer_id=customer_id,
            tenant_id=tenant_id,
            name=name,
            email=email,
            currency=currency,
            status=CustomerStatus.ACTIVE.value,
            metadata_json=json.dumps(metadata or {}),
            created_at=now,
            updated_at=now
        )
        self.session.add(rec)
        await self.session.commit()
        return CustomerAccount(
            customer_id=rec.customer_id,
            tenant_id=rec.tenant_id,
            name=rec.name,
            email=rec.email,
            currency=rec.currency,
            status=rec.status,
            metadata=json.loads(rec.metadata_json),
            created_at=rec.created_at,
            updated_at=rec.updated_at
        )

    async def get_customer(self, customer_id: str) -> Optional[CustomerAccount]:
        stmt = select(CustomerAccountRecordV2).where(CustomerAccountRecordV2.customer_id == customer_id)
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            return None
        return CustomerAccount(
            customer_id=rec.customer_id,
            tenant_id=rec.tenant_id,
            name=rec.name,
            email=rec.email,
            currency=rec.currency,
            status=rec.status,
            metadata=json.loads(rec.metadata_json or "{}"),
            created_at=rec.created_at,
            updated_at=rec.updated_at
        )

    async def update_customer(
        self,
        customer_id: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[CustomerAccount]:
        stmt = select(CustomerAccountRecordV2).where(CustomerAccountRecordV2.customer_id == customer_id)
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            return None

        if name is not None:
            rec.name = name
        if email is not None:
            rec.email = email
        if status is not None:
            rec.status = status
        if metadata is not None:
            rec.metadata_json = json.dumps(metadata)
        rec.updated_at = datetime.now(timezone.utc)

        await self.session.commit()
        return CustomerAccount(
            customer_id=rec.customer_id,
            tenant_id=rec.tenant_id,
            name=rec.name,
            email=rec.email,
            currency=rec.currency,
            status=rec.status,
            metadata=json.loads(rec.metadata_json or "{}"),
            created_at=rec.created_at,
            updated_at=rec.updated_at
        )

    async def suspend_customer(self, customer_id: str) -> Optional[CustomerAccount]:
        return await self.update_customer(customer_id, status=CustomerStatus.SUSPENDED.value)

    async def close_customer(self, customer_id: str) -> Optional[CustomerAccount]:
        return await self.update_customer(customer_id, status=CustomerStatus.CLOSED.value)


class SubscriptionLifecycleManager:
    """
    Manages Subscriptions and State Transitions (BIL-017).
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_subscription(
        self,
        subscription_id: str,
        tenant_id: str,
        customer_id: str,
        plan_id: str,
        current_period_start: datetime,
        current_period_end: datetime,
        status: str = SubscriptionStatus.ACTIVE.value
    ) -> Subscription:
        now = datetime.now(timezone.utc)
        rec = SubscriptionRecordV2(
            subscription_id=subscription_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            plan_id=plan_id,
            status=status,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            cancel_at_period_end=False,
            canceled_at=None,
            created_at=now,
            updated_at=now
        )
        self.session.add(rec)
        await self.session.commit()
        return Subscription.model_validate(rec)

    async def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        stmt = select(SubscriptionRecordV2).where(SubscriptionRecordV2.subscription_id == subscription_id)
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            return None
        return Subscription.model_validate(rec)

    async def transition_status(self, subscription_id: str, new_status: str) -> Optional[Subscription]:
        stmt = select(SubscriptionRecordV2).where(SubscriptionRecordV2.subscription_id == subscription_id)
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            return None
        
        rec.status = new_status
        rec.updated_at = datetime.now(timezone.utc)
        if new_status == SubscriptionStatus.CANCELED.value and not rec.canceled_at:
            rec.canceled_at = datetime.now(timezone.utc)

        await self.session.commit()
        return Subscription.model_validate(rec)

    async def cancel_subscription(self, subscription_id: str, immediate: bool = False) -> Optional[Subscription]:
        stmt = select(SubscriptionRecordV2).where(SubscriptionRecordV2.subscription_id == subscription_id)
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            return None
        
        now = datetime.now(timezone.utc)
        rec.updated_at = now
        if immediate:
            rec.status = SubscriptionStatus.CANCELED.value
            rec.canceled_at = now
            rec.cancel_at_period_end = False
        else:
            rec.cancel_at_period_end = True

        await self.session.commit()
        return Subscription.model_validate(rec)

    async def pause_subscription(self, subscription_id: str, effective_time: Optional[datetime] = None) -> Optional[Subscription]:
        stmt = select(SubscriptionRecordV2).where(SubscriptionRecordV2.subscription_id == subscription_id)
        res = await self.session.execute(stmt)
        sub = res.scalar_one_or_none()
        if not sub:
            return None
        now = effective_time or datetime.now(timezone.utc)
        sub.status = SubscriptionStatus.PAUSED.value
        sub.paused_at = now
        sub.updated_at = now
        await self.session.commit()
        return Subscription.model_validate(sub)

    async def resume_subscription(self, subscription_id: str, effective_time: Optional[datetime] = None) -> Optional[Subscription]:
        stmt = select(SubscriptionRecordV2).where(SubscriptionRecordV2.subscription_id == subscription_id)
        res = await self.session.execute(stmt)
        sub = res.scalar_one_or_none()
        if not sub:
            return None
        now = effective_time or datetime.now(timezone.utc)
        if sub.paused_at:
            paused_at = sub.paused_at if sub.paused_at.tzinfo else sub.paused_at.replace(tzinfo=timezone.utc)
            now_dt = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
            cur_end = sub.current_period_end if sub.current_period_end.tzinfo else sub.current_period_end.replace(tzinfo=timezone.utc)
            pause_duration = now_dt - paused_at
            sub.current_period_end = cur_end + pause_duration
            sub.paused_at = None

        sub.status = SubscriptionStatus.ACTIVE.value
        sub.updated_at = now
        await self.session.commit()
        return Subscription.model_validate(sub)

    async def upgrade_subscription(
        self,
        subscription_id: str,
        new_plan_id: str,
        new_plan_price_cents: int,
        old_plan_price_cents: int,
        effective_time: Optional[datetime] = None
    ) -> Tuple[Optional[Subscription], Any]:
        """
        Executes an immediate subscription plan upgrade with exact pro-rata billing (BIL-020).
        """
        stmt = select(SubscriptionRecordV2).where(SubscriptionRecordV2.subscription_id == subscription_id)
        res = await self.session.execute(stmt)
        sub = res.scalar_one_or_none()
        if not sub:
            return None, None

        eff_time = effective_time or datetime.now(timezone.utc)
        from models.proration import calculate_proration
        proration = calculate_proration(
            old_plan_price_cents=old_plan_price_cents,
            new_plan_price_cents=new_plan_price_cents,
            period_start=sub.current_period_start,
            period_end=sub.current_period_end,
            effective_time=eff_time
        )

        sub.plan_id = new_plan_id
        sub.updated_at = eff_time
        await self.session.commit()
        return Subscription.model_validate(sub), proration

    async def downgrade_subscription(
        self,
        subscription_id: str,
        new_plan_id: str,
        new_plan_price_cents: int,
        old_plan_price_cents: int,
        effective_time: Optional[datetime] = None,
        immediate: bool = True
    ) -> Tuple[Optional[Subscription], Optional[Any]]:
        """
        Executes a plan downgrade either immediately with pro-rata credit or scheduled at period end (BIL-021).
        """
        stmt = select(SubscriptionRecordV2).where(SubscriptionRecordV2.subscription_id == subscription_id)
        res = await self.session.execute(stmt)
        sub = res.scalar_one_or_none()
        if not sub:
            return None, None

        eff_time = effective_time or datetime.now(timezone.utc)
        from models.proration import calculate_proration
        if immediate:
            proration = calculate_proration(
                old_plan_price_cents=old_plan_price_cents,
                new_plan_price_cents=new_plan_price_cents,
                period_start=sub.current_period_start,
                period_end=sub.current_period_end,
                effective_time=eff_time
            )
            sub.plan_id = new_plan_id
            sub.updated_at = eff_time
        else:
            proration = None
            sub.plan_id = new_plan_id
            sub.updated_at = eff_time

        await self.session.commit()
        return Subscription.model_validate(sub), proration

    async def cancel_with_proration(
        self,
        subscription_id: str,
        plan_price_cents: int,
        effective_time: Optional[datetime] = None
    ) -> Tuple[Optional[Subscription], Any]:
        """
        Cancels subscription immediately and calculates unused pro-rata credit (BIL-022).
        """
        stmt = select(SubscriptionRecordV2).where(SubscriptionRecordV2.subscription_id == subscription_id)
        res = await self.session.execute(stmt)
        sub = res.scalar_one_or_none()
        if not sub:
            return None, None

        eff_time = effective_time or datetime.now(timezone.utc)
        from models.proration import calculate_proration
        proration = calculate_proration(
            old_plan_price_cents=plan_price_cents,
            new_plan_price_cents=0,
            period_start=sub.current_period_start,
            period_end=sub.current_period_end,
            effective_time=eff_time
        )
        sub.status = SubscriptionStatus.CANCELED.value
        sub.canceled_at = eff_time
        sub.updated_at = eff_time
        await self.session.commit()
        return Subscription.model_validate(sub), proration

    async def start_trial(
        self,
        subscription_id: str,
        tenant_id: str,
        customer_id: str,
        plan_id: str,
        trial_start: datetime,
        trial_end: datetime
    ) -> Subscription:
        """
        Initializes a subscription in TRIALING status with trial bounds (BIL-024).
        """
        rec = SubscriptionRecordV2(
            subscription_id=subscription_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            plan_id=plan_id,
            status=SubscriptionStatus.TRIALING.value,
            current_period_start=trial_start,
            current_period_end=trial_end,
            cancel_at_period_end=False,
            canceled_at=None,
            created_at=trial_start,
            updated_at=trial_start
        )
        self.session.add(rec)
        await self.session.commit()
        return Subscription.model_validate(rec)

    async def convert_trial_to_active(
        self,
        subscription_id: str,
        new_period_start: datetime,
        new_period_end: datetime
    ) -> Optional[Subscription]:
        """
        Converts a trialing subscription to fully ACTIVE upon trial expiration (BIL-024).
        """
        stmt = select(SubscriptionRecordV2).where(SubscriptionRecordV2.subscription_id == subscription_id)
        res = await self.session.execute(stmt)
        sub = res.scalar_one_or_none()
        if not sub:
            return None
        sub.status = SubscriptionStatus.ACTIVE.value
        sub.current_period_start = new_period_start
        sub.current_period_end = new_period_end
        sub.updated_at = new_period_start
        await self.session.commit()
        return Subscription.model_validate(sub)



class PlanAssignmentManager:
    """
    Manages Plan Catalog and Plan Assignment to Subscriptions (BIL-019).
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_plan(
        self,
        plan_id: str,
        tenant_id: str,
        name: str,
        description: str = "",
        currency: str = "USD_CENTS",
        interval: str = "MONTHLY"
    ) -> Plan:
        now = datetime.now(timezone.utc)
        rec = PlanRecord(
            plan_id=plan_id,
            tenant_id=tenant_id,
            name=name,
            description=description,
            currency=currency,
            interval=interval,
            created_at=now
        )
        self.session.add(rec)
        await self.session.commit()
        return Plan.model_validate(rec)

    async def get_plan(self, plan_id: str) -> Optional[Plan]:
        stmt = select(PlanRecord).where(PlanRecord.plan_id == plan_id)
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            return None
        return Plan.model_validate(rec)

    async def assign_plan_to_subscription(
        self,
        assignment_id: str,
        subscription_id: str,
        tenant_id: str,
        plan_id: str,
        effective_from: Optional[datetime] = None
    ) -> PlanAssignment:
        now = datetime.now(timezone.utc)
        eff_from = effective_from or now

        # Close any previous active assignment for this subscription
        stmt = select(PlanAssignmentRecord).where(
            PlanAssignmentRecord.subscription_id == subscription_id,
            PlanAssignmentRecord.effective_to.is_(None)
        )
        res = await self.session.execute(stmt)
        prev_assignments = res.scalars().all()
        for prev in prev_assignments:
            prev.effective_to = eff_from

        # Update the subscription itself
        sub_stmt = select(SubscriptionRecordV2).where(SubscriptionRecordV2.subscription_id == subscription_id)
        sub_res = await self.session.execute(sub_stmt)
        sub_rec = sub_res.scalar_one_or_none()
        if sub_rec:
            sub_rec.plan_id = plan_id
            sub_rec.updated_at = now

        # Add new assignment
        new_assignment = PlanAssignmentRecord(
            id=assignment_id,
            subscription_id=subscription_id,
            tenant_id=tenant_id,
            plan_id=plan_id,
            effective_from=eff_from,
            effective_to=None,
            created_at=now
        )
        self.session.add(new_assignment)
        await self.session.commit()
        return PlanAssignment.model_validate(new_assignment)

    async def get_subscription_plan_history(self, subscription_id: str) -> List[PlanAssignment]:
        stmt = select(PlanAssignmentRecord).where(
            PlanAssignmentRecord.subscription_id == subscription_id
        ).order_by(PlanAssignmentRecord.effective_from.asc())
        res = await self.session.execute(stmt)
        return [PlanAssignment.model_validate(r) for r in res.scalars().all()]
