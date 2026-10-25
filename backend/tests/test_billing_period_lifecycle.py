import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from aggregation.periods import PeriodManager, PeriodStatus

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
async def test_BIL_055_billing_period_lifecycle(async_session):
    """
    BIL-055: Billing-period lifecycle.
    Tests creation and state progression of a billing period (OPEN -> CLOSED).
    """
    mgr = PeriodManager(async_session)

    start_date = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_date = datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc)

    # 1. Create period: Starts in OPEN status
    period = await mgr.create_period(
        period_id="period-2026-10",
        tenant_id="tenant-acme",
        customer_id="cust-1",
        start_date=start_date,
        end_date=end_date
    )
    assert period.period_id == "period-2026-10"
    assert period.status == PeriodStatus.OPEN
    assert period.closed_at is None

    # Check is_closed
    is_closed = await mgr.is_period_closed_for_timestamp("tenant-acme", "cust-1", start_date + timedelta(days=5))
    assert is_closed is False

    # 2. Close period
    closed = await mgr.close_period("period-2026-10")
    assert closed.status == PeriodStatus.CLOSED
    assert closed.closed_at is not None

    # Verify closed status check
    is_closed_after = await mgr.is_period_closed_for_timestamp("tenant-acme", "cust-1", start_date + timedelta(days=5))
    assert is_closed_after is True
