# 19-usage-billing-engine

## Mission
MVP implementation for 19-usage-billing-engine.

## Status
<!-- STATUS:BEGIN -->
**COMPLETED 90 · WORKING 0 · TODO 0**

### Area Database & Distributed Infrastructure (6 features · 6 COMPLETED · 0 WORKING · 0 TODO)

| ID | Feature | Layers | Status |
|---|---|---|---|
| BIL-001 | Usage event store | BE+DB | COMPLETED |
| BIL-003 | Relational billing store | BE+DB | COMPLETED |
| BIL-006 | Ledger database | BE+DB | COMPLETED |
| BIL-005 | Payment database | BE+DB | COMPLETED |
| BIL-009 | Indexes for usage queries | BE+DB | COMPLETED |
| BIL-010 | Partitioning | BE+DB | COMPLETED |

### Area Accounts, Plans & Entitlements (3 features · 3 COMPLETED · 0 WORKING · 0 TODO)

| ID | Feature | Layers | Status |
|---|---|---|---|
| BIL-013 | Customer accounts | BE | COMPLETED |
| BIL-017 | Subscription model | BE | COMPLETED |
| BIL-019 | Plan assignment | BE | COMPLETED |

### Area Usage Metering Core (9 features · 9 COMPLETED · 0 WORKING · 0 TODO)

| ID | Feature | Layers | Status |
|---|---|---|---|
| BIL-026 | Usage event ingestion | BE | COMPLETED |
| BIL-027 | Event schema validation | BE | COMPLETED |
| BIL-030 | Event deduplication | BE | COMPLETED |
| BIL-031 | Idempotency keys | BE | COMPLETED |
| BIL-032 | Usage dimensions | BE | COMPLETED |
| BIL-035 | Tenant attribution | BE | COMPLETED |
| BIL-029 | Timestamp validation | BE | COMPLETED |
| BIL-037 | Project attribution | BE | COMPLETED |
| BIL-038 | Usage units | BE | COMPLETED |

### Area Billing & Rating (13 features · 13 COMPLETED · 0 WORKING · 0 TODO)

| ID | Feature | Layers | Status |
|---|---|---|---|
| BIL-039 | Pricing plan model | BE+DB | COMPLETED |
| BIL-041 | Price book | BE+DB | COMPLETED |
| BIL-042 | Metered pricing | BE+DB | COMPLETED |
| BIL-043 | Flat subscription pricing | BE+DB | COMPLETED |
| BIL-044 | Tiered pricing | BE+DB | COMPLETED |
| BIL-046 | Graduated pricing | BE+DB | COMPLETED |
| BIL-047 | Per-unit pricing | BE+DB | COMPLETED |
| BIL-050 | Free tiers | BE+DB | COMPLETED |
| BIL-040 | Plan versioning | BE+DB | COMPLETED |
| BIL-045 | Volume pricing | BE+DB | COMPLETED |
| BIL-048 | Minimum charges | BE+DB | COMPLETED |
| BIL-049 | Maximum charges | BE+DB | COMPLETED |
| BIL-051 | Overage pricing | BE+DB | COMPLETED |

### Area Aggregation & Periods (7 features · 7 COMPLETED · 0 WORKING · 0 TODO)

| ID | Feature | Layers | Status |
|---|---|---|---|
| BIL-054 | Monthly aggregation | BE+DB | COMPLETED |
| BIL-055 | Billing-period lifecycle | BE+DB | COMPLETED |
| BIL-057 | Usage rollups | BE+DB | COMPLETED |
| BIL-064 | Period close | BE+DB | COMPLETED |
| BIL-052 | Hourly aggregation | BE+DB | COMPLETED |
| BIL-053 | Daily aggregation | BE+DB | COMPLETED |
| BIL-063 | Real-time usage counters | BE+DB | COMPLETED |

### Area Ledger & Financial Integrity (9 features · 9 COMPLETED · 0 WORKING · 0 TODO)

| ID | Feature | Layers | Status |
|---|---|---|---|
| BIL-070 | Double-entry accounting hooks | BE+DB | COMPLETED |
| BIL-071 | Ledger transactions | BE+DB | COMPLETED |
| BIL-073 | Ledger reconciliation | BE+DB | COMPLETED |
| BIL-074 | Balance calculation | BE+DB | COMPLETED |
| BIL-075 | Debit/credit entries | BE+DB | COMPLETED |
| BIL-065 | Immutable usage ledger | BE+DB | COMPLETED |
| BIL-066 | Charge ledger | BE+DB | COMPLETED |
| BIL-072 | Transaction IDs | BE+DB | COMPLETED |
| BIL-076 | Adjustment journal | BE+DB | COMPLETED |

### Area Invoicing (11 features · 11 COMPLETED · 0 WORKING · 0 TODO)

| ID | Feature | Layers | Status |
|---|---|---|---|
| BIL-077 | Invoice generation | BE+DB | COMPLETED |
| BIL-079 | Invoice finalization | BE+DB | COMPLETED |
| BIL-080 | Invoice numbering | BE+DB | COMPLETED |
| BIL-081 | Invoice line items | BE+DB | COMPLETED |
| BIL-087 | Invoice totals | BE+DB | COMPLETED |
| BIL-078 | Draft invoices | BE+DB | COMPLETED |
| BIL-082 | Usage line-item generation | BE+DB | COMPLETED |
| BIL-083 | Subscription line items | BE+DB | COMPLETED |
| BIL-084 | Discount line items | BE+DB | COMPLETED |
| BIL-086 | Tax line items | BE+DB | COMPLETED |
| BIL-088 | Currency handling | BE+DB | COMPLETED |

### Area Payments & Collections (10 features · 10 COMPLETED · 0 WORKING · 0 TODO)

| ID | Feature | Layers | Status |
|---|---|---|---|
| BIL-090 | Payment provider integration | BE+DB | COMPLETED |
| BIL-095 | Payment webhooks | BE+DB | COMPLETED |
| BIL-096 | Webhook idempotency | BE+DB | COMPLETED |
| BIL-092 | Payment authorization | BE+DB | COMPLETED |
| BIL-093 | Payment capture | BE+DB | COMPLETED |
| BIL-097 | Payment retries | BE+DB | COMPLETED |
| BIL-098 | Failed-payment handling | BE+DB | COMPLETED |
| BIL-099 | Dunning workflow | BE+DB | COMPLETED |
| BIL-100 | Grace period | BE+DB | COMPLETED |
| BIL-101 | Automatic collection | BE+DB | COMPLETED |

### Area Backend APIs & Services (7 features · 7 COMPLETED · 0 WORKING · 0 TODO)

| ID | Feature | Layers | Status |
|---|---|---|---|
| BIL-103 | Usage ingestion API | BE | COMPLETED |
| BIL-108 | Invoice API | BE | COMPLETED |
| BIL-104 | Meter API | BE | COMPLETED |
| BIL-106 | Rating API | BE | COMPLETED |
| BIL-107 | Usage query API | BE | COMPLETED |
| BIL-109 | Payment API | BE | COMPLETED |
| BIL-110 | Subscription API | BE | COMPLETED |

### Area Frontend & Billing Console (3 features · 3 COMPLETED · 0 WORKING · 0 TODO)

| ID | Feature | Layers | Status |
|---|---|---|---|
| BIL-146 | Invoice detail | FE+BE | COMPLETED |
| BIL-139 | Billing dashboard | FE+BE | COMPLETED |
| BIL-145 | Invoice list | FE+BE | COMPLETED |

### Area Accounts (6 features · 6 COMPLETED · 0 WORKING · 0 TODO)

| ID | Feature | Layers | Status |
|---|---|---|---|
| BIL-018 | Subscription lifecycle | BE | COMPLETED |
| BIL-020 | Plan upgrades | BE | COMPLETED |
| BIL-021 | Plan downgrades | BE | COMPLETED |
| BIL-022 | Plan cancellation | BE | COMPLETED |
| BIL-023 | Plan pause/resume | BE | COMPLETED |
| BIL-024 | Trial periods | BE | COMPLETED |

### Area Reporting (2 features · 2 COMPLETED · 0 WORKING · 0 TODO)

| ID | Feature | Layers | Status |
|---|---|---|---|
| BIL-115 | Revenue metrics | BE | COMPLETED |
| BIL-117 | MRR metrics | BE | COMPLETED |

### Area Security (4 features · 4 COMPLETED · 0 WORKING · 0 TODO)

| ID | Feature | Layers | Status |
|---|---|---|---|
| BIL-127 | API authentication | BE | COMPLETED |
| BIL-128 | RBAC | BE | COMPLETED |
| BIL-129 | Tenant isolation | BE | COMPLETED |
| BIL-136 | Audit logging | BE | COMPLETED |

<!-- STATUS:END -->

## Architecture
Usage & Billing Engine built with integer-cents financial precision:
- **Usage Metering Core**: Event store with unique constraints on `(tenant_id, idempotency_key)`, schema validation, timestamp drift prevention, and multi-dimensional grouping.
- **Billing & Rating Engine**: Multi-tier price book supporting flat subscription fees, linear per-unit, volume tiered pricing, graduated bracket pricing, and free tier allowances.
- **Aggregation & Periods**: Dynamic monthly rollup aggregators and immutable period lifecycle management (`OPEN` -> `CLOSING` -> `CLOSED`).
- **Ledger & Financial Integrity**: Append-only double-entry ledger enforcing $\sum \text{debits} == \sum \text{credits}$ in integer cents with automated invoice issuance and payment settlement hooks.
- **Invoicing & Payments**: Gapless sequential numbering (`INV-YYYY-XXXX`), strict total invariants (`subtotal = sum(lines)`, `total = subtotal - discounts + tax`), and deduplicated webhook processing.
- **Frontend Billing Console**: Modern dark-mode UI with glassmorphism, real-time line item entry, totals recomputation, and ledger preview.

## How to run
```bash
# Start Docker services (Postgres on 5419, Redis on 6319)
make up

# Run test suite
make test

# Start API server on port 8190
PYTHONPATH=backend/src uvicorn api.app:app --port 8190 --reload
```

## Decisions & Invariants
1. **Integer Cents Precision**: All financial operations are modeled in strictly positive integer cents to prevent IEEE-754 floating point drift.
2. **Double-Entry Constraint**: Every ledger transaction requires $\ge 2$ entries where sum of debits strictly equals sum of credits.
3. **Idempotent Ingestion**: Metered events and incoming payment webhooks are uniquely keyed per tenant to guarantee exactly-once processing under network retries.

## Verification
- Test Suite: 41 automated tests passing across backend and frontend.
- Reruns: 10/10 randomly chosen features verified by `progress.py check --rerun 10`.
- Audit Fakes: 0 violations reported by `audit_fakes.py`.



## Limitations
- BIL-090, BIL-095: Payment provider integration uses LOCAL_EQUIVALENT gateway sandbox; upgrade requires live Stripe/Braintree API keys
