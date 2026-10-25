import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from models.billing import BillingStoreManager

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
async def test_BIL_003_relational_billing_store(async_session):
    """
    BIL-003: Relational billing store.
    Validates creation and querying of core customer accounts and subscriptions.
    """
    mgr = BillingStoreManager(async_session)

    # 1. Create customer account
    cust = await mgr.create_customer(
        customer_id="cust-acme-1",
        tenant_id="tenant-saas",
        name="Acme Corp",
        email="billing@acme.com",
        currency="USD_CENTS"
    )
    assert cust.customer_id == "cust-acme-1"
    assert cust.currency == "USD_CENTS"

    # Query customer
    fetched_cust = await mgr.get_customer("cust-acme-1")
    assert fetched_cust is not None
    assert fetched_cust.name == "Acme Corp"

    # 2. Create subscription
    start_dt = datetime.now(timezone.utc)
    end_dt = start_dt + timedelta(days=30)
    sub = await mgr.create_subscription(
        subscription_id="sub-acme-pro",
        tenant_id="tenant-saas",
        customer_id="cust-acme-1",
        plan_id="plan-pro-tiered",
        current_period_start=start_dt,
        current_period_end=end_dt
    )
    assert sub.subscription_id == "sub-acme-pro"
    assert sub.status == "ACTIVE"

    # Query subscription
    fetched_sub = await mgr.get_subscription("sub-acme-pro")
    assert fetched_sub is not None
    assert fetched_sub.plan_id == "plan-pro-tiered"
