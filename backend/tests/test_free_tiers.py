import pytest
from rating.engine import RatingEngine, PriceBookEntry, PricingType

def test_BIL_050_free_tiers():
    """
    BIL-050: Free tiers.
    Validates that free unit allowance is deducted from total quantity prior to rating.
    Free tier: 100 free units.
    Rate above free tier: 5 cents/unit.
    """
    entry = PriceBookEntry(
        id="entry-free-tier",
        tenant_id="tenant-x",
        plan_id="plan-dev",
        event_type="api.calls",
        pricing_type=PricingType.PER_UNIT,
        free_units=100,
        unit_price_cents=5
    )

    # 1. 80 units used: all free, 0 billable, 0 cents
    line1 = RatingEngine.rate_usage(entry, quantity=80)
    assert line1.free_units_applied == 80
    assert line1.billable_quantity == 0
    assert line1.total_cents == 0

    # 2. 100 units used: exactly free tier, 0 cents
    line2 = RatingEngine.rate_usage(entry, quantity=100)
    assert line2.free_units_applied == 100
    assert line2.billable_quantity == 0
    assert line2.total_cents == 0

    # 3. 150 units used: 100 free, 50 billable * 5 = 250 cents
    line3 = RatingEngine.rate_usage(entry, quantity=150)
    assert line3.free_units_applied == 100
    assert line3.billable_quantity == 50
    assert line3.total_cents == 250
