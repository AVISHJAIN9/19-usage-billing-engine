"""
Aggregation & Billing Periods (BIL-054, BIL-055, BIL-057, BIL-064).
Manages:
- Monthly aggregation of metered usage.
- Billing period lifecycle (OPEN -> CLOSING -> CLOSED).
- Usage rollups pre-aggregation and raw-event reconciliation.
- Period close enforcement and immutability.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from enum import Enum
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import Column, String, BigInteger, DateTime, Index, CheckConstraint, select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import Base
from models.events import UsageEventRecord


class PeriodStatus(str, Enum):
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"


def _normalize_tz(v):
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


class BillingPeriodRecord(Base):
    __tablename__ = "billing_periods"

    period_id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    customer_id = Column(String(64), nullable=False, index=True)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(32), default=PeriodStatus.OPEN.value, nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_tenant_cust_period", "tenant_id", "customer_id", "start_date", "end_date"),
    )


class UsageRollupRecord(Base):
    __tablename__ = "usage_rollups"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    customer_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    granularity = Column(String(16), default="hourly", nullable=False)
    bucket_start = Column(DateTime(timezone=True), nullable=False)
    bucket_end = Column(DateTime(timezone=True), nullable=False)
    total_quantity = Column(BigInteger, nullable=False)
    event_count = Column(BigInteger, nullable=False)

    __table_args__ = (
        Index("ix_rollup_lookup", "tenant_id", "customer_id", "event_type", "granularity", "bucket_start"),
    )


class BillingPeriodSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period_id: str
    tenant_id: str
    customer_id: str
    start_date: datetime
    end_date: datetime
    status: PeriodStatus
    closed_at: Optional[datetime] = None

    @field_validator("start_date", "end_date", "closed_at", mode="before")
    @classmethod
    def normalize_dates(cls, v):
        return _normalize_tz(v)


class UsageRollupSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    customer_id: str
    event_type: str
    granularity: str = "hourly"
    bucket_start: datetime
    bucket_end: datetime
    total_quantity: int
    event_count: int

    @field_validator("bucket_start", "bucket_end", mode="before")
    @classmethod
    def normalize_dates(cls, v):
        return _normalize_tz(v)


class PeriodManager:
    """
    Manages billing periods and lifecycle transitions (BIL-055, BIL-064).
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_period(
        self,
        period_id: str,
        tenant_id: str,
        customer_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> BillingPeriodSchema:
        rec = BillingPeriodRecord(
            period_id=period_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            status=PeriodStatus.OPEN.value,
            closed_at=None,
            created_at=datetime.now(timezone.utc)
        )
        self.session.add(rec)
        await self.session.commit()
        return BillingPeriodSchema.model_validate(rec)

    async def get_period(self, period_id: str) -> Optional[BillingPeriodSchema]:
        stmt = select(BillingPeriodRecord).where(BillingPeriodRecord.period_id == period_id)
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            return None
        return BillingPeriodSchema.model_validate(rec)

    async def close_period(self, period_id: str) -> BillingPeriodSchema:
        """
        Closes a billing period, making it immutable (BIL-064).
        """
        stmt = select(BillingPeriodRecord).where(BillingPeriodRecord.period_id == period_id)
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            raise ValueError(f"Period {period_id} not found")

        rec.status = PeriodStatus.CLOSED.value
        rec.closed_at = datetime.now(timezone.utc)
        await self.session.commit()
        return BillingPeriodSchema.model_validate(rec)

    async def is_period_closed_for_timestamp(
        self,
        tenant_id: str,
        customer_id: str,
        ts: datetime
    ) -> bool:
        """
        Checks if the period covering the timestamp has already been closed.
        """
        stmt = select(BillingPeriodRecord).where(
            BillingPeriodRecord.tenant_id == tenant_id,
            BillingPeriodRecord.customer_id == customer_id,
            BillingPeriodRecord.start_date <= ts,
            BillingPeriodRecord.end_date >= ts
        )
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if rec and rec.status == PeriodStatus.CLOSED.value:
            return True
        return False


class UsageAggregator:
    """
    Computes monthly aggregations, hourly/daily rollups, and reconciles late events (BIL-052, BIL-053, BIL-054, BIL-057).
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def aggregate_monthly_usage(
        self,
        tenant_id: str,
        customer_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, int]:
        """
        Aggregates raw usage events across the monthly period grouped by event_type (BIL-054).
        """
        stmt = (
            select(
                UsageEventRecord.event_type,
                func.sum(UsageEventRecord.quantity).label("total_qty")
            )
            .where(
                UsageEventRecord.tenant_id == tenant_id,
                UsageEventRecord.customer_id == customer_id,
                UsageEventRecord.timestamp >= start_date,
                UsageEventRecord.timestamp <= end_date
            )
            .group_by(UsageEventRecord.event_type)
        )
        res = await self.session.execute(stmt)
        return {row[0]: int(row[1]) for row in res.all()}

    async def create_usage_rollup(
        self,
        rollup_id: str,
        tenant_id: str,
        customer_id: str,
        event_type: str,
        bucket_start: datetime,
        bucket_end: datetime
    ) -> UsageRollupSchema:
        """
        Rolls up raw usage events in a time bucket into pre-aggregated record (BIL-057).
        """
        stmt = (
            select(
                func.coalesce(func.sum(UsageEventRecord.quantity), 0).label("total_qty"),
                func.count(UsageEventRecord.event_id).label("cnt")
            )
            .where(
                UsageEventRecord.tenant_id == tenant_id,
                UsageEventRecord.customer_id == customer_id,
                UsageEventRecord.event_type == event_type,
                UsageEventRecord.timestamp >= bucket_start,
                UsageEventRecord.timestamp < bucket_end
            )
        )
        res = await self.session.execute(stmt)
        row = res.one()
        total_qty = int(row[0])
        event_count = int(row[1])

        rec = UsageRollupRecord(
            id=rollup_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            event_type=event_type,
            granularity="hourly",
            bucket_start=bucket_start,
            bucket_end=bucket_end,
            total_quantity=total_qty,
            event_count=event_count
        )
        self.session.add(rec)
        await self.session.commit()
        return UsageRollupSchema.model_validate(rec)

    async def aggregate_hourly(
        self,
        tenant_id: str,
        customer_id: str,
        event_type: str,
        bucket_time: datetime
    ) -> UsageRollupSchema:
        """
        BIL-052: Computes or updates hourly rollup for a 1-hour bucket.
        """
        bucket_start = bucket_time.replace(minute=0, second=0, microsecond=0)
        bucket_end = bucket_start + timedelta(hours=1)
        rollup_id = f"hourly_{tenant_id}_{customer_id}_{event_type}_{int(bucket_start.timestamp())}"

        # Re-aggregate raw events including any late-arriving events
        stmt = (
            select(
                func.coalesce(func.sum(UsageEventRecord.quantity), 0).label("total_qty"),
                func.count(UsageEventRecord.event_id).label("cnt")
            )
            .where(
                UsageEventRecord.tenant_id == tenant_id,
                UsageEventRecord.customer_id == customer_id,
                UsageEventRecord.event_type == event_type,
                UsageEventRecord.timestamp >= bucket_start,
                UsageEventRecord.timestamp < bucket_end
            )
        )
        res = await self.session.execute(stmt)
        row = res.one()
        total_qty = int(row[0])
        event_count = int(row[1])

        # Upsert rollup
        q_find = select(UsageRollupRecord).where(UsageRollupRecord.id == rollup_id)
        existing = (await self.session.execute(q_find)).scalar_one_or_none()
        if existing:
            existing.total_quantity = total_qty
            existing.event_count = event_count
            rec = existing
        else:
            rec = UsageRollupRecord(
                id=rollup_id,
                tenant_id=tenant_id,
                customer_id=customer_id,
                event_type=event_type,
                granularity="hourly",
                bucket_start=bucket_start,
                bucket_end=bucket_end,
                total_quantity=total_qty,
                event_count=event_count
            )
            self.session.add(rec)

        await self.session.commit()
        return UsageRollupSchema.model_validate(rec)

    async def aggregate_daily(
        self,
        tenant_id: str,
        customer_id: str,
        event_type: str,
        bucket_time: datetime
    ) -> UsageRollupSchema:
        """
        BIL-053: Computes or updates daily rollup for a 1-day bucket.
        """
        bucket_start = bucket_time.replace(hour=0, minute=0, second=0, microsecond=0)
        bucket_end = bucket_start + timedelta(days=1)
        rollup_id = f"daily_{tenant_id}_{customer_id}_{event_type}_{int(bucket_start.timestamp())}"

        stmt = (
            select(
                func.coalesce(func.sum(UsageEventRecord.quantity), 0).label("total_qty"),
                func.count(UsageEventRecord.event_id).label("cnt")
            )
            .where(
                UsageEventRecord.tenant_id == tenant_id,
                UsageEventRecord.customer_id == customer_id,
                UsageEventRecord.event_type == event_type,
                UsageEventRecord.timestamp >= bucket_start,
                UsageEventRecord.timestamp < bucket_end
            )
        )
        res = await self.session.execute(stmt)
        row = res.one()
        total_qty = int(row[0])
        event_count = int(row[1])

        q_find = select(UsageRollupRecord).where(UsageRollupRecord.id == rollup_id)
        existing = (await self.session.execute(q_find)).scalar_one_or_none()
        if existing:
            existing.total_quantity = total_qty
            existing.event_count = event_count
            rec = existing
        else:
            rec = UsageRollupRecord(
                id=rollup_id,
                tenant_id=tenant_id,
                customer_id=customer_id,
                event_type=event_type,
                granularity="daily",
                bucket_start=bucket_start,
                bucket_end=bucket_end,
                total_quantity=total_qty,
                event_count=event_count
            )
            self.session.add(rec)

        await self.session.commit()
        return UsageRollupSchema.model_validate(rec)

    async def recompute_from_scratch(
        self,
        tenant_id: str,
        customer_id: str,
        event_type: str,
        start_date: datetime,
        end_date: datetime
    ) -> int:
        """
        Differential test baseline: sum of raw events directly from source of truth.
        """
        stmt = (
            select(func.coalesce(func.sum(UsageEventRecord.quantity), 0))
            .where(
                UsageEventRecord.tenant_id == tenant_id,
                UsageEventRecord.customer_id == customer_id,
                UsageEventRecord.event_type == event_type,
                UsageEventRecord.timestamp >= start_date,
                UsageEventRecord.timestamp < end_date
            )
        )
        res = await self.session.execute(stmt)
        return int(res.scalar_one())

    async def sum_rollups_in_range(
        self,
        tenant_id: str,
        customer_id: str,
        event_type: str,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "hourly"
    ) -> int:
        stmt = (
            select(func.coalesce(func.sum(UsageRollupRecord.total_quantity), 0))
            .where(
                UsageRollupRecord.tenant_id == tenant_id,
                UsageRollupRecord.customer_id == customer_id,
                UsageRollupRecord.event_type == event_type,
                UsageRollupRecord.granularity == granularity,
                UsageRollupRecord.bucket_start >= start_date,
                UsageRollupRecord.bucket_end <= end_date
            )
        )
        res = await self.session.execute(stmt)
        return int(res.scalar_one())
