import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from rating.engine import PriceBookManager, PricingType

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
async def test_BIL_041_price_book(async_session):
    """
    BIL-041: Price book.
    Tests maintaining a price book with catalog entries linking event types to pricing strategies.
    """
    mgr = PriceBookManager(async_session)

    # Add entries to price book for plan
    await mgr.add_entry(
        entry_id="pb-entry-1",
        tenant_id="tenant-acme",
        plan_id="plan-pro",
        event_type="api.requests",
        pricing_type=PricingType.PER_UNIT,
        unit_price_cents=2
    )

    await mgr.add_entry(
        entry_id="pb-entry-2",
        tenant_id="tenant-acme",
        plan_id="plan-pro",
        event_type="storage.gb",
        pricing_type=PricingType.PER_UNIT,
        unit_price_cents=15
    )

    entries = await mgr.get_entries_for_plan("tenant-acme", "plan-pro")
    assert len(entries) == 2
    types = {e.event_type: e.unit_price_cents for e in entries}
    assert types["api.requests"] == 2
    assert types["storage.gb"] == 15
