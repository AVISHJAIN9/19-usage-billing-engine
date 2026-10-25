"""
Tests for Billing & Rating:
- BIL-040: Plan versioning (immutable versioning, locking)
- BIL-045: Volume pricing (hand-computed golden tables)
- BIL-048: Minimum charges (floor clamping)
- BIL-049: Maximum charges (ceiling clamping)
- BIL-051: Overage pricing (included units + overage rate)
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from db.database import Base
from models.plan_versions import PlanVersionRecord, PlanVersionManager
from rating.engine import RatingEngine, PriceBookEntry, PriceTier, PricingType, PriceBookManager


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
async def test_BIL_040_plan_versioning_and_immutability(async_session: AsyncSession):
    manager = PlanVersionManager(async_session)

    # 1. Create initial version (v1)
    v1 = await manager.create_plan_version(
        tenant_id="tenant-100",
        plan_id="pro-plan",
        name="Pro Plan v1",
        base_fee_cents=4900,
        min_charge_cents=1000
    )
    assert v1.version == 1
    assert v1.is_locked is False

    # 2. Update unlocked v1 attributes
    updated_v1 = await manager.update_version(
        tenant_id="tenant-100",
        plan_id="pro-plan",
        version=1,
        name="Pro Plan v1 Revised",
        base_fee_cents=5500
    )
    assert updated_v1.name == "Pro Plan v1 Revised"
    assert updated_v1.base_fee_cents == 5500

    # 3. Lock version (e.g. finalized invoice references it)
    locked_v1 = await manager.lock_version("tenant-100", "pro-plan", version=1)
    assert locked_v1.is_locked is True

    # 4. Attempt to mutate locked version must raise ValueError
    with pytest.raises(ValueError, match="is locked and cannot be modified"):
        await manager.update_version(
            tenant_id="tenant-100",
            plan_id="pro-plan",
            version=1,
            base_fee_cents=6000
        )

    # 5. Create new version (v2) increments version automatically
    v2 = await manager.create_plan_version(
        tenant_id="tenant-100",
        plan_id="pro-plan",
        name="Pro Plan v2",
        base_fee_cents=6000
    )
    assert v2.version == 2
    assert v2.is_locked is False
    assert v2.base_fee_cents == 6000


def test_BIL_045_volume_pricing_hand_computed_table():
    """
    Tiered Volume Pricing:
    All billable units are charged at the single unit rate of the reached tier.
    Hand-computed golden table:
      Tier 1: 1 - 100 units   @ 20 cents/unit, 0 flat
      Tier 2: 101 - 500 units @ 15 cents/unit, 0 flat
      Tier 3: 501+ units      @ 10 cents/unit, 0 flat
      Base flat fee on entry = 500 cents

    Test cases:
      - 50 units  -> Tier 1: 50 * 20 = 1000 + 500 flat = 1500 cents
      - 100 units -> Tier 1: 100 * 20 = 2000 + 500 flat = 2500 cents
      - 250 units -> Tier 2: 250 * 15 = 3750 + 500 flat = 4250 cents
      - 500 units -> Tier 2: 500 * 15 = 7500 + 500 flat = 8000 cents
      - 1000 units -> Tier 3: 1000 * 10 = 10000 + 500 flat = 10500 cents
    """
    entry = PriceBookEntry(
        id="pbe-vol-1",
        tenant_id="tenant-100",
        plan_id="plan-vol",
        event_type="api_call",
        pricing_type=PricingType.TIERED_VOLUME,
        flat_fee_cents=500,
        tiers=[
            PriceTier(up_to=100, unit_price_cents=20),
            PriceTier(up_to=500, unit_price_cents=15),
            PriceTier(up_to=None, unit_price_cents=10),
        ]
    )

    cases = [
        (50, 1500, 1000),
        (100, 2500, 2000),
        (250, 4250, 3750),
        (500, 8000, 7500),
        (1000, 10500, 10000),
    ]

    for qty, expected_total, expected_subtotal in cases:
        item = RatingEngine.rate_usage(entry, qty)
        assert item.total_cents == expected_total, f"Qty {qty}: expected {expected_total}, got {item.total_cents}"
        assert item.subtotal_cents == expected_subtotal


def test_BIL_048_minimum_charges_enforcement():
    """
    Minimum charge enforces a floor: total_cents cannot be lower than min_charge_cents.
    Hand-computed test:
      Per-unit pricing: 5 cents/unit, 0 flat fee.
      min_charge_cents = 2500 cents ($25.00)

      - 100 units  -> 500 cents raw. Clamped to floor: 2500 cents. min_charge_applied = True
      - 400 units  -> 2000 cents raw. Clamped to floor: 2500 cents. min_charge_applied = True
      - 500 units  -> 2500 cents raw. Exactly min: 2500 cents. min_charge_applied = False
      - 1000 units -> 5000 cents raw. Above min: 5000 cents. min_charge_applied = False
    """
    entry = PriceBookEntry(
        id="pbe-min-1",
        tenant_id="tenant-100",
        plan_id="plan-min",
        event_type="compute_sec",
        pricing_type=PricingType.PER_UNIT,
        unit_price_cents=5,
        min_charge_cents=2500
    )

    r100 = RatingEngine.rate_usage(entry, 100)
    assert r100.total_cents == 2500
    assert r100.min_charge_applied is True

    r400 = RatingEngine.rate_usage(entry, 400)
    assert r400.total_cents == 2500
    assert r400.min_charge_applied is True

    r500 = RatingEngine.rate_usage(entry, 500)
    assert r500.total_cents == 2500
    assert r500.min_charge_applied is False

    r1000 = RatingEngine.rate_usage(entry, 1000)
    assert r1000.total_cents == 5000
    assert r1000.min_charge_applied is False


def test_BIL_049_maximum_charges_enforcement():
    """
    Maximum charge enforces a ceiling: total_cents cannot exceed max_charge_cents.
    Hand-computed test:
      Per-unit pricing: 10 cents/unit, flat fee 1000 cents.
      max_charge_cents = 5000 cents ($50.00 cap)

      - 100 units -> 1000 + 1000 = 2000 cents (below cap, max_applied = False)
      - 400 units -> 1000 + 4000 = 5000 cents (at cap, max_applied = False)
      - 600 units -> 1000 + 6000 = 7000 cents -> clamped to 5000 cents (max_applied = True)
    """
    entry = PriceBookEntry(
        id="pbe-max-1",
        tenant_id="tenant-100",
        plan_id="plan-max",
        event_type="storage_gb",
        pricing_type=PricingType.PER_UNIT,
        flat_fee_cents=1000,
        unit_price_cents=10,
        max_charge_cents=5000
    )

    r100 = RatingEngine.rate_usage(entry, 100)
    assert r100.total_cents == 2000
    assert r100.max_charge_applied is False

    r400 = RatingEngine.rate_usage(entry, 400)
    assert r400.total_cents == 5000
    assert r400.max_charge_applied is False

    r600 = RatingEngine.rate_usage(entry, 600)
    assert r600.total_cents == 5000
    assert r600.max_charge_applied is True


def test_BIL_051_overage_pricing_hand_computed_table():
    """
    Overage Pricing:
    Base subscription includes N units. Any usage beyond N is billed at overage_unit_price_cents.
    Hand-computed golden table:
      Base fee: 3000 cents ($30.00)
      Included units: 1000
      Overage unit price: 4 cents/unit

      - 500 units  -> overage = 0, subtotal = 0, total = 3000 cents
      - 1000 units -> overage = 0, subtotal = 0, total = 3000 cents
      - 1250 units -> overage = 250 units * 4c = 1000c, total = 3000 + 1000 = 4000 cents
      - 2000 units -> overage = 1000 units * 4c = 4000c, total = 3000 + 4000 = 7000 cents
    """
    entry = PriceBookEntry(
        id="pbe-ovg-1",
        tenant_id="tenant-100",
        plan_id="plan-ovg",
        event_type="bandwidth_gb",
        pricing_type=PricingType.OVERAGE,
        flat_fee_cents=3000,
        included_units=1000,
        overage_unit_price_cents=4
    )

    cases = [
        (500, 3000, 0),
        (1000, 3000, 0),
        (1250, 4000, 1000),
        (2000, 7000, 4000),
    ]

    for qty, expected_total, expected_subtotal in cases:
        item = RatingEngine.rate_usage(entry, qty)
        assert item.total_cents == expected_total
        assert item.subtotal_cents == expected_subtotal
