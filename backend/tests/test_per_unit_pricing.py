import pytest
from rating.engine import RatingEngine, PriceBookEntry, PricingType

def test_BIL_047_per_unit_pricing():
    """
    BIL-047: Per-unit pricing.
    Validates linear per-unit cost calculation: total = quantity * unit_price_cents + flat_fee.
    """
    entry = PriceBookEntry(
        id="entry-per-unit",
        tenant_id="tenant-x",
        plan_id="plan-linear",
        event_type="sms.sent",
        pricing_type=PricingType.PER_UNIT,
        unit_price_cents=4,
        flat_fee_cents=100
    )

    # 1. 0 SMS sent: flat fee 100 cents
    line1 = RatingEngine.rate_usage(entry, quantity=0)
    assert line1.billable_quantity == 0
    assert line1.subtotal_cents == 0
    assert line1.total_cents == 100

    # 2. 50 SMS sent: 50 * 4 = 200 subtotal + 100 flat = 300 cents
    line2 = RatingEngine.rate_usage(entry, quantity=50)
    assert line2.billable_quantity == 50
    assert line2.subtotal_cents == 200
    assert line2.total_cents == 300
