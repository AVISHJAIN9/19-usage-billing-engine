import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from models.accounts import PlanAssignmentManager

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
async def test_BIL_039_pricing_plan_model(async_session):
    """
    BIL-039: Pricing plan model.
    Tests defining plans with billing intervals, currencies, descriptions, and plan metadata.
    """
    mgr = PlanAssignmentManager(async_session)

    plan = await mgr.create_plan(
        plan_id="plan-business-monthly",
        tenant_id="tenant-saas",
        name="Business Monthly",
        description="Business plan billed monthly in USD cents",
        currency="USD_CENTS",
        interval="MONTHLY"
    )

    assert plan.plan_id == "plan-business-monthly"
    assert plan.interval == "MONTHLY"
    assert plan.currency == "USD_CENTS"

    fetched = await mgr.get_plan("plan-business-monthly")
    assert fetched is not None
    assert fetched.name == "Business Monthly"
