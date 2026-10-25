import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from models.accounts import (
    AccountManager, SubscriptionLifecycleManager, PlanAssignmentManager,
    SubscriptionStatus
)
from models.proration import calculate_proration

@pytest_asyncio.fixture
async def sub_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        yield session
    await engine.dispose()

@pytest.mark.asyncio
async def test_BIL_018_subscription_lifecycle(sub_session):
    """
    BIL-018: Complete subscription lifecycle state machine transitions.
    Tests ACTIVE -> PAUSED -> ACTIVE -> CANCELED.
    """
    acct_mgr = AccountManager(sub_session)
    sub_mgr = SubscriptionLifecycleManager(sub_session)

    # 1. Create customer
    cust = await acct_mgr.create_customer(
        customer_id="cust-life-1",
        tenant_id="tenant-life-1",
        name="Lifecycle Corp",
        email="billing@lifecycle.com"
    )

    t_start = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    t_end = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)

    # 2. Create active subscription
    sub = await sub_mgr.create_subscription(
        subscription_id="sub-life-1",
        tenant_id="tenant-life-1",
        customer_id="cust-life-1",
        plan_id="plan-standard",
        current_period_start=t_start,
        current_period_end=t_end,
        status=SubscriptionStatus.ACTIVE.value
    )
    assert sub.status == SubscriptionStatus.ACTIVE.value

    # 3. Pause subscription
    paused = await sub_mgr.pause_subscription("sub-life-1")
    assert paused.status == SubscriptionStatus.PAUSED.value

    # 4. Resume subscription
    resumed = await sub_mgr.resume_subscription("sub-life-1")
    assert resumed.status == SubscriptionStatus.ACTIVE.value

    # 5. Cancel subscription at period end
    canceled_sched = await sub_mgr.cancel_subscription("sub-life-1", immediate=False)
    assert canceled_sched.cancel_at_period_end is True

    # 6. Immediate cancel
    canceled_now = await sub_mgr.cancel_subscription("sub-life-1", immediate=True)
    assert canceled_now.status == SubscriptionStatus.CANCELED.value
    assert canceled_now.canceled_at is not None

@pytest.mark.asyncio
async def test_BIL_020_plan_upgrades_with_hand_computed_proration(sub_session):
    """
    BIL-020: Mid-cycle plan upgrade with hand-computed proration verification.
    Golden hand calculation:
      Period: 2026-10-01 00:00:00 to 2026-10-31 00:00:00 (30 days = 2,592,000s).
      Effective upgrade: 2026-10-11 00:00:00 (10 days elapsed, 20 days remaining = 2/3).
      Old Starter plan: $30.00 = 3000 cents.
      New Enterprise plan: $90.00 = 9000 cents.
      HAND-COMPUTED EXPECTED VALUES:
        Unused credit = 3000 * (2/3) = 2000 cents.
        New charge    = 9000 * (2/3) = 6000 cents.
        Net charge    = 6000 - 2000  = 4000 cents ($40.00).
    """
    acct_mgr = AccountManager(sub_session)
    sub_mgr = SubscriptionLifecycleManager(sub_session)

    await acct_mgr.create_customer("cust-upg-1", "tenant-upg-1", "Upgrade Buyer", "upg@test.com")

    period_start = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    period_end = datetime(2026, 10, 31, 0, 0, tzinfo=timezone.utc)
    effective_upgrade = datetime(2026, 10, 11, 0, 0, tzinfo=timezone.utc)

    sub = await sub_mgr.create_subscription(
        subscription_id="sub-upg-1",
        tenant_id="tenant-upg-1",
        customer_id="cust-upg-1",
        plan_id="plan-starter-3000",
        current_period_start=period_start,
        current_period_end=period_end
    )

    # Execute upgrade
    updated_sub, proration = await sub_mgr.upgrade_subscription(
        subscription_id="sub-upg-1",
        new_plan_id="plan-enterprise-9000",
        new_plan_price_cents=9000,
        old_plan_price_cents=3000,
        effective_time=effective_upgrade
    )

    assert updated_sub.plan_id == "plan-enterprise-9000"

    # STRICT ASSERTIONS AGAINST INDEPENDENT HAND-COMPUTED GOLDEN VALUES
    HAND_COMPUTED_UNUSED_CREDIT = 2000
    HAND_COMPUTED_NEW_CHARGE = 6000
    HAND_COMPUTED_NET_CHARGE = 4000

    assert proration.unused_credit_cents == HAND_COMPUTED_UNUSED_CREDIT, (
        f"Expected unused credit {HAND_COMPUTED_UNUSED_CREDIT}, got {proration.unused_credit_cents}"
    )
    assert proration.new_charge_cents == HAND_COMPUTED_NEW_CHARGE, (
        f"Expected new charge {HAND_COMPUTED_NEW_CHARGE}, got {proration.new_charge_cents}"
    )
    assert proration.net_proration_cents == HAND_COMPUTED_NET_CHARGE, (
        f"Expected net charge {HAND_COMPUTED_NET_CHARGE}, got {proration.net_proration_cents}"
    )

@pytest.mark.asyncio
async def test_BIL_021_plan_downgrades_with_hand_computed_credit(sub_session):
    """
    BIL-021: Mid-cycle plan downgrade with hand-computed credit verification.
    Golden hand calculation:
      Period: 2026-10-01 00:00:00 to 2026-10-31 00:00:00 (30 days = 2,592,000s).
      Effective downgrade: 2026-10-16 00:00:00 (15 days elapsed, 15 days remaining = 1/2 = 0.5).
      Old Enterprise plan: $90.00 = 9000 cents.
      New Starter plan:    $30.00 = 3000 cents.
      HAND-COMPUTED EXPECTED VALUES:
        Unused credit = 9000 * 0.5 = 4500 cents.
        New charge    = 3000 * 0.5 = 1500 cents.
        Net charge    = 1500 - 4500 = -3000 cents ($30.00 credit to customer).
    """
    acct_mgr = AccountManager(sub_session)
    sub_mgr = SubscriptionLifecycleManager(sub_session)

    await acct_mgr.create_customer("cust-dwn-1", "tenant-dwn-1", "Downgrade Buyer", "dwn@test.com")

    period_start = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    period_end = datetime(2026, 10, 31, 0, 0, tzinfo=timezone.utc)
    effective_downgrade = datetime(2026, 10, 16, 0, 0, tzinfo=timezone.utc)

    sub = await sub_mgr.create_subscription(
        subscription_id="sub-dwn-1",
        tenant_id="tenant-dwn-1",
        customer_id="cust-dwn-1",
        plan_id="plan-enterprise-9000",
        current_period_start=period_start,
        current_period_end=period_end
    )

    # Execute immediate downgrade
    updated_sub, proration = await sub_mgr.downgrade_subscription(
        subscription_id="sub-dwn-1",
        new_plan_id="plan-starter-3000",
        new_plan_price_cents=3000,
        old_plan_price_cents=9000,
        effective_time=effective_downgrade,
        immediate=True
    )

    assert updated_sub.plan_id == "plan-starter-3000"

    # STRICT ASSERTIONS AGAINST INDEPENDENT HAND-COMPUTED GOLDEN VALUES
    HAND_COMPUTED_UNUSED_CREDIT = 4500
    HAND_COMPUTED_NEW_CHARGE = 1500
    HAND_COMPUTED_NET_CREDIT = -3000

    assert proration.unused_credit_cents == HAND_COMPUTED_UNUSED_CREDIT
    assert proration.new_charge_cents == HAND_COMPUTED_NEW_CHARGE
    assert proration.net_proration_cents == HAND_COMPUTED_NET_CREDIT

@pytest.mark.asyncio
async def test_BIL_022_plan_cancellation_with_hand_computed_credit(sub_session):
    """
    BIL-022: Immediate plan cancellation with hand-computed credit verification.
    Golden hand calculation:
      Period: 2026-10-01 00:00:00 to 2026-10-31 00:00:00 (30 days = 2,592,000s).
      Cancellation time: 2026-10-21 00:00:00 (20 days elapsed, 10 days remaining = 1/3).
      Plan price: $60.00 = 6000 cents.
      HAND-COMPUTED EXPECTED VALUES:
        Unused credit = 6000 * (1/3) = 2000 cents.
        New charge    = 0 cents.
        Net credit    = -2000 cents ($20.00 credit to customer).
    """
    acct_mgr = AccountManager(sub_session)
    sub_mgr = SubscriptionLifecycleManager(sub_session)

    await acct_mgr.create_customer("cust-cnl-1", "tenant-cnl-1", "Cancel Buyer", "cnl@test.com")

    period_start = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    period_end = datetime(2026, 10, 31, 0, 0, tzinfo=timezone.utc)
    effective_cancel = datetime(2026, 10, 21, 0, 0, tzinfo=timezone.utc)

    sub = await sub_mgr.create_subscription(
        subscription_id="sub-cnl-1",
        tenant_id="tenant-cnl-1",
        customer_id="cust-cnl-1",
        plan_id="plan-pro-6000",
        current_period_start=period_start,
        current_period_end=period_end
    )

    canceled_sub, proration = await sub_mgr.cancel_with_proration(
        subscription_id="sub-cnl-1",
        plan_price_cents=6000,
        effective_time=effective_cancel
    )

    assert canceled_sub.status == SubscriptionStatus.CANCELED.value

    # STRICT ASSERTIONS AGAINST INDEPENDENT HAND-COMPUTED GOLDEN VALUES
    HAND_COMPUTED_CREDIT = 2000
    assert proration.unused_credit_cents == HAND_COMPUTED_CREDIT
    assert proration.new_charge_cents == 0
    assert proration.net_proration_cents == -HAND_COMPUTED_CREDIT

@pytest.mark.asyncio
async def test_BIL_023_plan_pause_and_resume_period_extension(sub_session):
    """
    BIL-023: Plan pause/resume with exact billing period extension.
    Hand calculation:
      Period: 2026-10-01 00:00:00 to 2026-11-01 00:00:00.
      Paused at: 2026-10-10 12:00:00.
      Resumed at: 2026-10-15 12:00:00 (paused for exactly 5 days = 432,000s).
      HAND-COMPUTED EXPECTED NEW PERIOD END:
        2026-11-01 00:00:00 + 5 days = 2026-11-06 00:00:00!
    """
    acct_mgr = AccountManager(sub_session)
    sub_mgr = SubscriptionLifecycleManager(sub_session)

    await acct_mgr.create_customer("cust-pau-1", "tenant-pau-1", "Pause Buyer", "pau@test.com")

    t_start = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    t_end = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)
    t_pause = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    t_resume = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)

    sub = await sub_mgr.create_subscription(
        subscription_id="sub-pau-1",
        tenant_id="tenant-pau-1",
        customer_id="cust-pau-1",
        plan_id="plan-standard",
        current_period_start=t_start,
        current_period_end=t_end
    )

    # 1. Pause
    paused = await sub_mgr.pause_subscription("sub-pau-1", effective_time=t_pause)
    assert paused.status == SubscriptionStatus.PAUSED.value

    # 2. Resume
    resumed = await sub_mgr.resume_subscription("sub-pau-1", effective_time=t_resume)
    assert resumed.status == SubscriptionStatus.ACTIVE.value

    # STRICT ASSERTION: Period end extended by exactly 5 days
    HAND_COMPUTED_EXTENDED_END = datetime(2026, 11, 6, 0, 0, tzinfo=timezone.utc)
    resumed_end = resumed.current_period_end if resumed.current_period_end.tzinfo else resumed.current_period_end.replace(tzinfo=timezone.utc)
    assert resumed_end == HAND_COMPUTED_EXTENDED_END

@pytest.mark.asyncio
async def test_BIL_024_trial_periods(sub_session):
    """
    BIL-024: Free trial lifecycle management.
    Tests start in TRIALING status and automatic/explicit conversion to ACTIVE with regular billing cycle.
    """
    acct_mgr = AccountManager(sub_session)
    sub_mgr = SubscriptionLifecycleManager(sub_session)

    await acct_mgr.create_customer("cust-tri-1", "tenant-tri-1", "Trial Buyer", "tri@test.com")

    trial_start = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    trial_end = datetime(2026, 10, 15, 0, 0, tzinfo=timezone.utc)

    # 1. Start trial
    trial_sub = await sub_mgr.start_trial(
        subscription_id="sub-tri-1",
        tenant_id="tenant-tri-1",
        customer_id="cust-tri-1",
        plan_id="plan-pro",
        trial_start=trial_start,
        trial_end=trial_end
    )
    assert trial_sub.status == SubscriptionStatus.TRIALING.value
    assert trial_sub.current_period_start.replace(tzinfo=timezone.utc) == trial_start
    assert trial_sub.current_period_end.replace(tzinfo=timezone.utc) == trial_end

    # 2. Convert trial to active paid subscription
    cycle_start = trial_end
    cycle_end = cycle_start + timedelta(days=30)
    active_sub = await sub_mgr.convert_trial_to_active(
        subscription_id="sub-tri-1",
        new_period_start=cycle_start,
        new_period_end=cycle_end
    )
    assert active_sub.status == SubscriptionStatus.ACTIVE.value
    assert active_sub.current_period_start.replace(tzinfo=timezone.utc) == cycle_start
    assert active_sub.current_period_end.replace(tzinfo=timezone.utc) == cycle_end

