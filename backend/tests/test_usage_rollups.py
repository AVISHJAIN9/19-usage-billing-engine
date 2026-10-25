import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from models.events import UsageEventStore
from aggregation.periods import UsageAggregator

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
async def test_BIL_057_usage_rollups(async_session):
    """
    BIL-057: Usage rollups.
    Tests pre-aggregation of raw usage events into hourly/daily rollups,
    verifying rollup total_quantity matches raw event sum.
    """
    store = UsageEventStore(async_session)
    aggregator = UsageAggregator(async_session)

    b_start = datetime(2026, 10, 24, 10, 0, 0, tzinfo=timezone.utc)
    b_end = datetime(2026, 10, 24, 11, 0, 0, tzinfo=timezone.utc)

    # Insert 3 events inside the bucket
    await store.record_event(
        event_id="ev-roll-1",
        tenant_id="tenant-saas",
        customer_id="cust-roll",
        event_type="tokens.input",
        quantity=300,
        idempotency_key="k-r-1",
        timestamp=b_start + timedelta(minutes=10)
    )
    await store.record_event(
        event_id="ev-roll-2",
        tenant_id="tenant-saas",
        customer_id="cust-roll",
        event_type="tokens.input",
        quantity=500,
        idempotency_key="k-r-2",
        timestamp=b_start + timedelta(minutes=25)
    )
    await store.record_event(
        event_id="ev-roll-3",
        tenant_id="tenant-saas",
        customer_id="cust-roll",
        event_type="tokens.input",
        quantity=200,
        idempotency_key="k-r-3",
        timestamp=b_start + timedelta(minutes=50)
    )

    # Generate rollup
    rollup = await aggregator.create_usage_rollup(
        rollup_id="rollup-2026-10-24-10",
        tenant_id="tenant-saas",
        customer_id="cust-roll",
        event_type="tokens.input",
        bucket_start=b_start,
        bucket_end=b_end
    )

    assert rollup.id == "rollup-2026-10-24-10"
    assert rollup.event_count == 3
    assert rollup.total_quantity == 1000  # Invariant: 300 + 500 + 200 == 1000
