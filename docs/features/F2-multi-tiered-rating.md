# F2: Multi-Tiered Dynamic Rating Engine

## Overview & Architecture
The dynamic rating engine in `backend/src/rating/engine.py` converts raw usage quantities into exact monetary amounts (in integer cents) across multiple pricing models.

```mermaid
flowchart TD
    Usage[Raw Usage Units] --> FreeTier{Exceeds Free Allowance?}
    FreeTier -->|No| ZeroCharge[Charge = 0 Cents]
    FreeTier -->|Yes| BillableQty[Compute Billable Units = Usage - Free]
    BillableQty --> ModelSelect{Pricing Model}
    ModelSelect -->|Graduated (Bracket)| GraduatedCalc[Slice across progressive rate brackets]
    ModelSelect -->|Volume Tiered| VolumeCalc[Select single unit rate for entire volume]
    ModelSelect -->|Overage Base| OverageCalc[Base recurring fee + Excess rate]
    GraduatedCalc --> SumCents[Sum Total Integer Cents]
    VolumeCalc --> SumCents
    OverageCalc --> SumCents
    SumCents --> ClampLimits{Min Floor / Max Ceiling?}
    ClampLimits -->|Below Min| MinCharge[Apply Minimum Charge Floor]
    ClampLimits -->|Above Max| MaxCap[Apply Maximum Charge Ceiling]
    ClampLimits -->|Within Limits| FinalCents[Final Billable Amount]
```

## Say It Out Loud
> "I built the rating engine in `rating/engine.py` to handle complex enterprise SaaS pricing models without requiring manual calculations or code changes. When usage is rated, the engine deducts any free tier allowance first, then branches into the appropriate pricing algorithm.
> 
> For graduated bracket pricing, it slices the billable volume into successive tiers—for instance, charging the first 1,000 units at 5 cents and subsequent units at 3 cents. For volume pricing, it evaluates total volume to select a single discounted rate applied across all units. It also supports overage pricing with base allowances, and automatically enforces contract minimum charge floors and maximum charge ceilings.
> 
> Crucially, all math is done in exact integer cents or fixed-point decimal arithmetic, completely avoiding binary floating-point rounding errors.
> 
> I chose a pure functional rating engine design so that pricing can be evaluated both in batch during monthly invoicing and on-the-fly when customers request real-time cost estimates.
> 
> If an invalid pricing configuration or negative quantity is passed, the engine throws an immediate ValueError.
> 
> A current limitation is that currency conversion happens downstream rather than inside the rating engine, which I would unify in the next release."
