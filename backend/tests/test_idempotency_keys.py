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
async def test_BIL_031_idempotency_keys(async_session):
    """
    BIL-031: Idempotency keys.
    Tests idempotency key scoping per tenant: identical idempotency keys belonging
    to DIFFERENT tenants are both accepted and isolated.
    """
    pipeline = UsageIngestionPipeline(async_session)

    # Ingest for Tenant A
    payload_a = IngestEventPayload(
        event_id="evt-tenant-a-1",
        tenant_id="tenant-alpha",
        customer_id="cust-1",
        event_type="bandwidth.mb",
        quantity=1000,
        idempotency_key="shared-client-uuid-999"
    )
    res_a = await pipeline.ingest_event(payload_a)
    assert res_a.status == IngestionStatus.ACCEPTED

    # Ingest same idempotency key for Tenant B
    payload_b = IngestEventPayload(
        event_id="evt-tenant-b-1",
        tenant_id="tenant-beta",
        customer_id="cust-2",
        event_type="bandwidth.mb",
        quantity=2000,
        idempotency_key="shared-client-uuid-999"
    )
    res_b = await pipeline.ingest_event(payload_b)
    assert res_b.status == IngestionStatus.ACCEPTED

    # Re-ingest for Tenant A: DUPLICATE
    res_a_dup = await pipeline.ingest_event(payload_a)
    assert res_a_dup.status == IngestionStatus.DUPLICATE
    assert res_a_dup.event_id == "evt-tenant-a-1"
