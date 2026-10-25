# Project Pitch: Real-Time Usage & Metered Billing Engine

## 30-Second Elevator Pitch
> "I designed and built **19-Usage-Billing-Engine**, an enterprise-grade metered billing, rating, and invoicing platform in Python FastAPI, PostgreSQL, and React. It solves the critical financial risk of usage-based pricing by providing an idempotent ingestion pipeline that guarantees exactly-once billing under network retries. It features a multi-tiered rating engine supporting graduated and volume pricing calculated to exact integer cents, an append-only double-entry ledger that strictly enforces debit-credit conservation, and automated billing cycle reconciliation with gapless invoice numbering."

---

## 2-Minute Technical Interview Pitch
> "As SaaS companies transition from flat subscriptions to usage-based models, their billing infrastructure faces severe reliability challenges: duplicate events caused by network retries, floating-point rounding errors on micro-transactions, and complex mid-cycle plan upgrades requiring exact pro-rata math.
>
> To solve these challenges, I engineered a high-throughput, audit-proof billing platform.
>
> At the edge, in `metering/ingestion.py`, the ingestion pipeline handles high-volume telemetry events like API calls or GPU compute seconds. Every event is checked against a cryptographic idempotency key index in PostgreSQL. If client network timeouts cause retries, our system recognizes duplicate keys in constant time and returns the cached confirmation, preventing double-billing without dropping valid traffic.
>
> In `rating/engine.py`, the rating engine evaluates accumulated raw usage against dynamic customer price books. It supports flat rates, per-unit metering, volume discounts, and graduated slab tiers—where the first 1,000 units might be free, the next 10,000 cost 2 cents, and beyond costs 1 cent. All mathematical operations are calculated in integer minor units (cents) or fixed-point Decimal with `ROUND_HALF_UP`, eliminating floating-point rounding drift.
>
> In `invoicing/manager.py`, when a billing period closes, the invoice manager locks customer meters, aggregates usage rollups, applies promotional discounts and taxes, and assigns a gapless sequential invoice number (`INV-YYYY-XXXX`) using row-level locking.
>
> Crucially, every financial mutation is synchronized with an append-only double-entry ledger in `models/ledger.py`. Every ledger transaction enforces that the sum of debits strictly equals the sum of credits across at least two entries, guaranteeing accounting compliance.
>
> The frontend provides an interactive billing console with real-time KPI metrics and invoice inspection. The entire architecture is verified by 87 automated tests covering timestamp drift rejection, differential rollup reconciliation, and dunning schedules."
