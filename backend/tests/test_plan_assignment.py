import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from models.accounts import AccountManager, SubscriptionLifecycleManager, PlanAssignmentManager

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
async def test_BIL_019_plan_assignment(async_session):
    """
    BIL-019: Plan assignment.
    Tests plan creation, assigning a plan to a subscription, upgrading/downgrading,
    and querying plan assignment history with effective date ranges.
    """
    acct_mgr = AccountManager(async_session)
    sub_mgr = SubscriptionLifecycleManager(async_session)
    plan_mgr = PlanAssignmentManager(async_session)

    # 1. Create Plans
    starter = await plan_mgr.create_plan(
        plan_id="plan-standard",
        tenant_id="tenant-saas",
        name="Standard Plan",
        description="Standard features up to 10k events",
        currency="USD_CENTS"
    )
    enterprise = await plan_mgr.create_plan(
        plan_id="plan-enterprise",
        tenant_id="tenant-saas",
        name="Enterprise Plan",
        description="Unlimited events with premium SLA",
        currency="USD_CENTS"
    )
    assert starter.plan_id == "plan-standard"
    assert enterprise.plan_id == "plan-enterprise"

    # 2. Create customer & subscription
    now = datetime.now(timezone.utc)
    cust = await acct_mgr.create_customer(
        customer_id="cust-co-1",
        tenant_id="tenant-saas",
        name="Company One",
        email="ops@companyone.com"
    )
    sub = await sub_mgr.create_subscription(
        subscription_id="sub-co-1",
        tenant_id="tenant-saas",
        customer_id="cust-co-1",
        plan_id="plan-standard",
        current_period_start=now,
        current_period_end=now + timedelta(days=30)
    )

    # 3. Initial assignment
    assign1 = await plan_mgr.assign_plan_to_subscription(
        assignment_id="assign-1",
        subscription_id="sub-co-1",
        tenant_id="tenant-saas",
        plan_id="plan-standard",
        effective_from=now
    )
    assert assign1.plan_id == "plan-standard"
    assert assign1.effective_to is None

    # 4. Upgrade plan to enterprise
    upgrade_time = now + timedelta(days=10)
    assign2 = await plan_mgr.assign_plan_to_subscription(
        assignment_id="assign-2",
        subscription_id="sub-co-1",
        tenant_id="tenant-saas",
        plan_id="plan-enterprise",
        effective_from=upgrade_time
    )
    assert assign2.plan_id == "plan-enterprise"
    assert assign2.effective_to is None

    # Check updated subscription
    updated_sub = await sub_mgr.get_subscription("sub-co-1")
    assert updated_sub.plan_id == "plan-enterprise"

    # 5. Verify assignment history
    history = await plan_mgr.get_subscription_plan_history("sub-co-1")
    assert len(history) == 2
    assert history[0].plan_id == "plan-standard"
    assert history[0].effective_to == upgrade_time
    assert history[1].plan_id == "plan-enterprise"
    assert history[1].effective_to is None
