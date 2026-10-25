"""
Meter Definition Store and Manager (BIL-104).
Allows tenants to define meters with event type mapping, unit, and aggregation rules (COUNT, SUM, MAX, UNIQUE).
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, String, DateTime, Index, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict
from db.database import Base


class MeterAggregationType(str, Enum):
    SUM = "SUM"
    COUNT = "COUNT"
    MAX = "MAX"
    LAST = "LAST"


class MeterRecord(Base):
    __tablename__ = "meters"

    meter_id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    event_type = Column(String(64), nullable=False, index=True)
    aggregation_type = Column(String(32), default=MeterAggregationType.SUM.value, nullable=False)
    unit = Column(String(32), default="units", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_tenant_meter_event", "tenant_id", "event_type", unique=True),
    )


class MeterSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    meter_id: str
    tenant_id: str
    name: str
    event_type: str
    aggregation_type: MeterAggregationType
    unit: str
    created_at: datetime


class MeterManager:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_meter(
        self,
        meter_id: str,
        tenant_id: str,
        name: str,
        event_type: str,
        aggregation_type: MeterAggregationType = MeterAggregationType.SUM,
        unit: str = "units"
    ) -> MeterSchema:
        rec = MeterRecord(
            meter_id=meter_id,
            tenant_id=tenant_id,
            name=name,
            event_type=event_type,
            aggregation_type=aggregation_type.value,
            unit=unit,
            created_at=datetime.now(timezone.utc)
        )
        self.session.add(rec)
        await self.session.commit()
        return MeterSchema.model_validate(rec)

    async def get_meter(self, tenant_id: str, meter_id: str) -> Optional[MeterSchema]:
        stmt = (
            select(MeterRecord)
            .where(MeterRecord.tenant_id == tenant_id)
            .where(MeterRecord.meter_id == meter_id)
        )
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            return None
        return MeterSchema.model_validate(rec)

    async def list_meters(self, tenant_id: str) -> List[MeterSchema]:
        stmt = select(MeterRecord).where(MeterRecord.tenant_id == tenant_id)
        res = await self.session.execute(stmt)
        return [MeterSchema.model_validate(r) for r in res.scalars().all()]
