"""
Relational Billing Store Database Schema and Manager (BIL-003).
Stores relational entities: Customer accounts, Subscriptions, and Plans.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy import Column, String, BigInteger, DateTime, ForeignKey, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict
from db.database import Base

class CustomerAccountRecord(Base):
    __tablename__ = "customer_accounts"

    customer_id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    email = Column(String(128), nullable=False)
    currency = Column(String(16), default="USD_CENTS", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class SubscriptionRecord(Base):
    __tablename__ = "subscriptions"

    subscription_id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    customer_id = Column(String(64), ForeignKey("customer_accounts.customer_id"), nullable=False, index=True)
    plan_id = Column(String(64), nullable=False, index=True)
    status = Column(String(32), default="ACTIVE", nullable=False)
    current_period_start = Column(DateTime(timezone=True), nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class CustomerAccountSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    customer_id: str
    tenant_id: str
    name: str
    email: str
    currency: str = "USD_CENTS"
    created_at: Optional[datetime] = None

class SubscriptionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subscription_id: str
    tenant_id: str
    customer_id: str
    plan_id: str
    status: str
    current_period_start: datetime
    current_period_end: datetime

class BillingStoreManager:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_customer(
        self,
        customer_id: str,
        tenant_id: str,
        name: str,
        email: str,
        currency: str = "USD_CENTS"
    ) -> CustomerAccountSchema:
        rec = CustomerAccountRecord(
            customer_id=customer_id,
            tenant_id=tenant_id,
            name=name,
            email=email,
            currency=currency,
            created_at=datetime.now(timezone.utc)
        )
        self.session.add(rec)
        await self.session.commit()
        return CustomerAccountSchema.model_validate(rec)

    async def get_customer(self, customer_id: str) -> Optional[CustomerAccountSchema]:
        stmt = select(CustomerAccountRecord).where(CustomerAccountRecord.customer_id == customer_id)
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            return None
        return CustomerAccountSchema.model_validate(rec)

    async def create_subscription(
        self,
        subscription_id: str,
        tenant_id: str,
        customer_id: str,
        plan_id: str,
        current_period_start: datetime,
        current_period_end: datetime,
        status: str = "ACTIVE"
    ) -> SubscriptionSchema:
        rec = SubscriptionRecord(
            subscription_id=subscription_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            plan_id=plan_id,
            status=status,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            created_at=datetime.now(timezone.utc)
        )
        self.session.add(rec)
        await self.session.commit()
        return SubscriptionSchema.model_validate(rec)

    async def get_subscription(self, subscription_id: str) -> Optional[SubscriptionSchema]:
        stmt = select(SubscriptionRecord).where(SubscriptionRecord.subscription_id == subscription_id)
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            return None
        return SubscriptionSchema.model_validate(rec)
