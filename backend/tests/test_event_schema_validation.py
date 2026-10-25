import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from metering.ingestion import UsageIngestionPipeline, IngestEventPayload, IngestionStatus

@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        yield session
    await engine.dispose()

@pytest.mark.asyncio
async def test_BIL_027_event_schema_validation(async_session):
    """
    BIL-027: Event schema validation.
    Tests validation of event schema, required fields, negative quantities,
    invalid event type formatting, and timestamp drift constraints.
    """
    pipeline = UsageIngestionPipeline(async_session, max_drift_days=30)

    # 1. Negative quantity rejected by schema validator
    with pytest.raises(ValidationError):
        IngestEventPayload(
            tenant_id="tenant-saas",
            customer_id="cust-1",
            event_type="compute.seconds",
            quantity=-5,
            idempotency_key="k1"
        )

    # 2. Empty tenant_id rejected
    with pytest.raises(ValidationError):
        IngestEventPayload(
            tenant_id="   ",
            customer_id="cust-1",
            event_type="compute.seconds",
            quantity=10,
            idempotency_key="k2"
        )

    # 3. Invalid event_type format (disallowed characters)
    with pytest.raises(ValidationError):
        IngestEventPayload(
            tenant_id="tenant-saas",
            customer_id="cust-1",
            event_type="compute*seconds#bad",
            quantity=10,
            idempotency_key="k3"
        )

    # 4. Out-of-bounds timestamp (too far in past > 30 days) rejected by pipeline validation
    too_old_ts = datetime.now(timezone.utc) - timedelta(days=45)
    old_event = IngestEventPayload(
        tenant_id="tenant-saas",
        customer_id="cust-1",
        event_type="compute.seconds",
        quantity=10,
        idempotency_key="k4",
        timestamp=too_old_ts
    )
    res_old = await pipeline.ingest_event(old_event)
    assert res_old.status == IngestionStatus.REJECTED
    assert "older than allowed window" in res_old.error
