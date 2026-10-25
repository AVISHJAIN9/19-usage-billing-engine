import pytest
from rating.engine import RatingEngine, PriceBookEntry, PricingType

def test_BIL_042_metered_pricing():
    """
    BIL-042: Metered pricing.
    Validates end-to-end metered rating of variable resource consumption based on tracked volume.
    """
    entry = PriceBookEntry(
        id="entry-metered",
        tenant_id="tenant-x",
        plan_id="plan-metered",
        event_type="compute.seconds",
        pricing_type=PricingType.PER_UNIT,
        unit_price_cents=3  # 3 cents per compute second
    )

    # 1. 100 seconds => 100 * 3 = 300 cents
    line1 = RatingEngine.rate_usage(entry, quantity=100)
    assert line1.billable_quantity == 100
    assert line1.total_cents == 300

    # 2. 0 seconds => 0 cents
    line2 = RatingEngine.rate_usage(entry, quantity=0)
    assert line2.billable_quantity == 0
    assert line2.total_cents == 0

    # 3. 12,500 seconds => 37,500 cents
    line3 = RatingEngine.rate_usage(entry, quantity=12500)
    assert line3.total_cents == 37500
