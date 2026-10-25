import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from models.accounts import AccountManager, SubscriptionLifecycleManager, SubscriptionStatus

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
async def test_BIL_017_subscription_model(async_session):
    """
    BIL-017: Subscription model.
    Tests subscription creation, lifecycle status transitions (TRIALING -> ACTIVE -> PAUSED -> RESUMED),
    and end-of-period or immediate cancellation.
    """
    acct_mgr = AccountManager(async_session)
    sub_mgr = SubscriptionLifecycleManager(async_session)

    # Pre-requisite: Customer account
    cust = await acct_mgr.create_customer(
        customer_id="cust-sub-test",
        tenant_id="tenant-saas",
        name="Alpha Devs",
        email="devs@alpha.test"
    )

    now = datetime.now(timezone.utc)
    period_start = now
    period_end = now + timedelta(days=30)

    # 1. Create subscription in TRIALING status
    sub = await sub_mgr.create_subscription(
        subscription_id="sub-alpha-001",
        tenant_id="tenant-saas",
        customer_id="cust-sub-test",
        plan_id="plan-starter",
        current_period_start=period_start,
        current_period_end=period_end,
        status=SubscriptionStatus.TRIALING.value
    )
    assert sub.subscription_id == "sub-alpha-001"
    assert sub.status == SubscriptionStatus.TRIALING.value
    assert sub.cancel_at_period_end is False

    # 2. Transition from TRIALING to ACTIVE
    activated = await sub_mgr.transition_status("sub-alpha-001", SubscriptionStatus.ACTIVE.value)
    assert activated.status == SubscriptionStatus.ACTIVE.value

    # 3. Pause and Resume
    paused = await sub_mgr.pause_subscription("sub-alpha-001")
    assert paused.status == SubscriptionStatus.PAUSED.value

    resumed = await sub_mgr.resume_subscription("sub-alpha-001")
    assert resumed.status == SubscriptionStatus.ACTIVE.value

    # 4. Cancel at period end
    scheduled_cancel = await sub_mgr.cancel_subscription("sub-alpha-001", immediate=False)
    assert scheduled_cancel.status == SubscriptionStatus.ACTIVE.value
    assert scheduled_cancel.cancel_at_period_end is True

    # 5. Immediate cancellation
    immediate_cancel = await sub_mgr.cancel_subscription("sub-alpha-001", immediate=True)
    assert immediate_cancel.status == SubscriptionStatus.CANCELED.value
    assert immediate_cancel.canceled_at is not None
