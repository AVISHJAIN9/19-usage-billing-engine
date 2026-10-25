"""
Subscription Proration and Mid-Cycle Change Engine (BIL-018, BIL-020, BIL-021).
Calculates exact pro-rata adjustments to the minor unit (cents) for upgrades, downgrades,
cancellations, pauses, resumes, and trials.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_HALF_UP

@dataclass
class ProrationResult:
    old_plan_price_cents: int
    new_plan_price_cents: int
    total_period_seconds: float
    remaining_seconds: float
    fraction_remaining: float
    unused_credit_cents: int
    new_charge_cents: int
    net_proration_cents: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def calculate_proration(
    old_plan_price_cents: int,
    new_plan_price_cents: int,
    period_start: datetime,
    period_end: datetime,
    effective_time: datetime
) -> ProrationResult:
    """
    Computes pro-rata credit for unused portion of old plan and charge for remaining portion of new plan.
    Computed to the minor unit (cents) with standard financial rounding (HALF_UP).
    """
    period_start = _to_utc(period_start)
    period_end = _to_utc(period_end)
    effective_time = _to_utc(effective_time)

    if effective_time < period_start:
        effective_time = period_start
    if effective_time > period_end:
        effective_time = period_end

    total_seconds = Decimal(str((period_end - period_start).total_seconds()))
    if total_seconds <= 0:
        raise ValueError("period_end must be strictly greater than period_start")

    remaining_seconds = Decimal(str((period_end - effective_time).total_seconds()))
    fraction = remaining_seconds / total_seconds

    # Calculate unused credit from previous plan
    unused_credit = (Decimal(old_plan_price_cents) * fraction).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    # Calculate new plan charge for remaining period
    new_charge = (Decimal(new_plan_price_cents) * fraction).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    unused_credit_cents = int(unused_credit)
    new_charge_cents = int(new_charge)
    net_cents = new_charge_cents - unused_credit_cents

    return ProrationResult(
        old_plan_price_cents=old_plan_price_cents,
        new_plan_price_cents=new_plan_price_cents,
        total_period_seconds=float(total_seconds),
        remaining_seconds=float(remaining_seconds),
        fraction_remaining=float(fraction),
        unused_credit_cents=unused_credit_cents,
        new_charge_cents=new_charge_cents,
        net_proration_cents=net_cents
    )
