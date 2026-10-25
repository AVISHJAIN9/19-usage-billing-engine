"""
Usage Metering Core & Ingestion Engine (BIL-026, BIL-027, BIL-030, BIL-031, BIL-032, BIL-035).
Provides:
- Ingestion pipeline with validation, deduplication, and attribution.
- Schema validation with timestamp drift checks.
- Idempotency key tracking and deduplication.
- Dimensional querying and aggregation.
- Strict multi-tenant attribution and isolation.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from enum import Enum
import json
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from models.events import UsageEventRecord, UsageEventSchema, UsageEventStore


class IngestionStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    REJECTED = "REJECTED"


class UsageUnit(str, Enum):
    COUNT = "COUNT"
    BYTES = "BYTES"
    KILOBYTES = "KILOBYTES"
    MEGABYTES = "MEGABYTES"
    GIGABYTES = "GIGABYTES"
    SECONDS = "SECONDS"
    MILLISECONDS = "MILLISECONDS"
    MINUTES = "MINUTES"
    HOURS = "HOURS"
    TOKENS = "TOKENS"


def convert_usage_unit(quantity: float, from_unit: UsageUnit, to_unit: UsageUnit) -> float:
    """
    Unit conversion engine for metered usage dimensions (BIL-038).
    Converts storage bytes, execution runtimes, and token counts.
    """
    byte_multipliers = {
        UsageUnit.BYTES: 1.0,
        UsageUnit.KILOBYTES: 1024.0,
        UsageUnit.MEGABYTES: 1024.0**2,
        UsageUnit.GIGABYTES: 1024.0**3,
    }
    time_multipliers = {
        UsageUnit.MILLISECONDS: 0.001,
        UsageUnit.SECONDS: 1.0,
        UsageUnit.MINUTES: 60.0,
        UsageUnit.HOURS: 3600.0,
    }
    if from_unit in byte_multipliers and to_unit in byte_multipliers:
        bytes_val = float(quantity) * byte_multipliers[from_unit]
        return bytes_val / byte_multipliers[to_unit]
    elif from_unit in time_multipliers and to_unit in time_multipliers:
        seconds_val = float(quantity) * time_multipliers[from_unit]
        return seconds_val / time_multipliers[to_unit]
    elif from_unit == to_unit:
        return float(quantity)
    else:
        raise ValueError(f"Incompatible unit conversion from {from_unit} to {to_unit}")


class IngestEventPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: Optional[str] = None
    tenant_id: str
    customer_id: str
    event_type: str
    quantity: int
    idempotency_key: str
    timestamp: Optional[datetime] = None
    project_id: Optional[str] = None
    unit: Optional[str] = "COUNT"
    dimensions: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("tenant_id", "customer_id", "event_type", "idempotency_key")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace")
        return v.strip()

    @field_validator("event_type")
    @classmethod
    def validate_event_type_format(cls, v: str) -> str:
        # Event type must match alphanumeric with dots, dashes, underscores
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", v):
            raise ValueError(f"Invalid event_type format: '{v}'")
        return v

    @field_validator("quantity")
    @classmethod
    def validate_quantity_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Quantity cannot be negative")
        return v

    @field_validator("timestamp", mode="before")
    @classmethod
    def normalize_timestamp(cls, v):
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


class IngestionResponse(BaseModel):
    status: IngestionStatus
    event_id: Optional[str] = None
    tenant_id: str
    idempotency_key: str
    error: Optional[str] = None


class UsageIngestionPipeline:
    def __init__(self, session: AsyncSession, max_drift_days: int = 90):
        self.session = session
        self.event_store = UsageEventStore(session)
        self.max_drift_days = max_drift_days

    def validate_payload(self, payload: IngestEventPayload) -> Tuple[bool, Optional[str]]:
        """
        Validates event schema, timestamp boundaries, and dimension formats (BIL-027, BIL-029).
        """
        if payload.quantity < 0:
            return False, "QUANTITY_NEGATIVE: Quantity cannot be negative"

        event_ts = payload.timestamp or datetime.now(timezone.utc)
        if event_ts.tzinfo is None:
            event_ts = event_ts.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)

        # Allow max drift: not more than max_drift_days in past, and not more than 1 hour in future (BIL-029)
        if event_ts < now - timedelta(days=self.max_drift_days):
            return False, f"TIMESTAMP_TOO_OLD: Timestamp is older than allowed window of {self.max_drift_days} days"
        if event_ts > now + timedelta(hours=1):
            return False, "TIMESTAMP_IN_FUTURE: Timestamp cannot be in the future beyond 1 hour"

        # Dimensions must be json-serializable dict
        try:
            json.dumps(payload.dimensions)
        except Exception as e:
            return False, f"Dimensions not JSON serializable: {str(e)}"

        return True, None

    async def ingest_event(self, payload: IngestEventPayload) -> IngestionResponse:
        """
        Ingests a single usage event with validation and deduplication (BIL-026, BIL-030, BIL-031).
        """
        # 1. Validation
        is_valid, err = self.validate_payload(payload)
        if not is_valid:
            return IngestionResponse(
                status=IngestionStatus.REJECTED,
                tenant_id=payload.tenant_id,
                idempotency_key=payload.idempotency_key,
                error=err
            )

        # 2. Deduplication check via idempotency key + tenant
        existing_stmt = select(UsageEventRecord).where(
            UsageEventRecord.tenant_id == payload.tenant_id,
            UsageEventRecord.idempotency_key == payload.idempotency_key
        )
        res = await self.session.execute(existing_stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return IngestionResponse(
                status=IngestionStatus.DUPLICATE,
                event_id=existing.event_id,
                tenant_id=existing.tenant_id,
                idempotency_key=existing.idempotency_key,
                error=None
            )

        # 3. Ingestion & Persistence
        import uuid
        event_id = payload.event_id or f"evt-{uuid.uuid4().hex[:12]}"

        # Merge project_id and unit into dimensions
        dims = dict(payload.dimensions)
        if payload.project_id:
            dims["project_id"] = payload.project_id
        if payload.unit:
            dims["unit"] = payload.unit

        stored = await self.event_store.record_event(
            event_id=event_id,
            tenant_id=payload.tenant_id,
            customer_id=payload.customer_id,
            event_type=payload.event_type,
            quantity=payload.quantity,
            idempotency_key=payload.idempotency_key,
            timestamp=payload.timestamp or datetime.now(timezone.utc),
            dimensions=dims
        )

        return IngestionResponse(
            status=IngestionStatus.ACCEPTED,
            event_id=stored.event_id,
            tenant_id=stored.tenant_id,
            idempotency_key=stored.idempotency_key
        )

    async def ingest_batch(self, payloads: List[IngestEventPayload]) -> List[IngestionResponse]:
        """
        Batch ingestion pipeline (BIL-026).
        """
        results = []
        for p in payloads:
            res = await self.ingest_event(p)
            results.append(res)
        return results

    async def aggregate_by_dimension(
        self,
        tenant_id: str,
        customer_id: str,
        event_type: str,
        dimension_key: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        Aggregates usage quantity grouped by a specific dimension value (BIL-032).
        """
        events = await self.event_store.query_events(
            tenant_id=tenant_id,
            customer_id=customer_id,
            event_type=event_type,
            start_time=start_time,
            end_time=end_time
        )

        breakdown: Dict[str, int] = {}
        for ev in events:
            val = str(ev.dimensions.get(dimension_key, "UNKNOWN"))
            breakdown[val] = breakdown.get(val, 0) + ev.quantity

        return breakdown

    async def get_tenant_attribution(
        self,
        tenant_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Summarizes usage strictly attributed to a specific tenant (BIL-035).
        Guarantees multi-tenant isolation.
        """
        stmt = select(UsageEventRecord).where(UsageEventRecord.tenant_id == tenant_id)
        if start_time:
            stmt = stmt.where(UsageEventRecord.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(UsageEventRecord.timestamp <= end_time)

        res = await self.session.execute(stmt)
        records = res.scalars().all()

        customer_totals: Dict[str, int] = {}
        event_type_totals: Dict[str, int] = {}
        total_quantity = 0

        for r in records:
            customer_totals[r.customer_id] = customer_totals.get(r.customer_id, 0) + r.quantity
            event_type_totals[r.event_type] = event_type_totals.get(r.event_type, 0) + r.quantity
            total_quantity += r.quantity

        return {
            "tenant_id": tenant_id,
            "total_events": len(records),
            "total_quantity": total_quantity,
            "by_customer": customer_totals,
            "by_event_type": event_type_totals
        }

    async def aggregate_by_project(
        self,
        tenant_id: str,
        customer_id: str,
        event_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        Aggregates metered usage grouped by project_id within a customer account (BIL-037).
        """
        events = await self.event_store.query_events(
            tenant_id=tenant_id,
            customer_id=customer_id,
            event_type=event_type,
            start_time=start_time,
            end_time=end_time
        )

        breakdown: Dict[str, int] = {}
        for ev in events:
            proj = ev.dimensions.get("project_id", "default")
            breakdown[proj] = breakdown.get(proj, 0) + ev.quantity

        return breakdown

