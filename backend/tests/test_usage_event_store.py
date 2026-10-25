import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from models.events import UsageEventStore

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
async def test_BIL_001_usage_event_store(async_session):
    """
    BIL-001: Usage event store.
    Validates ingestion of metered usage events, dimension storage, idempotency,
    and querying across tenants and timestamps.
    """
    store = UsageEventStore(async_session)

    # 1. Ingest event
    now = datetime.now(timezone.utc)
    ev1 = await store.record_event(
        event_id="evt-101",
        tenant_id="tenant-alpha",
        customer_id="cust-1",
        event_type="api_requests",
        quantity=500,
        idempotency_key="idem-evt-1",
        timestamp=now,
        dimensions={"region": "us-east-1", "endpoint": "/v1/chat"}
    )
    assert ev1.event_id == "evt-101"
    assert ev1.quantity == 500
    assert ev1.dimensions["region"] == "us-east-1"

    # 2. Replay with same idempotency key returns existing event without duplicate
    ev1_replay = await store.record_event(
        event_id="evt-102-ignored",
        tenant_id="tenant-alpha",
        customer_id="cust-1",
        event_type="api_requests",
        quantity=500,
        idempotency_key="idem-evt-1",
        timestamp=now
    )
    assert ev1_replay.event_id == "evt-101"

    # 3. Query events by tenant and customer
    events = await store.query_events("tenant-alpha", "cust-1", event_type="api_requests")
    assert len(events) == 1
    assert events[0].event_id == "evt-101"

    # 4. Negative quantity rejected
    with pytest.raises(ValueError):
        await store.record_event(
            event_id="evt-bad",
            tenant_id="tenant-alpha",
            customer_id="cust-1",
            event_type="api_requests",
            quantity=-10,
            idempotency_key="bad-qty"
        )
