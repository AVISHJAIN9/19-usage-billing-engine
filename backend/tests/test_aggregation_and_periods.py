"""
Tests for Aggregation & Periods:
- BIL-052: Hourly aggregation (hourly rollups & differential recompute with late events)
- BIL-053: Daily aggregation (daily rollups & differential recompute with late events)
- BIL-063: Real-time usage counters (hot cache increments and Postgres reconciliation)
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from db.database import Base
from models.events import UsageEventRecord
from aggregation.periods import UsageAggregator, UsageRollupRecord
from aggregation.counters import RealtimeUsageCounter


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
async def test_BIL_052_hourly_aggregation_differential_and_late_events(async_session: AsyncSession):
    aggregator = UsageAggregator(async_session)
    base_time = datetime(2026, 10, 24, 10, 0, 0, tzinfo=timezone.utc)

    # 1. Ingest events across two hours: 10:00-11:00 and 11:00-12:00
    events = [
        UsageEventRecord(
            event_id="e-h-1", tenant_id="tenant-1", customer_id="cust-1",
            event_type="api_requests", quantity=50, idempotency_key="idemp-h1",
            timestamp=base_time + timedelta(minutes=10)
        ),
        UsageEventRecord(
            event_id="e-h-2", tenant_id="tenant-1", customer_id="cust-1",
            event_type="api_requests", quantity=70, idempotency_key="idemp-h2",
            timestamp=base_time + timedelta(minutes=45)
        ),
        UsageEventRecord(
            event_id="e-h-3", tenant_id="tenant-1", customer_id="cust-1",
            event_type="api_requests", quantity=100, idempotency_key="idemp-h3",
            timestamp=base_time + timedelta(hours=1, minutes=15)
        )
    ]
    for e in events:
        async_session.add(e)
    await async_session.commit()

    # 2. Compute hourly rollups
    r1 = await aggregator.aggregate_hourly("tenant-1", "cust-1", "api_requests", base_time)
    r2 = await aggregator.aggregate_hourly("tenant-1", "cust-1", "api_requests", base_time + timedelta(hours=1))

    assert r1.total_quantity == 120
    assert r1.event_count == 2
    assert r2.total_quantity == 100
    assert r2.event_count == 1

    # 3. Inject a late-arriving event for the first hour (timestamp 10:30)
    late_event = UsageEventRecord(
        event_id="e-h-late", tenant_id="tenant-1", customer_id="cust-1",
        event_type="api_requests", quantity=35, idempotency_key="idemp-h-late",
        timestamp=base_time + timedelta(minutes=30)
    )
    async_session.add(late_event)
    await async_session.commit()

    # Re-aggregate the first hour with the late event
    r1_updated = await aggregator.aggregate_hourly("tenant-1", "cust-1", "api_requests", base_time)
    assert r1_updated.total_quantity == 155
    assert r1_updated.event_count == 3

    # 4. Differential test: sum of rollups in range == from-scratch raw recompute
    rollup_sum = await aggregator.sum_rollups_in_range(
        "tenant-1", "cust-1", "api_requests",
        start_date=base_time,
        end_date=base_time + timedelta(hours=2),
        granularity="hourly"
    )
    raw_sum = await aggregator.recompute_from_scratch(
        "tenant-1", "cust-1", "api_requests",
        start_date=base_time,
        end_date=base_time + timedelta(hours=2)
    )
    assert rollup_sum == raw_sum
    assert rollup_sum == (155 + 100) == 255


@pytest.mark.asyncio
async def test_BIL_053_daily_aggregation_differential_and_late_events(async_session: AsyncSession):
    aggregator = UsageAggregator(async_session)
    day1 = datetime(2026, 10, 24, 0, 0, 0, tzinfo=timezone.utc)
    day2 = datetime(2026, 10, 25, 0, 0, 0, tzinfo=timezone.utc)

    # Ingest events on day 1 and day 2
    events = [
        UsageEventRecord(
            event_id="e-d-1", tenant_id="tenant-1", customer_id="cust-2",
            event_type="storage_bytes", quantity=1000, idempotency_key="idemp-d1",
            timestamp=day1 + timedelta(hours=5)
        ),
        UsageEventRecord(
            event_id="e-d-2", tenant_id="tenant-1", customer_id="cust-2",
            event_type="storage_bytes", quantity=2500, idempotency_key="idemp-d2",
            timestamp=day1 + timedelta(hours=14)
        ),
        UsageEventRecord(
            event_id="e-d-3", tenant_id="tenant-1", customer_id="cust-2",
            event_type="storage_bytes", quantity=4000, idempotency_key="idemp-d3",
            timestamp=day2 + timedelta(hours=3)
        ),
    ]
    for e in events:
        async_session.add(e)
    await async_session.commit()

    # Rollup daily
    r_day1 = await aggregator.aggregate_daily("tenant-1", "cust-2", "storage_bytes", day1)
    r_day2 = await aggregator.aggregate_daily("tenant-1", "cust-2", "storage_bytes", day2)
    assert r_day1.total_quantity == 3500
    assert r_day2.total_quantity == 4000

    # Inject late event for day 1
    late_d1 = UsageEventRecord(
        event_id="e-d-late", tenant_id="tenant-1", customer_id="cust-2",
        event_type="storage_bytes", quantity=500, idempotency_key="idemp-d-late",
        timestamp=day1 + timedelta(hours=22)
    )
    async_session.add(late_d1)
    await async_session.commit()

    # Re-run day 1 rollup
    r_day1_updated = await aggregator.aggregate_daily("tenant-1", "cust-2", "storage_bytes", day1)
    assert r_day1_updated.total_quantity == 4000

    # Differential test: rollups sum == raw events sum
    rollup_sum = await aggregator.sum_rollups_in_range(
        "tenant-1", "cust-2", "storage_bytes",
        start_date=day1,
        end_date=day2 + timedelta(days=1),
        granularity="daily"
    )
    raw_sum = await aggregator.recompute_from_scratch(
        "tenant-1", "cust-2", "storage_bytes",
        start_date=day1,
        end_date=day2 + timedelta(days=1)
    )
    assert rollup_sum == raw_sum == 8000


@pytest.mark.asyncio
async def test_BIL_063_realtime_usage_counters_and_postgres_reconciliation(async_session: AsyncSession):
    counter = RealtimeUsageCounter()
    tenant_id = "tenant-1"
    customer_id = "cust-live"
    event_type = "tokens_processed"

    # 1. Hot real-time increments in cache
    await counter.increment(tenant_id, customer_id, event_type, 150)
    await counter.increment(tenant_id, customer_id, event_type, 350)
    cached_val = await counter.get_count(tenant_id, customer_id, event_type)
    assert cached_val == 500

    # 2. Persisted events in Postgres DB: total 480 (a slight drift of 20 units pending async flush)
    events = [
        UsageEventRecord(
            event_id="e-rt-1", tenant_id=tenant_id, customer_id=customer_id,
            event_type=event_type, quantity=280, idempotency_key="idemp-rt1",
            timestamp=datetime.now(timezone.utc)
        ),
        UsageEventRecord(
            event_id="e-rt-2", tenant_id=tenant_id, customer_id=customer_id,
            event_type=event_type, quantity=200, idempotency_key="idemp-rt2",
            timestamp=datetime.now(timezone.utc)
        )
    ]
    for e in events:
        async_session.add(e)
    await async_session.commit()

    # 3. Reconcile with DB: DB has 480, Cache had 500 -> drift 20 (within documented bound of 50)
    report = await counter.reconcile_with_db(
        session=async_session,
        tenant_id=tenant_id,
        customer_id=customer_id,
        event_type=event_type,
        max_allowed_drift=50
    )

    assert report["drift"] == 20
    assert report["drift_within_bounds"] is True
    assert report["db_source_of_truth"] == 480
    assert report["reconciled"] is True

    # 4. Assert cache is now reconciled to match Postgres source of truth
    reconciled_val = await counter.get_count(tenant_id, customer_id, event_type)
    assert reconciled_val == 480
