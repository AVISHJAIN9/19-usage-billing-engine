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
async def test_BIL_064_period_close(async_session):
    """
    BIL-064: Period close.
    Validates freezing of billing periods upon close, ensuring immutability
    and rejection/detection of event timestamps belonging to closed periods.
    """
    mgr = PeriodManager(async_session)

    start_date = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_date = datetime(2026, 9, 30, 23, 59, 59, tzinfo=timezone.utc)

    # Create period
    period = await mgr.create_period(
        period_id="period-september",
        tenant_id="tenant-fin",
        customer_id="cust-fin-1",
        start_date=start_date,
        end_date=end_date
    )
    assert period.status == PeriodStatus.OPEN

    # Close period
    closed = await mgr.close_period("period-september")
    assert closed.status == PeriodStatus.CLOSED
    assert closed.closed_at is not None

    # Check whether events dated September 15 are recognized as closed
    in_period_ts = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
    assert await mgr.is_period_closed_for_timestamp("tenant-fin", "cust-fin-1", in_period_ts) is True

    # Check whether events dated October 15 are NOT closed
    out_of_period_ts = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    assert await mgr.is_period_closed_for_timestamp("tenant-fin", "cust-fin-1", out_of_period_ts) is False
