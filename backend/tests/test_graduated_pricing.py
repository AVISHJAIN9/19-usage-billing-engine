import pytest
from rating.engine import RatingEngine, PriceBookEntry, PriceTier, PricingType

def test_BIL_046_graduated_pricing():
    """
    BIL-046: Graduated pricing (Bracket / Slab-based).
    Units are charged bracket by bracket:
      0-100 units   : 10 cents/unit
      101-500 units : 8 cents/unit
      501+ units    : 5 cents/unit
    """
    entry = PriceBookEntry(
        id="entry-graduated",
        tenant_id="tenant-x",
        plan_id="plan-grad",
        event_type="compute.hours",
        pricing_type=PricingType.GRADUATED_BRACKET,
        tiers=[
            PriceTier(up_to=100, unit_price_cents=10),
            PriceTier(up_to=500, unit_price_cents=8),
            PriceTier(up_to=None, unit_price_cents=5)
        ]
    )

    # 1. 50 units -> 50 in first bracket (10c) = 500 cents
    line1 = RatingEngine.rate_usage(entry, quantity=50)
    assert line1.total_cents == 500

    # 2. 200 units -> 100 * 10c (1000c) + 100 * 8c (800c) = 1800 cents
    line2 = RatingEngine.rate_usage(entry, quantity=200)
    assert line2.total_cents == 1800

    # 3. 600 units -> 100 * 10c (1000c) + 400 * 8c (3200c) + 100 * 5c (500c) = 4700 cents
    line3 = RatingEngine.rate_usage(entry, quantity=600)
    assert line3.total_cents == 4700
