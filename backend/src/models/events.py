"""
Usage Event Store Database Schema and Manager (BIL-001).
Stores granular metered usage records with dimension metadata and unique idempotency keys.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import json
from sqlalchemy import Column, String, BigInteger, DateTime, Index, CheckConstraint, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict
from db.database import Base

class UsageEventRecord(Base):
    __tablename__ = "usage_events"

    event_id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    customer_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    quantity = Column(BigInteger, nullable=False)
    dimensions_json = Column(String(1024), nullable=False, default="{}")
    idempotency_key = Column(String(128), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    received_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="chk_usage_quantity_nonneg"),
        Index("ix_tenant_idem", "tenant_id", "idempotency_key", unique=True),
        Index("ix_tenant_cust_time", "tenant_id", "customer_id", "timestamp"),
        Index("ix_usage_tenant_cust_type_time", "tenant_id", "customer_id", "event_type", "timestamp"),
        Index("ix_usage_tenant_type_time", "tenant_id", "event_type", "timestamp"),
        Index("ix_usage_tenant_time", "tenant_id", "timestamp"),
    )

class UsageEventSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    tenant_id: str
    customer_id: str
    event_type: str
    quantity: int
    dimensions: Dict[str, Any]
    idempotency_key: str
    timestamp: datetime
    received_at: Optional[datetime] = None

class UsageEventStore:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_event(
        self,
        event_id: str,
        tenant_id: str,
        customer_id: str,
        event_type: str,
        quantity: int,
        idempotency_key: str,
        timestamp: Optional[datetime] = None,
        dimensions: Optional[Dict[str, Any]] = None
    ) -> UsageEventSchema:
        if quantity < 0:
            raise ValueError("Quantity cannot be negative")

        event_ts = timestamp or datetime.now(timezone.utc)
        dims = dimensions or {}

        # Idempotency check: if already recorded for this tenant, return existing
        existing_stmt = (
            select(UsageEventRecord)
            .where(UsageEventRecord.tenant_id == tenant_id)
            .where(UsageEventRecord.idempotency_key == idempotency_key)
        )
        res = await self.session.execute(existing_stmt)
        existing = res.scalar_one_or_none()
        if existing:
            dims_dict = json.loads(existing.dimensions_json) if existing.dimensions_json else {}
            return UsageEventSchema(
                event_id=existing.event_id,
                tenant_id=existing.tenant_id,
                customer_id=existing.customer_id,
                event_type=existing.event_type,
                quantity=existing.quantity,
                dimensions=dims_dict,
                idempotency_key=existing.idempotency_key,
                timestamp=existing.timestamp,
                received_at=existing.received_at
            )

        rec = UsageEventRecord(
            event_id=event_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            event_type=event_type,
            quantity=quantity,
            dimensions_json=json.dumps(dims, sort_keys=True),
            idempotency_key=idempotency_key,
            timestamp=event_ts,
            received_at=datetime.now(timezone.utc)
        )
        self.session.add(rec)
        await self.session.commit()

        return UsageEventSchema(
            event_id=rec.event_id,
            tenant_id=rec.tenant_id,
            customer_id=rec.customer_id,
            event_type=rec.event_type,
            quantity=rec.quantity,
            dimensions=dims,
            idempotency_key=rec.idempotency_key,
            timestamp=rec.timestamp,
            received_at=rec.received_at
        )

    async def query_events(
        self,
        tenant_id: str,
        customer_id: str,
        event_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[UsageEventSchema]:
        stmt = (
            select(UsageEventRecord)
            .where(UsageEventRecord.tenant_id == tenant_id)
            .where(UsageEventRecord.customer_id == customer_id)
        )
        if event_type:
            stmt = stmt.where(UsageEventRecord.event_type == event_type)
        if start_time:
            stmt = stmt.where(UsageEventRecord.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(UsageEventRecord.timestamp <= end_time)

        stmt = stmt.order_by(UsageEventRecord.timestamp.asc())
        res = await self.session.execute(stmt)
        records = res.scalars().all()

        results = []
        for r in records:
            dims = json.loads(r.dimensions_json) if r.dimensions_json else {}
            results.append(UsageEventSchema(
                event_id=r.event_id,
                tenant_id=r.tenant_id,
                customer_id=r.customer_id,
                event_type=r.event_type,
                quantity=r.quantity,
                dimensions=dims,
                idempotency_key=r.idempotency_key,
                timestamp=r.timestamp,
                received_at=r.received_at
            ))
        return results
