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
async def test_BIL_054_monthly_aggregation(async_session):
    """
    BIL-054: Monthly aggregation.
    Tests collecting and aggregating events across month bounds by customer and event_type.
    """
    store = UsageEventStore(async_session)
    aggregator = UsageAggregator(async_session)

    month_start = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    month_end = datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc)

    # 1. Events inside October
    await store.record_event(
        event_id="ev-oct-1",
        tenant_id="t1",
        customer_id="cust-1",
        event_type="api.calls",
        quantity=500,
        idempotency_key="k-oct-1",
        timestamp=month_start + timedelta(days=2)
    )
    await store.record_event(
        event_id="ev-oct-2",
        tenant_id="t1",
        customer_id="cust-1",
        event_type="api.calls",
        quantity=700,
        idempotency_key="k-oct-2",
        timestamp=month_start + timedelta(days=15)
    )
    await store.record_event(
        event_id="ev-oct-3",
        tenant_id="t1",
        customer_id="cust-1",
        event_type="storage.gb",
        quantity=25,
        idempotency_key="k-oct-3",
        timestamp=month_start + timedelta(days=10)
    )

    # 2. Event outside October (November) - should NOT be included
    await store.record_event(
        event_id="ev-nov-1",
        tenant_id="t1",
        customer_id="cust-1",
        event_type="api.calls",
        quantity=1000,
        idempotency_key="k-nov-1",
        timestamp=datetime(2026, 11, 2, 0, 0, 0, tzinfo=timezone.utc)
    )

    # Perform monthly aggregation
    totals = await aggregator.aggregate_monthly_usage("t1", "cust-1", month_start, month_end)
    assert totals["api.calls"] == 1200  # 500 + 700 (Nov event excluded)
    assert totals["storage.gb"] == 25
