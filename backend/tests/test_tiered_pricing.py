import pytest
from rating.engine import RatingEngine, PriceBookEntry, PriceTier, PricingType

def test_BIL_044_tiered_pricing():
    """
    BIL-044: Tiered pricing (Volume-based).
    Once volume crosses a tier threshold, all units are billed at that tier's unit rate.
    Tiers:
      1-100 units   : 10 cents/unit
      101-500 units : 8 cents/unit
      501+ units    : 5 cents/unit
    """
    entry = PriceBookEntry(
        id="entry-volume-tier",
        tenant_id="tenant-x",
        plan_id="plan-vol",
        event_type="api.calls",
        pricing_type=PricingType.TIERED_VOLUME,
        tiers=[
            PriceTier(up_to=100, unit_price_cents=10),
            PriceTier(up_to=500, unit_price_cents=8),
            PriceTier(up_to=None, unit_price_cents=5)
        ]
    )

    # 1. Volume 50 units -> Tier 1 (10 cents): 50 * 10 = 500 cents
    line1 = RatingEngine.rate_usage(entry, quantity=50)
    assert line1.total_cents == 500

    # 2. Volume 200 units -> Tier 2 (8 cents): 200 * 8 = 1600 cents
    line2 = RatingEngine.rate_usage(entry, quantity=200)
    assert line2.total_cents == 1600

    # 3. Volume 1,000 units -> Tier 3 (5 cents): 1000 * 5 = 5000 cents
    line3 = RatingEngine.rate_usage(entry, quantity=1000)
    assert line3.total_cents == 5000
