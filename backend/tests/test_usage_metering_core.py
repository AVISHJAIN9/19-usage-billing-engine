import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from metering.ingestion import (
    UsageIngestionPipeline, IngestEventPayload, IngestionStatus,
    UsageUnit, convert_usage_unit
)

@pytest_asyncio.fixture
async def metering_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        yield session
    await engine.dispose()

@pytest.mark.asyncio
async def test_BIL_029_timestamp_validation(metering_session):
    """
    BIL-029: Timestamp validation and boundary drift checking.
    Verifies that timestamps too far in the past or in the future are strictly rejected.
    """
    pipeline = UsageIngestionPipeline(metering_session, max_drift_days=30)
    now = datetime.now(timezone.utc)

    # 1. Valid timestamp within current window
    valid_payload = IngestEventPayload(
        tenant_id="tenant-time-1",
        customer_id="cust-time-1",
        event_type="api_requests",
        quantity=100,
        idempotency_key="idemp-valid-ts",
        timestamp=now - timedelta(days=2)
    )
    res_valid = await pipeline.ingest_event(valid_payload)
    assert res_valid.status == IngestionStatus.ACCEPTED

    # 2. Timestamp too old (older than 30 days)
    old_payload = IngestEventPayload(
        tenant_id="tenant-time-1",
        customer_id="cust-time-1",
        event_type="api_requests",
        quantity=100,
        idempotency_key="idemp-old-ts",
        timestamp=now - timedelta(days=35)
    )
    res_old = await pipeline.ingest_event(old_payload)
    assert res_old.status == IngestionStatus.REJECTED
    assert "TIMESTAMP_TOO_OLD" in res_old.error

    # 3. Timestamp too far in future (> 1 hour)
    future_payload = IngestEventPayload(
        tenant_id="tenant-time-1",
        customer_id="cust-time-1",
        event_type="api_requests",
        quantity=100,
        idempotency_key="idemp-future-ts",
        timestamp=now + timedelta(hours=5)
    )
    res_future = await pipeline.ingest_event(future_payload)
    assert res_future.status == IngestionStatus.REJECTED
    assert "TIMESTAMP_IN_FUTURE" in res_future.error

@pytest.mark.asyncio
async def test_BIL_037_project_attribution(metering_session):
    """
    BIL-037: Usage project attribution and project-level breakdown.
    Attributes usage events to separate project identifiers within a single customer.
    """
    pipeline = UsageIngestionPipeline(metering_session)
    now = datetime.now(timezone.utc)

    # Ingest events across projects
    events = [
        IngestEventPayload(
            tenant_id="tenant-proj-1",
            customer_id="cust-proj-1",
            project_id="proj-ai-inference",
            event_type="compute_seconds",
            quantity=5000,
            idempotency_key="idem-p1"
        ),
        IngestEventPayload(
            tenant_id="tenant-proj-1",
            customer_id="cust-proj-1",
            project_id="proj-web-frontend",
            event_type="compute_seconds",
            quantity=3000,
            idempotency_key="idem-p2"
        ),
        IngestEventPayload(
            tenant_id="tenant-proj-1",
            customer_id="cust-proj-1",
            project_id="proj-db-cluster",
            event_type="compute_seconds",
            quantity=2000,
            idempotency_key="idem-p3"
        ),
        IngestEventPayload(
            tenant_id="tenant-proj-1",
            customer_id="cust-proj-1",
            event_type="compute_seconds",
            quantity=1000,
            idempotency_key="idem-p4"
        )
    ]

    for ev in events:
        resp = await pipeline.ingest_event(ev)
        assert resp.status == IngestionStatus.ACCEPTED

    # Query project breakdown
    breakdown = await pipeline.aggregate_by_project(
        tenant_id="tenant-proj-1",
        customer_id="cust-proj-1",
        event_type="compute_seconds"
    )

    assert breakdown["proj-ai-inference"] == 5000
    assert breakdown["proj-web-frontend"] == 3000
    assert breakdown["proj-db-cluster"] == 2000
    assert breakdown["default"] == 1000
    assert sum(breakdown.values()) == 11000

def test_BIL_038_usage_units_and_conversion():
    """
    BIL-038: Usage units and unit conversion engine.
    Verifies metric conversion across storage bytes, runtimes, and tokens.
    """
    # 1. Byte conversions
    one_gb_in_bytes = 1024 * 1024 * 1024
    assert convert_usage_unit(one_gb_in_bytes, UsageUnit.BYTES, UsageUnit.GIGABYTES) == 1.0
    assert convert_usage_unit(2.5, UsageUnit.GIGABYTES, UsageUnit.MEGABYTES) == 2560.0

    # 2. Time conversions
    assert convert_usage_unit(120, UsageUnit.SECONDS, UsageUnit.MINUTES) == 2.0
    assert convert_usage_unit(3600, UsageUnit.SECONDS, UsageUnit.HOURS) == 1.0
    assert convert_usage_unit(1500, UsageUnit.MILLISECONDS, UsageUnit.SECONDS) == 1.5

    # 3. Same unit identity
    assert convert_usage_unit(5000, UsageUnit.TOKENS, UsageUnit.TOKENS) == 5000.0

    # 4. Incompatible units raise ValueError
    with pytest.raises(ValueError, match="Incompatible unit conversion"):
        convert_usage_unit(100, UsageUnit.BYTES, UsageUnit.SECONDS)
