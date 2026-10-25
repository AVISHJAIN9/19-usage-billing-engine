import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from metering.ingestion import UsageIngestionPipeline, IngestEventPayload

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
async def test_BIL_035_tenant_attribution(async_session):
    """
    BIL-035: Tenant attribution.
    Tests strict multi-tenant isolation, ensuring usage queries and summaries
    never leak across tenants, with complete customer and event-type breakdown.
    """
    pipeline = UsageIngestionPipeline(async_session)

    # Ingest for Tenant A
    await pipeline.ingest_batch([
        IngestEventPayload(
            tenant_id="tenant-tenant-a",
            customer_id="cust-a1",
            event_type="storage.gb",
            quantity=100,
            idempotency_key="t-a-1"
        ),
        IngestEventPayload(
            tenant_id="tenant-tenant-a",
            customer_id="cust-a2",
            event_type="storage.gb",
            quantity=200,
            idempotency_key="t-a-2"
        ),
        IngestEventPayload(
            tenant_id="tenant-tenant-a",
            customer_id="cust-a1",
            event_type="compute.hours",
            quantity=50,
            idempotency_key="t-a-3"
        )
    ])

    # Ingest for Tenant B
    await pipeline.ingest_batch([
        IngestEventPayload(
            tenant_id="tenant-tenant-b",
            customer_id="cust-b1",
            event_type="storage.gb",
            quantity=500,
            idempotency_key="t-b-1"
        )
    ])

    # Tenant A Attribution Summary
    attr_a = await pipeline.get_tenant_attribution("tenant-tenant-a")
    assert attr_a["tenant_id"] == "tenant-tenant-a"
    assert attr_a["total_events"] == 3
    assert attr_a["total_quantity"] == 350
    assert attr_a["by_customer"]["cust-a1"] == 150  # 100 storage + 50 compute
    assert attr_a["by_customer"]["cust-a2"] == 200
    assert "cust-b1" not in attr_a["by_customer"]
    assert attr_a["by_event_type"]["storage.gb"] == 300
    assert attr_a["by_event_type"]["compute.hours"] == 50

    # Tenant B Attribution Summary
    attr_b = await pipeline.get_tenant_attribution("tenant-tenant-b")
    assert attr_b["tenant_id"] == "tenant-tenant-b"
    assert attr_b["total_events"] == 1
    assert attr_b["total_quantity"] == 500
    assert "cust-a1" not in attr_b["by_customer"]
