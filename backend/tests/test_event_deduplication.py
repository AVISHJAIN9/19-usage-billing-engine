import pytest
import pytest_asyncio
from datetime import datetime, timezone
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
async def test_BIL_030_event_deduplication(async_session):
    """
    BIL-030: Event deduplication.
    Tests deduplication of events with identical idempotency key for the same tenant.
    """
    pipeline = UsageIngestionPipeline(async_session)

    payload = IngestEventPayload(
        event_id="evt-dedup-orig",
        tenant_id="tenant-dedup-test",
        customer_id="cust-dedup",
        event_type="tokens.prompt",
        quantity=500,
        idempotency_key="dedup-token-key-1"
    )

    # First attempt: ACCEPTED
    res1 = await pipeline.ingest_event(payload)
    assert res1.status == IngestionStatus.ACCEPTED
    assert res1.event_id == "evt-dedup-orig"

    # Second attempt with same key & tenant: DUPLICATE
    res2 = await pipeline.ingest_event(payload)
    assert res2.status == IngestionStatus.DUPLICATE
    assert res2.event_id == "evt-dedup-orig"

    # Query events to verify only ONE event recorded
    events = await pipeline.event_store.query_events(
        tenant_id="tenant-dedup-test",
        customer_id="cust-dedup"
    )
    assert len(events) == 1
    assert events[0].quantity == 500
