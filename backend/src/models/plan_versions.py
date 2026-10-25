"""
Plan Versioning and Immutability Engine (BIL-040).
Guarantees plan versions are immutable once referenced by finalized invoices or active subscriptions.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy import Column, String, BigInteger, Boolean, DateTime, Index, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict
from db.database import Base

class PlanVersionRecord(Base):
    __tablename__ = "plan_versions"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    plan_id = Column(String(64), nullable=False, index=True)
    version = Column(BigInteger, nullable=False)
    name = Column(String(128), nullable=False)
    base_fee_cents = Column(BigInteger, default=0, nullable=False)
    min_charge_cents = Column(BigInteger, default=0, nullable=False)
    max_charge_cents = Column(BigInteger, nullable=True)
    is_locked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_tenant_plan_version", "tenant_id", "plan_id", "version", unique=True),
    )

class PlanVersionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    plan_id: str
    version: int
    name: str
    base_fee_cents: int
    min_charge_cents: int = 0
    max_charge_cents: Optional[int] = None
    is_locked: bool = False
    created_at: datetime

class PlanVersionManager:
    """
    Manages versioned plans with strict immutability checks upon finalization.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_plan_version(
        self,
        tenant_id: str,
        plan_id: str,
        name: str,
        base_fee_cents: int = 0,
        min_charge_cents: int = 0,
        max_charge_cents: Optional[int] = None
    ) -> PlanVersionSchema:
        # Determine next version
        stmt = (
            select(PlanVersionRecord.version)
            .where(PlanVersionRecord.tenant_id == tenant_id)
            .where(PlanVersionRecord.plan_id == plan_id)
            .order_by(PlanVersionRecord.version.desc())
        )
        res = await self.session.execute(stmt)
        latest = res.scalars().first()
        next_ver = (latest or 0) + 1

        rec = PlanVersionRecord(
            id=f"{plan_id}_v{next_ver}",
            tenant_id=tenant_id,
            plan_id=plan_id,
            version=next_ver,
            name=name,
            base_fee_cents=base_fee_cents,
            min_charge_cents=min_charge_cents,
            max_charge_cents=max_charge_cents,
            is_locked=False,
            created_at=datetime.now(timezone.utc)
        )
        self.session.add(rec)
        await self.session.commit()
        return PlanVersionSchema.model_validate(rec)

    async def get_version(self, tenant_id: str, plan_id: str, version: int) -> Optional[PlanVersionSchema]:
        stmt = (
            select(PlanVersionRecord)
            .where(PlanVersionRecord.tenant_id == tenant_id)
            .where(PlanVersionRecord.plan_id == plan_id)
            .where(PlanVersionRecord.version == version)
        )
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            return None
        return PlanVersionSchema.model_validate(rec)

    async def lock_version(self, tenant_id: str, plan_id: str, version: int) -> PlanVersionSchema:
        stmt = (
            select(PlanVersionRecord)
            .where(PlanVersionRecord.tenant_id == tenant_id)
            .where(PlanVersionRecord.plan_id == plan_id)
            .where(PlanVersionRecord.version == version)
        )
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            raise ValueError(f"Plan version {plan_id} v{version} not found")

        rec.is_locked = True
        await self.session.commit()
        return PlanVersionSchema.model_validate(rec)

    async def update_version(
        self,
        tenant_id: str,
        plan_id: str,
        version: int,
        name: Optional[str] = None,
        base_fee_cents: Optional[int] = None,
        min_charge_cents: Optional[int] = None,
        max_charge_cents: Optional[int] = None
    ) -> PlanVersionSchema:
        """
        Updates plan attributes. If the version is locked, mutability is strictly rejected.
        """
        stmt = (
            select(PlanVersionRecord)
            .where(PlanVersionRecord.tenant_id == tenant_id)
            .where(PlanVersionRecord.plan_id == plan_id)
            .where(PlanVersionRecord.version == version)
        )
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            raise ValueError(f"Plan version {plan_id} v{version} not found")

        if rec.is_locked:
            raise ValueError(f"ImmutableError: Plan '{plan_id}' version {version} is locked and cannot be modified")

        if name is not None:
            rec.name = name
        if base_fee_cents is not None:
            rec.base_fee_cents = base_fee_cents
        if min_charge_cents is not None:
            rec.min_charge_cents = min_charge_cents
        if max_charge_cents is not None:
            rec.max_charge_cents = max_charge_cents

        await self.session.commit()
        return PlanVersionSchema.model_validate(rec)
