import pytest
from rating.engine import RatingEngine, PriceBookEntry, PricingType

def test_BIL_043_flat_subscription_pricing():
    """
    BIL-043: Flat subscription pricing.
    Validates fixed recurring base charge independent of metered consumption.
    """
    entry = PriceBookEntry(
        id="entry-base-fee",
        tenant_id="tenant-x",
        plan_id="plan-pro-flat",
        event_type="subscription.base_fee",
        pricing_type=PricingType.FLAT_FEE,
        flat_fee_cents=4900  # $49.00 / month flat fee
    )

    # Regardless of event quantity passed (0, 10, 1000), flat fee remains 4900 cents
    line1 = RatingEngine.rate_usage(entry, quantity=0)
    assert line1.total_cents == 4900

    line2 = RatingEngine.rate_usage(entry, quantity=100)
    assert line2.total_cents == 4900
