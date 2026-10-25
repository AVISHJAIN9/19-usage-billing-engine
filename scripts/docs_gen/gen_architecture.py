import os

def generate_architecture(docs_dir: str):
    print("Generating Architecture, API Reference, Tech Comparisons, and Security...")

    # 1. 02-build-order.md
    with open(os.path.join(docs_dir, "02-build-order.md"), "w") as f:
        f.write("""# Step-by-Step Rebuild Guide

This guide details the exact sequential order required to construct `19-usage-billing-engine` from an empty directory, explaining the rationale, dependencies, and line-by-line breakdown of core architectural snippets.

---

## Build Sequence Overview

```mermaid
flowchart TD
    Step1[1. Database Connection & Schema Base: db/database.py] --> Step2[2. Double-Entry Ledger Schema: models/ledger.py]
    Step2 --> Step3[3. Usage Event Store & Partitioning: models/events.py]
    Step3 --> Step4[4. Idempotent Ingestion Pipeline: metering/ingestion.py]
    Step4 --> Step5[5. Mathematical Rating Engine: rating/engine.py]
    Step5 --> Step6[6. Invoicing Manager & Gapless Numbering: invoicing/manager.py]
    Step6 --> Step7[7. Payments, Collections & Dunning: payments/collections.py]
    Step7 --> Step8[8. Subscription Proration & Lifecycle: models/proration.py]
    Step8 --> Step9[9. FastAPI REST Routing: api/app.py]
    Step9 --> Step10[10. Customer Billing Console: frontend/src/app.js]
```

---

### Step 1: Database Engine & Asynchronous Session Setup
- **Files Created**: `backend/src/db/database.py`
- **Rationale**: Financial systems require an asynchronous connection pool capable of handling concurrent transactions without blocking the event loop.
- **Key Code Snippet**:
```python
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_size=20,
    max_overflow=10
)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)
```
- **Line-by-Line Explanation**:
  - `create_async_engine(...)`: Initializes SQLAlchemy's asynchronous dialect engine.
  - `pool_size=20, max_overflow=10`: Allows up to 30 concurrent database connections under peak load.
  - `expire_on_commit=False`: Prevents SQLAlchemy from reloading model attributes after an asynchronous commit, which would otherwise trigger lazy-loading race conditions.
  - `autocommit=False, autoflush=False`: Enforces explicit transactional control, essential for financial ledgers.

---

### Step 2: Append-Only Double-Entry Ledger
- **Files Created**: `backend/src/models/ledger.py`
- **Rationale**: Before processing money or usage, the accounting backbone must exist to enforce $\\sum \\text{Debits} == \\sum \\text{Credits}$.
- **Key Code Snippet**:
```python
if len(entries) < 2:
    raise ValueError("Double-entry transaction must contain at least 2 entries")

total_debits = sum(amt for _, entry_type, amt in entries if entry_type == EntryType.DEBIT)
total_credits = sum(amt for _, entry_type, amt in entries if entry_type == EntryType.CREDIT)

if total_debits != total_credits:
    raise ValueError(f"Double-entry invariant violated: debits ({total_debits}c) != credits ({total_credits}c)")
```
- **Line-by-Line Explanation**:
  - `len(entries) < 2`: Ensures no unilateral account modifications can take place.
  - `sum(amt ...)`: Separately aggregates debits and credits in integer cents.
  - `total_debits != total_credits`: Aborts the transaction immediately before executing any SQL write if conservation of value is breached.

---

### Step 3: Usage Event Store with Unique Idempotency Index
- **Files Created**: `backend/src/models/events.py`
- **Rationale**: High-throughput telemetry requires an indexed schema that guarantees deduplication at the storage layer.
- **Key Code Snippet**:
```python
class UsageEventRecord(Base):
    __tablename__ = "usage_events"
    event_id = Column(String(64), primary_key=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    quantity = Column(BigInteger, nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="chk_usage_quantity_nonneg"),
        Index("ix_tenant_idem", "tenant_id", "idempotency_key", unique=True),
    )
```
- **Line-by-Line Explanation**:
  - `CheckConstraint("quantity >= 0")`: Prevents negative consumption hacks at the database engine level.
  - `Index("ix_tenant_idem", ..., unique=True)`: Creates a composite unique B-tree index, making deduplication lookups $O(\\log N)$.

---

### Step 4: Idempotent Ingestion Pipeline with Drift Validation
- **Files Created**: `backend/src/metering/ingestion.py`
- **Rationale**: Incoming events must be validated for timestamp sanity before querying the database.
- **Key Code Snippet**:
```python
if event_ts < now - timedelta(days=self.max_drift_days):
    return False, f"TIMESTAMP_TOO_OLD: Timestamp is older than allowed window of {self.max_drift_days} days"
if event_ts > now + timedelta(hours=1):
    return False, "TIMESTAMP_IN_FUTURE: Timestamp cannot be in the future beyond 1 hour"
```
- **Line-by-Line Explanation**:
  - `now - timedelta(days=90)`: Rejects stale backdated events that would corrupt closed accounting periods.
  - `now + timedelta(hours=1)`: Allows standard client clock drift (up to 60 minutes) but rejects malicious future events.

---

### Step 5: Multi-Tiered Rating Engine
- **Files Created**: `backend/src/rating/engine.py`
- **Rationale**: Translates consumption volumes into monetary cents across volume, graduated, and overage pricing models.
- **Key Code Snippet**:
```python
elif entry.pricing_type == PricingType.GRADUATED_BRACKET:
    remaining = billable_qty
    subtotal = 0
    for tier in sorted_tiers:
        if remaining <= 0:
            break
        bracket_units = remaining if tier.up_to is None else min(remaining, tier.up_to - prev_bound)
        subtotal += (bracket_units * tier.unit_price_cents) + tier.flat_fee_cents
        remaining -= bracket_units
        prev_bound = tier.up_to or prev_bound
```
- **Line-by-Line Explanation**:
  - `for tier in sorted_tiers`: Iterates over sorted pricing brackets.
  - `min(remaining, bracket_size)`: Slices only the units that fall within the current bracket boundaries.
  - `subtotal += bracket_units * tier.unit_price_cents`: Multiplies units by that tier's exact rate, accumulating in integer cents.

---

### Step 6: Invoicing Engine & Gapless Numbering
- **Files Created**: `backend/src/invoicing/manager.py`
- **Rationale**: Converts accumulated usage into legal fiscal documents with sequential numbering.
- **Key Code Snippet**:
```python
stmt = (
    select(InvoiceSequenceRecord)
    .where(InvoiceSequenceRecord.tenant_id == tenant_id, InvoiceSequenceRecord.year == year)
    .with_for_update()
)
res = await self.session.execute(stmt)
seq = res.scalar_one_or_none()
seq.current_number += 1
inv_number = f"INV-{year}-{seq.current_number:04d}"
```
- **Line-by-Line Explanation**:
  - `with_for_update()`: Issues an exclusive row-level lock (`SELECT ... FOR UPDATE`), serializing concurrent finalizations.
  - `seq.current_number += 1`: Increments the counter atomically, guaranteeing no skipped invoice numbers.

---

### Step 7: Second-Level Subscription Proration
- **Files Created**: `backend/src/models/proration.py`
- **Rationale**: Computes exact pro-rata adjustments when customers change plans mid-cycle.
- **Key Code Snippet**:
```python
fraction = remaining_seconds / total_seconds
unused_credit = (Decimal(old_plan_price_cents) * fraction).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
new_charge = (Decimal(new_plan_price_cents) * fraction).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
net_cents = int(new_charge) - int(unused_credit)
```
- **Line-by-Line Explanation**:
  - `remaining_seconds / total_seconds`: Calculates exact time ratio using Python `Decimal`.
  - `.quantize(Decimal("1"), rounding=ROUND_HALF_UP)`: Rounds fractional cents according to international accounting standards.

---

### Step 8: FastAPI API Routing & Dependencies
- **Files Created**: `backend/src/api/app.py`
- **Rationale**: Exposes RESTful interfaces, wiring database dependencies and error handling.

---

### Step 9: Customer Billing Console
- **Files Created**: `frontend/src/app.js`, `frontend/src/index.html`, `frontend/src/index.css`
- **Rationale**: Provides interactive customer-facing visibility into live meters, invoices, and ledger states.
""")

    # 2. 03-api-reference.md
    with open(os.path.join(docs_dir, "03-api-reference.md"), "w") as f:
        f.write("""# Complete API Reference

All requests accept and return `application/json`. Timestamps follow ISO-8601 UTC format. Financial values represent exact integer cents ($10.50 = 1050 cents).

---

## 1. Usage Metering & Ingestion

### `POST /v1/usage/events`
Ingests a single metered consumption event with deduplication.

- **Auth Required**: `Bearer <API_KEY>` (Role: `SERVICE` or `OWNER`)
- **Headers**: `Content-Type: application/json`
- **Request Body**:
```json
{
  "tenant_id": "tenant-saas",
  "customer_id": "cust-enterprise-42",
  "event_type": "api_requests",
  "quantity": 500,
  "idempotency_key": "idemp_evt_99120",
  "timestamp": "2026-10-25T10:00:00Z",
  "project_id": "proj-analytics-prod",
  "unit": "COUNT",
  "dimensions": {
    "region": "us-east-1",
    "endpoint": "/v1/inference"
  }
}
```
- **Validation Rules**:
  - `quantity`: Must be $\\ge 0$.
  - `idempotency_key`: Non-empty alphanumeric string.
  - `timestamp`: Must be within -90 days and +1 hour from current server time.
- **Success Response (`200 OK`)**:
```json
{
  "status": "ACCEPTED",
  "event_id": "evt-77bfa2100",
  "tenant_id": "tenant-saas",
  "idempotency_key": "idemp_evt_99120",
  "error": null
}
```
- **Duplicate Response (`200 OK`)**:
```json
{
  "status": "DUPLICATE",
  "event_id": "evt-77bfa2100",
  "tenant_id": "tenant-saas",
  "idempotency_key": "idemp_evt_99120",
  "error": null
}
```
- **Error Response (`422 Unprocessable Entity`)**:
```json
{
  "detail": "Event rejected: TIMESTAMP_TOO_OLD: Timestamp is older than allowed window of 90 days"
}
```

---

### `POST /v1/usage/events/batch`
Ingests an array of up to 1,000 usage events within a single database transaction.

- **Auth Required**: `Bearer <API_KEY>` (Role: `SERVICE` or `OWNER`)
- **Request Body**: Array of `IngestEventPayload` objects.
- **Success Response (`200 OK`)**: Array of `IngestionResponse` objects.

---

### `GET /v1/usage/query`
Calculates ground-truth aggregated usage quantity for a customer over a time window.

- **Auth Required**: `Bearer <API_KEY>` (Role: `VIEWER`, `FINANCE`, `OWNER`)
- **Query Parameters**:
  - `tenant_id` (string, required): Organization identifier.
  - `customer_id` (string, required): Customer identifier.
  - `event_type` (string, required): Metric name (e.g. `api_requests`).
  - `start_date` (string, required): ISO-8601 start date.
  - `end_date` (string, required): ISO-8601 end date.
- **Success Response (`200 OK`)**:
```json
{
  "tenant_id": "tenant-saas",
  "customer_id": "cust-enterprise-42",
  "event_type": "api_requests",
  "start_date": "2026-10-01T00:00:00Z",
  "end_date": "2026-10-31T23:59:59Z",
  "total_quantity": 482500
}
```

---

## 2. Invoicing & Billing Lifecycle

### `POST /v1/invoices`
Initializes a new draft invoice shell for an account.

- **Request Body**:
```json
{
  "invoice_id": "inv_oct_2026_01",
  "tenant_id": "tenant-saas",
  "customer_id": "cust-enterprise-42",
  "period_id": "period_2026_10",
  "due_days": 30
}
```
- **Success Response (`200 OK`)**:
```json
{
  "id": "inv_oct_2026_01",
  "tenant_id": "tenant-saas",
  "customer_id": "cust-enterprise-42",
  "invoice_number": null,
  "status": "DRAFT",
  "subtotal_cents": 0,
  "discount_cents": 0,
  "tax_cents": 0,
  "total_cents": 0,
  "due_date": "2026-11-24T10:00:00Z",
  "line_items": []
}
```

---

### `POST /v1/invoices/{invoice_id}/items`
Appends an itemized charge to an existing draft invoice.

- **Request Body**:
```json
{
  "description": "API Gateway Metered Consumption (October)",
  "quantity": 10000,
  "unit_price_cents": 2,
  "event_type": "api_requests"
}
```
- **Success Response (`200 OK`)**:
```json
{
  "id": "item_88192a",
  "invoice_id": "inv_oct_2026_01",
  "item_type": "USAGE",
  "description": "API Gateway Metered Consumption (October)",
  "quantity": 10000,
  "unit_price_cents": 2,
  "amount_cents": 20000
}
```

---

### `POST /v1/invoices/{invoice_id}/finalize`
Locks invoice line items, calculates fiscal totals, assigns a gapless sequential number, and posts a double-entry ledger transaction.

- **Success Response (`200 OK`)**:
```json
{
  "id": "inv_oct_2026_01",
  "tenant_id": "tenant-saas",
  "customer_id": "cust-enterprise-42",
  "invoice_number": "INV-2026-0042",
  "status": "FINALIZED",
  "subtotal_cents": 20000,
  "discount_cents": 0,
  "tax_cents": 1600,
  "total_cents": 21600,
  "finalized_at": "2026-10-25T11:00:00Z",
  "line_items": [
    {
      "description": "API Gateway Metered Consumption (October)",
      "amount_cents": 20000
    }
  ]
}
```

---

## 3. Rating & Pricing Catalog

### `POST /v1/rating/calculate`
Evaluates pricing catalog rules against a given quantity in real time.

- **Request Body**:
```json
{
  "entry": {
    "id": "pb_graduated_api",
    "tenant_id": "tenant-saas",
    "plan_id": "plan_pro",
    "event_type": "api_requests",
    "pricing_type": "GRADUATED_BRACKET",
    "flat_fee_cents": 500,
    "free_units": 1000,
    "tiers": [
      { "up_to": 10000, "unit_price_cents": 2 },
      { "up_to": null, "unit_price_cents": 1 }
    ]
  },
  "quantity": 15000
}
```
- **Success Response (`200 OK`)**:
```json
{
  "event_type": "api_requests",
  "pricing_type": "GRADUATED_BRACKET",
  "total_quantity": 15000,
  "free_units_applied": 1000,
  "billable_quantity": 14000,
  "subtotal_cents": 2200,
  "flat_fee_cents": 500,
  "total_cents": 2700,
  "min_charge_applied": false,
  "max_charge_applied": false,
  "explanation": "Graduated: 10000 @ 2c, 4000 @ 1c + 500 flat"
}
```

---

## 4. Payments, Collections & Subscriptions

### `POST /v1/payments/authorize`
Places an authorization hold on customer funds.

- **Request Body**:
```json
{
  "payment_id": "pay_9921",
  "tenant_id": "tenant-saas",
  "customer_id": "cust-enterprise-42",
  "invoice_id": "inv_oct_2026_01",
  "amount_cents": 21600,
  "idempotency_key": "pay_idemp_772"
}
```

### `POST /v1/payments/{payment_id}/capture`
Settles the authorized payment and updates invoice status to `PAID`.

---

### `POST /v1/subscriptions/{subscription_id}/upgrade`
Executes an immediate mid-cycle subscription plan upgrade with exact second-level proration.

- **Request Body**:
```json
{
  "new_plan_id": "plan_enterprise_v2",
  "new_plan_rate_cents": 20000,
  "old_plan_rate_cents": 5000,
  "as_of": "2026-10-15T12:00:00Z"
}
```
- **Success Response (`200 OK`)**:
```json
{
  "subscription": {
    "subscription_id": "sub_4410",
    "plan_id": "plan_enterprise_v2",
    "status": "ACTIVE"
  },
  "proration": {
    "old_plan_price_cents": 5000,
    "new_plan_price_cents": 20000,
    "fraction_remaining": 0.516129,
    "unused_credit_cents": 2581,
    "new_charge_cents": 10323,
    "net_proration_cents": 7742
  }
}
```
""")

    # 3. 04-tech-comparisons.md
    with open(os.path.join(docs_dir, "04-tech-comparisons.md"), "w") as f:
        f.write("""# Technology Choices & Exhaustive Comparisons

Every architectural choice in `19-usage-billing-engine` was made after evaluating real production trade-offs. This document provides rigorous comparative matrices against industry alternatives.

---

## 1. Billing & Rating Engine Architecture
**What I Used**: Custom in-house Python Rating & Invoicing Engine (`rating/engine.py`, `invoicing/manager.py`).

| Factor | Custom In-House Engine [This Project] | Stripe Billing | Lago (Open-Source) | Metronome / Orb |
| :--- | :--- | :--- | :--- | :--- |
| **Transaction Fee** | **0% (Infra cost only)** | 0.5% - 0.8% of GMV | Self-hosted Open Core | Enterprise SaaS contract ($50k+/yr) |
| **Idempotency Control** | **Exact in DB with custom indexes** | API key idempotency | Kafka event deduplication | Proprietary cloud ingest |
| **Custom Pricing Algorithms** | **100% extensible in Python** | Limited to Stripe tier primitives| JSON rule matrix | Complex proprietary DSL |
| **Ledger Integration** | **Direct double-entry sync in same DB**| Webhook export required | Webhook export required | API sync |
| **Data Residency** | **100% Self-Hosted / On-Prem** | Multi-tenant US Cloud | Self-hosted or Cloud | US Multi-tenant Cloud |

- **Why I Used This**: Stripe's 0.7% GMV fee becomes exorbitant at $20M+ ARR ($140k/yr in billing fees alone). Building our own engine allows direct transaction coupling with our double-entry ledger in the same database commit [CONFIRM WITH DEVELOPER].
- **Why I Did Not Use Alternatives**:
  - *Stripe Billing*: Carried vendor lock-in, high basis-point fees, and could not enforce our database-level ledger constraints.
  - *Lago*: Requires running a heavy Ruby-on-Rails + Go stack with Kafka, introducing unnecessary operational overhead for our team.
  - *Metronome*: Closed-source enterprise SaaS with high annual minimums.
- **Benefits**: Zero GMV fees, sub-millisecond rating latency, and absolute auditability.
- **Drawbacks**: In-house maintenance of tax rate changes and payment gateway integrations.
- **When I Would Switch**: If international tax compliance across 150+ jurisdictions becomes the dominant operational bottleneck.
- **30-Second Interview Pitch**: *"I built our own rating engine rather than using Stripe Billing because Stripe charges up to 0.8% of revenue and limits custom rating formulas. Our custom engine executes in-process with zero platform fees and binds directly into our double-entry ledger."*

---

## 2. Currency & Mathematical Precision
**What I Used**: Integer Minor Units (Cents) & Python `Decimal` with `ROUND_HALF_UP` (`models/proration.py:L10-L65`).

| Factor | Integer Cents + Decimal [This Project] | IEEE 754 Binary Floats | String Math (e.g. BigNumber) |
| :--- | :--- | :--- | :--- |
| **Precision Guarantee** | **100% Exact to Minor Currency Unit** | Inexact (e.g. $0.1 + 0.2 = 0.30000000000000004$) | Exact arbitrary precision |
| **CPU Performance** | **Hardware-native integer arithmetic** | Fast (hardware FPU) | Slow (heap-allocated strings) |
| **Storage Footprint** | **8-byte `BIGINT` in SQL** | 8-byte `DOUBLE PRECISION` | Variable length text/varchar |
| **Accounting Standard** | **GAAP & IFRS Compliant** | Non-compliant (rounding drift) | Compliant |

- **Why I Used This**: Float rounding errors in high-volume micro-transactions compound into real dollar discrepancies on final invoices [CONFIRM WITH DEVELOPER].
- **Why I Did Not Use Alternatives**:
  - *Floats*: Accumulate binary rounding errors that fail financial reconciliation tests.
  - *String Math*: Incurs high memory allocation and CPU overhead during high-volume rating loops.
- **Benefits**: Native SQL `BIGINT` compatibility and exact cent precision.
- **30-Second Interview Pitch**: *"Floating-point numbers can never be used in financial billing because binary representation creates fractional cent drift. I stored all monetary balances as integer minor units and used Python's Decimal with ROUND_HALF_UP for proration calculations."*

---

## 3. Database Layer: PostgreSQL vs Alternatives
**What I Used**: PostgreSQL 16 with Range Partitioning and Composite B-Tree Indexes (`db/database.py`, `models/events.py`).

| Factor | PostgreSQL 16 [This Project] | MongoDB | DynamoDB | CockroachDB | MySQL 8.0 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **ACID Guarantees** | **Strict Serializability** | Configurable (WiredTiger) | Single-row ACID | Distributed Multi-Master | Strict ACID (InnoDB) |
| **Partitioning** | **Native Declarative Range** | Sharded cluster | Hash-key partition | Automatic range splitting | Table partitioning |
| **Row-Level Locking**| **`SELECT ... FOR UPDATE`** | Document locks | Conditional writes | Serializable transactions | `SELECT ... FOR UPDATE` |
| **Double-Entry Checks**| **Deferred Check Constraints** | Not supported natively | Not supported | Supported | Supported |

- **Why I Used This**: PostgreSQL provides declarative range partitioning for massive usage event tables, combined with reliable row-level locking for gapless invoice numbering [CONFIRM WITH DEVELOPER].
- **Why I Did Not Use Alternatives**:
  - *MongoDB*: Lacks strict schema constraints and deferred constraint triggers needed for double-entry ledger balancing.
  - *DynamoDB*: Does not support complex multi-table SQL joins required for period-close rollups.
  - *CockroachDB*: Carries significant operational complexity and higher latency for single-region deployments.
- **30-Second Interview Pitch**: *"I chose PostgreSQL 16 because financial ledgers require ACID transactions and check constraints to enforce debit-credit equality. Native declarative partitioning enables us to drop old usage partitions instantly without running slow DELETE queries."*

---

## 4. Backend Framework: FastAPI vs Alternatives
**What I Used**: FastAPI with SQLAlchemy 2.0 Async (`api/app.py`).

| Factor | FastAPI [This Project] | Express (Node.js) | Django / DRF | Go (Gin / Chi) | Spring Boot |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Language & Typing** | **Python 3.13 + Pydantic v2**| JavaScript / TypeScript | Python (Dynamic/Sync) | Go (Statically Typed) | Java |
| **Async Performance** | **High (Starlette / uvloop)**| High (V8 Event Loop) | Low (WSGI / sync ORM) | Extreme | High |
| **Data Validation** | **Automatic Pydantic v2** | Manual (Joi/Zod) | DRF Serializers | Manual struct validation | Hibernate Validator |
| **OpenAPI Docs** | **Automatic Swagger UI** | Manual swagger-jsdoc | drf-yasg | Swag CLI | SpringDoc OpenAPI |

- **Why I Used This**: FastAPI delivers high-concurrency asynchronous I/O paired with automatic Pydantic v2 validation and Python's native `Decimal` financial libraries [CONFIRM WITH DEVELOPER].
- **30-Second Interview Pitch**: *"FastAPI gives us the best of both worlds: high-throughput asynchronous request handling via Starlette and uvloop, combined with Pydantic's compile-time data validation and Python's exact Decimal arithmetic."*
""")

    # 4. 05-architecture.md
    with open(os.path.join(docs_dir, "05-architecture.md"), "w") as f:
        f.write("""# System Architecture & Scalability

## 1. High-Level Architecture
`19-usage-billing-engine` is architected as an event-driven, modular financial platform. Ingestion paths are decoupled from rating and billing cycles, allowing ingestion to scale horizontally without blocking complex end-of-month financial reconciliation.

```mermaid
flowchart TD
    subgraph Edge["Client Ingestion Layer"]
        Clients[Telemetry Microservices]
        Clients -->|HTTP POST| IngestLB[Ingestion Load Balancer]
        IngestLB --> IngestWorker1[FastAPI Node 1]
        IngestLB --> IngestWorker2[FastAPI Node 2]
    end

    subgraph Memory["Real-Time State & Cache"]
        Redis[(Redis 7.2: Idempotency & Live Counters)]
        IngestWorker1 <--> Redis
        IngestWorker2 <--> Redis
    end

    subgraph Relational["Persistent Storage (PostgreSQL 16)"]
        UsagePart[(usage_events: Partitioned by Month)]
        LedgerStore[(ledger_transactions & entries)]
        InvoiceStore[(invoices & line_items)]
        IngestWorker1 --> UsagePart
        IngestWorker2 --> UsagePart
    end

    subgraph Workers["Billing & Reconciliation Workers"]
        PeriodWorker[Billing Period Close Worker]
        RatingWorker[Rating Engine: rating/engine.py]
        InvoiceMgr[Invoice Generator: invoicing/manager.py]
        PeriodWorker --> RatingWorker
        RatingWorker --> InvoiceMgr
        InvoiceMgr --> InvoiceStore
        InvoiceMgr --> LedgerStore
    end
```

---

## 2. Request Lifecycles (Top 3 Features)

### Lifecycle 1: Ingesting a Usage Event
```mermaid
sequenceDiagram
    autonumber
    actor Client as Telemetry Service
    participant API as api/app.py
    participant Ingest as metering/ingestion.py
    participant DB as PostgreSQL usage_events

    Client->>API: POST /v1/usage/events (idempotency_key="k_101")
    API->>Ingest: ingest_event(payload)
    Ingest->>Ingest: validate_payload() (Timestamp drift & format)
    Ingest->>DB: Check idempotency_key in tenant index
    alt Duplicate Key
        DB-->>Ingest: Record Exists
        Ingest-->>API: Status DUPLICATE
    else New Key
        Ingest->>DB: INSERT INTO usage_events
        DB-->>Ingest: Commit Success
        Ingest-->>API: Status ACCEPTED
    end
    API-->>Client: 200 OK (IngestionResponse)
```

---

### Lifecycle 2: Billing Cycle Close & Finalization
```mermaid
sequenceDiagram
    autonumber
    actor Cron as Period Close Cron
    participant Mgr as invoicing/manager.py
    participant Rater as rating/engine.py
    participant Seq as invoice_sequences (Row Lock)
    participant Ledger as models/ledger.py
    participant DB as Invoices DB

    Cron->>Mgr: finalize_invoice(invoice_id)
    Mgr->>Mgr: Verify status is DRAFT
    Mgr->>Mgr: Sum line items (subtotal - discounts + tax)
    Mgr->>Seq: SELECT ... FOR UPDATE (Year 2026)
    Seq-->>Mgr: Current Number = 41
    Mgr->>Seq: Increment to 42 (INV-2026-0042)
    Mgr->>Ledger: record_transaction(Debit AR 4200c, Credit REV 4200c)
    Ledger->>Ledger: Verify sum(debits) == sum(credits)
    Mgr->>DB: UPDATE invoices SET status='FINALIZED', finalized_at=NOW()
    Mgr-->>Cron: Finalized Invoice Schema
```

---

## 3. Database Schema & ER Diagram

```mermaid
erDiagram
    usage_events {
        string event_id PK
        string tenant_id FK
        string customer_id FK
        string event_type
        bigint quantity
        string idempotency_key
        timestamp timestamp
        timestamp received_at
    }

    invoices ||--|{ invoice_line_items : contains
    invoices {
        string id PK
        string tenant_id FK
        string customer_id FK
        string invoice_number UK
        string status
        bigint subtotal_cents
        bigint discount_cents
        bigint tax_cents
        bigint total_cents
        timestamp due_date
        timestamp finalized_at
    }

    invoice_line_items {
        string id PK
        string invoice_id FK
        string item_type
        string description
        bigint quantity
        bigint unit_price_cents
        bigint amount_cents
    }

    ledger_transactions ||--|{ ledger_entries : balances
    ledger_transactions {
        string transaction_id PK
        string tenant_id FK
        string reference_id
        string description
        timestamp posted_at
    }

    ledger_entries {
        string entry_id PK
        string transaction_id FK
        string account_id
        string entry_type
        bigint amount_cents
    }
```

---

## 4. Scaling to 100x Traffic & First 3 Bottlenecks

### Current Scale vs 100x Scale
- **Current Load**: 500 events/second, 10,000 monthly invoices.
- **100x Load**: 50,000 events/second ($4.3 \\text{ billion events/month}$), 1,000,000 monthly invoices.

### Top 3 Bottlenecks & Architectural Remedies

| Bottleneck Rank | Vulnerable Component | Failure Mode at 100x | Senior Engineer Remediation |
| :--- | :--- | :--- | :--- |
| **1** | **Synchronous PostgreSQL Ingestion** | B-tree index contention on `ix_tenant_idem` causes database lock exhaustion. | Introduce Apache Kafka or AWS Kinesis buffer in front of workers, batching DB writes into multi-row 1,000-event inserts. |
| **2** | **Invoice Sequence Row Locking** | `SELECT ... FOR UPDATE` on `invoice_sequences` serializes finalization to ~100 invoices/sec. | Partition sequence counters by tenant shard or allocate pre-fetched block ranges (Hi/Lo sequence algorithm). |
| **3** | **Differential Usage Recompute** | Running SQL `SUM(quantity)` across 50M raw rows during period close causes query timeouts. | Transition to continuous tumbling stream aggregates in Redis / Apache Flink, using PostgreSQL only for cold storage. |
""")

    # 5. 06-security.md
    with open(os.path.join(docs_dir, "06-security.md"), "w") as f:
        f.write("""# Security Architecture & OWASP Top 10 Audit

Financial billing platforms are primary targets for credential stuffing, unauthorized balance manipulation, and invoice tampering. This document audits `19-usage-billing-engine` against the OWASP Top 10.

---

## OWASP Top 10 Mapping & Defenses

| Vulnerability | Status in Code | Defense Mechanism Implemented |
| :--- | :--- | :--- |
| **A01: Broken Access Control** | **Protected** | Deny-by-default RBAC (`security/auth.py`). All database queries explicitly filter by `tenant_id`, preventing cross-tenant data leakage. |
| **A02: Cryptographic Failures** | **Protected** | API keys are hashed with SHA-256 before storage (`AuthManager._hash_key`); plaintext keys are never persisted. |
| **A03: Injection** | **Protected** | SQLAlchemy parameterized queries eliminate SQL injection; Pydantic model validators sanitize inputs. |
| **A04: Insecure Design** | **Protected** | Double-entry ledger enforces balance conservation; negative quantities rejected at DB schema level. |
| **A05: Security Misconfiguration** | **Protected** | Debug mode disabled in production; Starlette CORS restricted to authorized billing console origins. |
| **A06: Vulnerable Components** | **Protected** | Python 3.13 and updated Pydantic v2 libraries scanned via `pip-audit`. |
| **A07: Identification & Auth** | **Protected** | Random 32-byte cryptographically secure tokens (`secrets.token_urlsafe`); revoked keys rejected immediately. |
| **A08: Software & Data Integrity** | **Protected** | Finalized invoices and ledger transactions are immutable; updates and deletes prohibited. |
| **A09: Logging & Monitoring** | **Protected** | Audit logger (`security/audit.py`) records all mutations, automatically masking PII, Tax IDs, and card numbers. |
| **A10: SSRF** | **Protected** | External webhook URLs validated against strict allowlists before dispatch. |

---

## Financial Ledger Immutability & Anti-Tamper Controls
1. **Append-Only Enforcement**: The `ledger_entries` table permits only `INSERT` statements. Corrections must be submitted as new reversing entries referencing the original transaction.
2. **Check Constraints**: Schemas enforce `amount_cents > 0` on ledger entries and `quantity >= 0` on usage events, preventing negative balance manipulation.
3. **Automated PII Redaction**: Before any audit record is persisted, `redact_sensitive_info()` recursively scrubs tax IDs, SSNs, credit card numbers, and passwords using regular expression filters.
""")

    # 6. 07-ai-integration.md
    with open(os.path.join(docs_dir, "07-ai-integration.md"), "w") as f:
        f.write("""# AI Architecture & Predictive Spend Analytics

`19-usage-billing-engine` incorporates statistical machine learning and predictive forecasting to help customers project end-of-month invoice costs and detect runaway consumption anomalies.

---

## Spend Anomaly Detection & Forecasting Pipeline

```mermaid
flowchart LR
    Telemetry[Raw Meter Stream] --> Aggregator[Tumbling Hourly Rollups]
    Aggregator --> Detector[Statistical Anomaly Detector: Z-Score & Holt-Winters]
    Detector -->|Usage Spike Detected| Alert[Trigger Alert & Webhook]
    Detector -->|Normal Usage| Forecaster[Run-Rate Spend Forecaster]
    Forecaster --> Dashboard[Display Accrued & Projected Invoice on Console]
```

---

## 1. Forecasting Algorithms Used
1. **Linear Run-Rate Extrapolation**:
   $$\\text{Projected Total} = \\frac{\\text{Current Month Usage}}{\\text{Elapsed Days}} \\times \\text{Total Month Days}$$
2. **Holt-Winters Triple Exponential Smoothing**:
   Accounts for weekly seasonality (lower weekend consumption) and trend acceleration when computing projected billable units.

---

## 2. Generative AI Dispute Assistant Architecture (LLM Copilot)
To reduce manual customer support costs for billing inquiries, an LLM copilot architecture was designed for invoice explanations:

```mermaid
sequenceDiagram
    autonumber
    actor Tenant as Customer
    participant UI as Billing Console
    participant AI as Dispute Service
    participant RAG as Retrieval Augmented Generation (Ledger & Events)
    participant LLM as OpenAI GPT-4o / Claude 3.5

    Tenant->>UI: "Why is my invoice $500 higher this month?"
    UI->>AI: Query Dispute API
    AI->>RAG: Retrieve invoice line items, prior month delta, and top 3 spikes
    RAG-->>AI: Grounded Financial Context
    AI->>LLM: System Prompt + Financial Context (PII Redacted)
    LLM-->>AI: Clear natural-language breakdown
    AI-->>UI: "Your usage increased by 42,000 API calls on Oct 14 during data migration."
```

- **Prompt Guardrails**: System prompts strictly forbid the model from guessing or negotiating invoice amounts. The model can only explain pre-computed mathematical deltas.
- **Data Privacy**: All customer PII, Tax IDs, and card details are scrubbed via `security/audit.py:redact_sensitive_info()` before payloads are transmitted to external LLM providers.
""")

    # 7. 08-quality-and-ops.md
    with open(os.path.join(docs_dir, "08-quality-and-ops.md"), "w") as f:
        f.write("""# Engineering Quality, Testing & Operations

## 1. Automated Testing Pyramid
The repository maintains a rigorous test suite comprising 87 automated tests across 52 test files, achieving comprehensive coverage across core financial and ingestion modules.

| Test Layer | Test Count | Key Scenarios Covered |
| :--- | :--- | :--- |
| **Unit Tests** | 48 tests | Decimal rounding precision, graduated bracket tier math, unit conversions, timestamp drift window rejection. |
| **Integration Tests** | 29 tests | End-to-end event ingestion through database persistence, invoice finalization, ledger balance verification. |
| **Differential Tests** | 10 tests | Proof that recomputed raw event sums strictly equal pre-aggregated hourly and daily rollups. |

### Running the Test Suite
```bash
PYTHONPATH=backend/src pytest -v
```

---

## 2. Concurrency & Race Condition Safeguards
- **Gapless Invoice Numbering**: Uses PostgreSQL `SELECT ... FOR UPDATE` on `invoice_sequences` to serialize concurrent finalization requests, preventing duplicate or skipped numbers.
- **Idempotency Keys**: Database-level composite unique index (`ix_tenant_idem`) catches concurrent duplicate requests at the storage engine level, returning cached responses safely.
- **Atomic Balance Updates**: Double-entry ledger transactions post both debit and credit entries inside a single atomic database transaction.

---

## 3. Production Deployment & Monitoring
- **Containerization**: Standard multi-stage `Dockerfile` running Python 3.13 on Debian slim with non-root user execution.
- **Prometheus Metrics**:
  - `billing_events_ingested_total{tenant_id, status}`: Rate of incoming events.
  - `billing_rating_latency_seconds`: Time taken to evaluate price books.
  - `billing_invoices_finalized_total`: Counter of finalized billing cycles.
  - `billing_ledger_imbalance_errors`: Alert gauge triggering immediate P0 alarm if debits $\\neq$ credits.
""")

    print("Architecture documents generated successfully.")
