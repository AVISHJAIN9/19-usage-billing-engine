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
async def test_BIL_026_usage_event_ingestion(async_session):
    """
    BIL-026: Usage event ingestion.
    Tests single and batch ingestion of events into the storage pipeline.
    """
    pipeline = UsageIngestionPipeline(async_session)

    # 1. Ingest single event
    payload1 = IngestEventPayload(
        event_id="evt-ingest-1",
        tenant_id="tenant-prod",
        customer_id="cust-100",
        event_type="api.calls",
        quantity=50,
        idempotency_key="key-ingest-1",
        dimensions={"route": "/v1/inference"}
    )
    res1 = await pipeline.ingest_event(payload1)
    assert res1.status == IngestionStatus.ACCEPTED
    assert res1.event_id == "evt-ingest-1"

    # 2. Ingest batch
    batch = [
        IngestEventPayload(
            event_id="evt-ingest-2",
            tenant_id="tenant-prod",
            customer_id="cust-100",
            event_type="storage.gigabytes",
            quantity=120,
            idempotency_key="key-ingest-2"
        ),
        IngestEventPayload(
            event_id="evt-ingest-3",
            tenant_id="tenant-prod",
            customer_id="cust-200",
            event_type="api.calls",
            quantity=80,
            idempotency_key="key-ingest-3"
        )
    ]
    batch_res = await pipeline.ingest_batch(batch)
    assert len(batch_res) == 2
    assert all(r.status == IngestionStatus.ACCEPTED for r in batch_res)
