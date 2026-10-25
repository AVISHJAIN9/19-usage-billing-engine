"""
Billing & Rating Engine (BIL-039, BIL-041, BIL-042, BIL-043, BIL-044, BIL-046, BIL-047, BIL-050).
Enforces financial integrity:
- All charges calculated in exact integer cents.
- Models: Flat subscription fees, Per-unit metered pricing, Tiered (volume) pricing,
  Graduated (bracket/slab) pricing, Free tier allowances, and Price Books.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import json
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, String, BigInteger, DateTime, ForeignKey, Text, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import Base


class PricingType(str, Enum):
    FLAT_FEE = "FLAT_FEE"
    PER_UNIT = "PER_UNIT"
    TIERED_VOLUME = "TIERED_VOLUME"        # All units charged at rate of achieved tier
    GRADUATED_BRACKET = "GRADUATED_BRACKET"  # Units charged bracket by bracket
    OVERAGE = "OVERAGE"                      # Included units + overage unit rate


class PriceBookEntryRecord(Base):
    __tablename__ = "price_book_entries"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    plan_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    pricing_type = Column(String(32), nullable=False)
    flat_fee_cents = Column(BigInteger, default=0, nullable=False)
    free_units = Column(BigInteger, default=0, nullable=False)
    unit_price_cents = Column(BigInteger, default=0, nullable=False)
    min_charge_cents = Column(BigInteger, default=0, nullable=False)
    max_charge_cents = Column(BigInteger, nullable=True)
    included_units = Column(BigInteger, default=0, nullable=False)
    overage_unit_price_cents = Column(BigInteger, default=0, nullable=False)
    tiers_json = Column(Text, default="[]", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class PriceTier(BaseModel):
    up_to: Optional[int] = None  # None indicates infinity/unbounded
    unit_price_cents: int
    flat_fee_cents: int = 0


class PriceBookEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    plan_id: str
    event_type: str
    pricing_type: PricingType
    flat_fee_cents: int = 0
    free_units: int = 0
    unit_price_cents: int = 0
    min_charge_cents: int = 0
    max_charge_cents: Optional[int] = None
    included_units: int = 0
    overage_unit_price_cents: int = 0
    tiers: List[PriceTier] = Field(default_factory=list)


class RatingLineItem(BaseModel):
    event_type: str
    pricing_type: PricingType
    total_quantity: int
    free_units_applied: int
    billable_quantity: int
    subtotal_cents: int
    flat_fee_cents: int
    total_cents: int
    min_charge_applied: bool = False
    max_charge_applied: bool = False
    explanation: str


class RatingEngine:
    @staticmethod
    def rate_usage(entry: PriceBookEntry, quantity: int) -> RatingLineItem:
        """
        Calculates exact integer cents for given usage quantity according to pricing model.
        """
        if quantity < 0:
            raise ValueError("Usage quantity cannot be negative")

        flat_fee = entry.flat_fee_cents
        free_applied = min(quantity, entry.free_units)
        billable_qty = max(0, quantity - entry.free_units)

        if entry.pricing_type == PricingType.FLAT_FEE:
            subtotal = 0
            total_cents = flat_fee
            expl = f"Flat fee of {flat_fee} cents"

        elif entry.pricing_type == PricingType.PER_UNIT:
            subtotal = billable_qty * entry.unit_price_cents
            total_cents = flat_fee + subtotal
            expl = f"{billable_qty} units @ {entry.unit_price_cents} cents/unit + {flat_fee} flat"

        elif entry.pricing_type == PricingType.TIERED_VOLUME:
            # Volume tiered: determine the tier the total billable quantity falls into,
            # then charge ALL billable units at that tier's unit rate.
            if not entry.tiers:
                raise ValueError("Tiered pricing requires tiers configuration")
            
            sorted_tiers = sorted(entry.tiers, key=lambda t: (t.up_to is None, t.up_to or 0))
            matched_tier = sorted_tiers[-1]
            for tier in sorted_tiers:
                if tier.up_to is not None and billable_qty <= tier.up_to:
                    matched_tier = tier
                    break

            tier_fee = matched_tier.flat_fee_cents
            subtotal = (billable_qty * matched_tier.unit_price_cents) + tier_fee
            total_cents = flat_fee + subtotal
            expl = f"Volume tier (up to {matched_tier.up_to}): {billable_qty} units @ {matched_tier.unit_price_cents}c/unit + {tier_fee} tier fee"

        elif entry.pricing_type == PricingType.GRADUATED_BRACKET:
            # Graduated / Bracket: charge units incrementally per bracket
            if not entry.tiers:
                raise ValueError("Graduated pricing requires tiers configuration")

            sorted_tiers = sorted(entry.tiers, key=lambda t: (t.up_to is None, t.up_to or 0))
            remaining = billable_qty
            prev_bound = 0
            subtotal = 0
            expl_parts = []

            for tier in sorted_tiers:
                if remaining <= 0:
                    break
                if tier.up_to is None:
                    # Unbounded top bracket
                    bracket_units = remaining
                else:
                    bracket_size = tier.up_to - prev_bound
                    bracket_units = min(remaining, bracket_size)
                    prev_bound = tier.up_to

                bracket_cost = (bracket_units * tier.unit_price_cents) + tier.flat_fee_cents
                subtotal += bracket_cost
                remaining -= bracket_units
                expl_parts.append(f"{bracket_units} @ {tier.unit_price_cents}c")

            total_cents = flat_fee + subtotal
            expl = f"Graduated: {', '.join(expl_parts)} + {flat_fee} flat"

        elif entry.pricing_type == PricingType.OVERAGE:
            # Overage pricing (BIL-051): included units covered by base, excess charged at overage rate
            overage_qty = max(0, billable_qty - entry.included_units)
            subtotal = overage_qty * entry.overage_unit_price_cents
            total_cents = flat_fee + subtotal
            expl = f"Included: {entry.included_units}, Overage: {overage_qty} @ {entry.overage_unit_price_cents}c/unit + {flat_fee} flat"

        else:
            raise ValueError(f"Unknown pricing type: {entry.pricing_type}")

        # Minimum charge floor (BIL-048)
        min_applied = False
        if entry.min_charge_cents > 0 and total_cents < entry.min_charge_cents:
            total_cents = entry.min_charge_cents
            expl += f" (Enforced minimum charge floor of {entry.min_charge_cents}c)"
            min_applied = True

        # Maximum charge cap (BIL-049)
        max_applied = False
        if entry.max_charge_cents is not None and total_cents > entry.max_charge_cents:
            total_cents = entry.max_charge_cents
            expl += f" (Enforced maximum charge cap of {entry.max_charge_cents}c)"
            max_applied = True

        return RatingLineItem(
            event_type=entry.event_type,
            pricing_type=entry.pricing_type,
            total_quantity=quantity,
            free_units_applied=free_applied,
            billable_quantity=billable_qty,
            subtotal_cents=subtotal,
            flat_fee_cents=flat_fee,
            total_cents=total_cents,
            min_charge_applied=min_applied,
            max_charge_applied=max_applied,
            explanation=expl
        )


class PriceBookManager:
    """
    Manages price book catalog and entries in relational store.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_entry(
        self,
        entry_id: str,
        tenant_id: str,
        plan_id: str,
        event_type: str,
        pricing_type: PricingType,
        flat_fee_cents: int = 0,
        free_units: int = 0,
        unit_price_cents: int = 0,
        min_charge_cents: int = 0,
        max_charge_cents: Optional[int] = None,
        included_units: int = 0,
        overage_unit_price_cents: int = 0,
        tiers: Optional[List[PriceTier]] = None
    ) -> PriceBookEntry:
        tiers_list = tiers or []
        tiers_json = json.dumps([t.model_dump() for t in tiers_list])
        rec = PriceBookEntryRecord(
            id=entry_id,
            tenant_id=tenant_id,
            plan_id=plan_id,
            event_type=event_type,
            pricing_type=pricing_type.value,
            flat_fee_cents=flat_fee_cents,
            free_units=free_units,
            unit_price_cents=unit_price_cents,
            min_charge_cents=min_charge_cents,
            max_charge_cents=max_charge_cents,
            included_units=included_units,
            overage_unit_price_cents=overage_unit_price_cents,
            tiers_json=tiers_json,
            created_at=datetime.now(timezone.utc)
        )
        self.session.add(rec)
        await self.session.commit()

        return PriceBookEntry(
            id=rec.id,
            tenant_id=rec.tenant_id,
            plan_id=rec.plan_id,
            event_type=rec.event_type,
            pricing_type=PricingType(rec.pricing_type),
            flat_fee_cents=rec.flat_fee_cents,
            free_units=rec.free_units,
            unit_price_cents=rec.unit_price_cents,
            min_charge_cents=rec.min_charge_cents,
            max_charge_cents=rec.max_charge_cents,
            included_units=rec.included_units,
            overage_unit_price_cents=rec.overage_unit_price_cents,
            tiers=[PriceTier(**t) for t in json.loads(rec.tiers_json)]
        )

    async def get_entries_for_plan(self, tenant_id: str, plan_id: str) -> List[PriceBookEntry]:
        stmt = select(PriceBookEntryRecord).where(
            PriceBookEntryRecord.tenant_id == tenant_id,
            PriceBookEntryRecord.plan_id == plan_id
        )
        res = await self.session.execute(stmt)
        records = res.scalars().all()
        return [
            PriceBookEntry(
                id=r.id,
                tenant_id=r.tenant_id,
                plan_id=r.plan_id,
                event_type=r.event_type,
                pricing_type=PricingType(r.pricing_type),
                flat_fee_cents=r.flat_fee_cents,
                free_units=r.free_units,
                unit_price_cents=r.unit_price_cents,
                min_charge_cents=r.min_charge_cents,
                max_charge_cents=r.max_charge_cents,
                included_units=r.included_units,
                overage_unit_price_cents=r.overage_unit_price_cents,
                tiers=[PriceTier(**t) for t in json.loads(r.tiers_json)]
            )
            for r in records
        ]
