import os

def generate_overview(docs_dir: str):
    print("Generating Overview documents...")

    # 1. 00-project-type.md
    with open(os.path.join(docs_dir, "00-project-type.md"), "w") as f:
        f.write("""# Project Type Detection & Adaptation Track

## Step 0 Pre-Check: Codebase Analysis & Classification

This document records the formal inspection and architectural classification of `19-usage-billing-engine`.

---

### Detection Evidence

A comprehensive inspection of `/Users/avishjain/avishjain9-repos/19-usage-billing-engine` was conducted across filesystem structure, dependencies, configuration files, and source code:

| Artifact Checked | Findings / Content | Classification Evidence |
| :--- | :--- | :--- |
| **Directory Name** | `19-usage-billing-engine` | High-throughput metered billing, rating, and double-entry financial engine. |
| **Backend Implementation** | `backend/src/` (`api/app.py`, `metering/`, `rating/`, `invoicing/`, `models/`, `payments/`, `security/`) | Python 3.13, FastAPI REST API framework, SQLAlchemy 2.0 Async, Pydantic v2 validation. |
| **Database Architecture** | `backend/src/db/database.py`, `backend/src/models/` | PostgreSQL 16 (production time-partitioned tables) / SQLite (`aiosqlite` testing), Redis counters. |
| **Frontend Implementation** | `frontend/src/` (`app.js`, `index.html`, `index.css`) | Vanilla ES6+ JavaScript, CSS3 responsive grid with dark mode theme variables, HTML5. |
| **Test Suite** | `backend/tests/` (50 test files), `frontend/tests/` (2 test files) | 87 passing unit & integration tests executed via `pytest-asyncio`. |
| **Package Manifests** | Root `package.json` (`vitepress`, `mermaid`), `backend/` Python imports | Node.js documentation toolchain + Pure Python asynchronous backend. |

---

### Formal Classification

- **Primary Classification**: **Track C: Non-MERN Backend & Financial Systems Engine**
  - **Backend**: Python 3.13, FastAPI, SQLAlchemy 2.0 (Async), Pydantic v2, PostgreSQL 16, Redis.
  - **Frontend**: Vanilla JavaScript (ES6+), HTML5, CSS3 Billing Dashboard & Invoice Inspector.
- **Financial Architecture Specializations**:
  - High-throughput idempotent usage event ingestion pipeline (`metering/ingestion.py`).
  - Multi-tier dynamic rating engine (`rating/engine.py`: volume, graduated, overage, free tiers).
  - Append-only double-entry bookkeeping ledger (`models/ledger.py`) with debit-credit conservation.
  - Automated billing cycle reconciliation, invoice finalization, and gapless sequential numbering (`invoicing/manager.py`).
  - Two-step payment authorization/capture, dunning workflow, and grace period lifecycle (`payments/collections.py`).

---

### Track Adaptation & Document Mapping Rules

Per the adaptation instructions for Track C:
1. **MERN Terminology Substitution**:
   - Replaced MongoDB / Mongoose with **PostgreSQL 16 time-partitioned tables**, SQLAlchemy 2.0 async sessions, and raw SQL indexing.
   - Replaced Express middleware with **FastAPI dependencies and Starlette CORS middleware**.
   - Replaced React Redux / Context with **Vanilla ES6+ state management and DOM updates**.
2. **Deep Dives Applied**:
   - Concurrency control: Row-level locking (`SELECT ... FOR UPDATE`) for gapless invoice numbering.
   - Financial invariants: Strict integer cents / Decimal `ROUND_HALF_UP` arithmetic, eliminating floating-point rounding drift.
   - Double-entry accounting: Every ledger transaction enforces `len(entries) >= 2` and `sum(debits) == sum(credits)`.
   - Data partitioning: Monthly range partitioning on `usage_events` with verified query plan partition pruning.
""")

    # 2. 00a-project-analysis.md
    with open(os.path.join(docs_dir, "00a-project-analysis.md"), "w") as f:
        f.write("""# Full Project Analysis: Usage & Metered Billing Engine

## 0.1 What the Project Is

### Project Name & Purpose
`19-usage-billing-engine` is an enterprise-grade, high-throughput metered billing, rating, and financial reconciliation engine. Modern cloud and AI companies are transitioning from flat monthly subscriptions to usage-based pricing (charging per API call, compute second, token, or gigabyte-hour). This introduces massive distributed systems challenges: out-of-order event delivery, network retries causing double-billing, floating-point rounding discrepancies, and mid-cycle plan upgrades requiring exact pro-rata credits.

This platform solves these problems through:
1. **Idempotent Ingestion**: Guarantees exactly-once accounting using cryptographic idempotency keys, absorbing burst traffic without duplicate charges.
2. **Mathematical Rating**: Evaluates raw consumption against complex pricing catalogs (flat, per-unit, volume-tiered, graduated brackets, and overage limits) calculated to exact minor currency units (cents).
3. **Double-Entry Financial Ledger**: Maintains an immutable, append-only ledger where every financial mutation enforces the fundamental accounting invariant: $\\sum \\text{Debits} == \\sum \\text{Credits}$.
4. **Automated Billing Cycles**: Reconciles usage periods, applies promotional discounts and taxes, and produces immutable invoices with gapless sequential numbers (`INV-YYYY-XXXX`).
5. **Collections & Dunning**: Manages two-step payment authorization/capture, automated collection retries, and dunning workflows with grace periods.
6. **Customer Billing Console**: A sleek, dark-mode responsive dashboard providing real-time KPI metrics, usage queries, and itemized invoice inspection.

---

### Target Users & Personas
- **Developer / Client Microservices**: High-frequency services reporting API requests, GPU runtimes, and token usage via `POST /v1/usage/events`.
- **Finance & Revenue Teams**: Accounting staff auditing ledger balances, setting price books, finalizing invoices, and tracking MRR/ARR.
- **Tenant Administrators**: B2B SaaS customers viewing current month accrued costs, downloading finalized invoices, and managing payment methods.

---

### Main User Journeys
1. **Telemetry Ingestion Journey**: Client microservice emits usage events with an idempotency key -> FastAPI validates payload and timestamp drift -> deduplication check in database -> event stored in time-partitioned table -> success response acknowledged in <15ms.
2. **Billing Period Reconciliation Journey**: End of month triggers period closure -> meter locks -> usage rollups aggregated -> rating engine computes line items across pricing tiers -> discounts and taxes calculated -> invoice finalized with sequential number -> ledger entries posted.
3. **Customer Payment & Dunning Journey**: Invoice finalized -> automated payment authorization requested -> gateway webhook verifies HMAC -> payment captured -> invoice marked `PAID`. If payment fails -> dunning workflow initiates retries at Day 0, 3, 7, and 14 with grace period tracking.

---

### Frontend Screens & Capabilities
- **Billing Dashboard (`/`)**: Displays real-time KPIs: Gross Revenue, Monthly Recurring Revenue (MRR), Annual Recurring Revenue (ARR), Active Subscriptions, and Outstanding Due Amount.
- **Invoice Explorer**: Filterable table of tenant invoices with status badges (`DRAFT`, `FINALIZED`, `PAID`, `VOID`), issue dates, due dates, and totals.
- **Interactive Invoice Inspector**: Line-item drilldown showing exact quantities, unit rates, subtotal, discounts, tax, and double-entry ledger impact.

---

## 0.2 Every Feature with Full Trace (F1 – F10)

```mermaid
flowchart TD
    subgraph Client["Client Services & Browser"]
        FE[Billing Dashboard Frontend: app.js]
        Service[Client Microservices]
    end

    subgraph API["FastAPI Gateway: api/app.py"]
        IngestRoute["POST /v1/usage/events"]
        InvoiceRoute["POST /v1/invoices"]
        RatingRoute["POST /v1/rating/calculate"]
        PaymentRoute["POST /v1/payments/authorize"]
    end

    subgraph Core["Core Business Engines"]
        Pipe[UsageIngestionPipeline: metering/ingestion.py]
        Rater[RatingEngine: rating/engine.py]
        Invoicer[InvoiceManager: invoicing/manager.py]
        Collector[PaymentCollectionsManager: payments/collections.py]
        Ledger[LedgerDatabaseManager: models/ledger.py]
        Prorater[calculate_proration: models/proration.py]
    end

    subgraph Storage["Persistent Storage"]
        EventsDB[(usage_events: Partitioned)]
        LedgerDB[(ledger_transactions & entries)]
        InvoicesDB[(invoices & line_items)]
        PriceDB[(price_book_entries)]
    end

    Service -->|HTTP POST| IngestRoute
    FE -->|HTTP GET/POST| InvoiceRoute
    IngestRoute --> Pipe
    InvoiceRoute --> Invoicer
    RatingRoute --> Rater
    PaymentRoute --> Collector

    Pipe --> EventsDB
    Invoicer --> Rater
    Invoicer --> Ledger
    Invoicer --> InvoicesDB
    Rater --> PriceDB
    Collector --> Ledger
    Ledger --> LedgerDB
```

---

### F1: Usage Event Store (`models/events.py:L14-L157`)
- **User Action**: Client service emits telemetry event with payload.
- **Frontend Flow**: N/A (headless background pipeline).
- **API Call**: `POST /v1/usage/events` with JSON payload.
- **Backend Flow**: `app.py:L60-L76` -> `UsageIngestionPipeline.ingest_event()` -> `UsageEventStore.record_event()` (`models/events.py:L53`).
- **Database Operations**: Inserts into `usage_events` with composite unique index `ix_tenant_idem (tenant_id, idempotency_key)` and non-negative check `quantity >= 0`.
- **Failure Path**: Negative quantity raises 422; duplicate key returns status `DUPLICATE` (200 OK); DB connection failure raises 500.

#### Diagrams (F1)
```mermaid
sequenceDiagram
    autonumber
    actor Svc as Client Service
    participant API as api/app.py
    participant Store as models/events.py:UsageEventStore
    participant DB as PostgreSQL usage_events

    Svc->>API: POST /v1/usage/events (idempotency_key="idemp_101")
    API->>Store: record_event(tenant_id, customer_id, qty, idempotency_key)
    Store->>DB: SELECT WHERE tenant_id=:t AND idempotency_key=:k
    alt Key Exists
        DB-->>Store: Existing Event Record
        Store-->>API: UsageEventSchema (Existing)
        API-->>Svc: 200 OK {status: "DUPLICATE"}
    else New Event
        Store->>DB: INSERT INTO usage_events VALUES (...)
        DB-->>Store: Insert Success
        Store-->>API: UsageEventSchema (New)
        API-->>Svc: 200 OK {status: "ACCEPTED"}
    end
```

---

### F2: Idempotent Event Ingestion Pipeline (`metering/ingestion.py:L123-L313`)
- **User Action**: Automated telemetry collection reporting compute seconds, API queries, or storage bytes.
- **Frontend Flow**: N/A.
- **API Call**: `POST /v1/usage/events` or `POST /v1/usage/events/batch`.
- **Backend Flow**: `UsageIngestionPipeline.validate_payload()` (`ingestion.py:L129`) -> checks timestamp drift (max 90 days past, 1 hour future) -> checks non-empty tenant/customer/event_type -> checks JSON dimensions.
- **Database Operations**: Queries `UsageEventRecord` using `select()` with `where(tenant_id == ..., idempotency_key == ...)`.
- **Failure Path**: Returns structured `IngestionResponse(status=REJECTED, error="TIMESTAMP_TOO_OLD")`.

#### Diagrams (F2)
```mermaid
stateDiagram-v2
    [*] --> IngestRequest: POST /v1/usage/events
    IngestRequest --> SchemaValidation: Check Pydantic Model
    SchemaValidation --> RejectValidation: Malformed / Negative Qty
    RejectValidation --> [*]: 422 Unprocessable Entity

    SchemaValidation --> TimestampCheck: Check Drift Window
    TimestampCheck --> RejectDrift: >90 Days Past or >1h Future
    RejectDrift --> [*]: 422 TIMESTAMP_TOO_OLD

    TimestampCheck --> IdempotencyCheck: Query DB by (tenant_id, key)
    IdempotencyCheck --> DuplicateFound: Key Exists
    DuplicateFound --> [*]: 200 OK (DUPLICATE)

    IdempotencyCheck --> PersistRecord: New Key
    PersistRecord --> [*]: 200 OK (ACCEPTED)
```

---

### F3: Multi-Tiered Dynamic Rating Engine (`rating/engine.py:L85-L193`)
- **User Action**: Invoicing cycle or quote calculation query.
- **Frontend Flow**: Frontend calls `fetch("/v1/rating/calculate")` to display price preview.
- **API Call**: `POST /v1/rating/calculate` with `{entry: PriceBookEntry, quantity: int}`.
- **Backend Flow**: `RatingEngine.rate_usage()` (`rating/engine.py:L87`) executes pricing algorithm based on `entry.pricing_type`:
  - `FLAT_FEE`: Flat integer cents charge.
  - `PER_UNIT`: $(qty - free) \\times unit\\_price + flat\\_fee$.
  - `TIERED_VOLUME`: Matches total volume to single tier bucket; all billable units billed at that tier rate.
  - `GRADUATED_BRACKET`: Slices volume into incremental brackets, rating each bracket independently.
  - `OVERAGE`: Base fee covers included units; excess billed at overage unit rate.
  - Enforces `min_charge_cents` floor and `max_charge_cents` ceiling.
- **Database Operations**: Reads `price_book_entries` via `PriceBookManager.get_entries_for_plan()`.
- **Failure Path**: Negative quantity or empty tiers raises `ValueError` (400 Bad Request).

#### Diagrams (F3)
```mermaid
flowchart TD
    Qty[Input Usage Quantity] --> Free[Deduct Free Units: min qty, free_units]
    Free --> Type{Pricing Type?}
    Type -->|FLAT_FEE| Flat[Total = Flat Fee]
    Type -->|PER_UNIT| Unit[Total = Billable * Unit Price + Flat]
    Type -->|TIERED_VOLUME| Vol[Find Bucket for Total Billable -> Rate All Units at Tier Rate]
    Type -->|GRADUATED_BRACKET| Grad[Slice Units Across Brackets -> Sum Bracket Subtotals]
    Type -->|OVERAGE| Over[Billable > Included? Rate Excess Units + Flat]
    
    Flat --> FloorCeil[Check Minimum Floor & Maximum Ceiling]
    Unit --> FloorCeil
    Vol --> FloorCeil
    Grad --> FloorCeil
    Over --> FloorCeil
    FloorCeil --> Item[Return RatingLineItem in Exact Integer Cents]
```

---

### F4: Append-Only Double-Entry Ledger (`models/ledger.py:L63-L436`)
- **User Action**: Internal financial events (invoice finalization, payment capture, refund, bad debt write-off).
- **Backend Flow**: `LedgerDatabaseManager.record_transaction()` (`ledger.py:L67`).
- **Invariant Enforcement**:
  - `len(entries) >= 2`.
  - Every entry has `amount_cents > 0`.
  - $\\sum \\text{Debits} == \\sum \\text{Credits}$.
- **Database Operations**: Inserts 1 row into `ledger_transactions` and $N$ rows into `ledger_entries` within an atomic transaction.
- **Failure Path**: If debits $\\neq$ credits, raises `ValueError` ("Double-entry invariant violated"); database aborts transaction.

#### Diagrams (F4)
```mermaid
erDiagram
    ledger_transactions ||--|{ ledger_entries : "contains >= 2"
    ledger_transactions {
        string transaction_id PK
        string tenant_id
        string reference_id
        string description
        timestamp posted_at
    }
    ledger_entries {
        string entry_id PK
        string transaction_id FK
        string account_id
        string entry_type "DEBIT or CREDIT"
        bigint amount_cents "amount_cents > 0"
    }
```

---

### F5: Invoicing Engine & Lifecycle (`invoicing/manager.py:L140-L421`)
- **User Action**: Billing manager clicks "Finalize Invoice" in UI or scheduled cron job executes period close.
- **Frontend Flow**: `app.js:finalizeInvoice(invoiceId)` sends POST request -> updates state -> re-renders DOM with finalized number.
- **API Call**: `POST /v1/invoices/{invoice_id}/finalize`.
- **Backend Flow**: `InvoiceManager.finalize_invoice()` (`manager.py:L260`):
  1. Checks invoice is in `DRAFT` status (raises error if already finalized/void).
  2. Aggregates all line items: $subtotal = \\sum line\\_items$.
  3. Applies tax and discounts: $total = subtotal - discounts - credits + tax$.
  4. Assigns gapless sequential number (`INV-YYYY-XXXX`) via `InvoiceSequenceRecord`.
  5. Syncs to double-entry ledger: Debits Accounts Receivable (`AR`), Credits Revenue (`REV`).
  6. Sets status to `FINALIZED` and stamps `finalized_at`.
- **Failure Path**: Finalizing an already finalized invoice returns 400 Bad Request; line-item additions to non-draft invoices are rejected.

#### Diagrams (F5)
```mermaid
stateDiagram-v2
    [*] --> DRAFT: create_draft_invoice()
    DRAFT --> DRAFT: add_line_item()
    DRAFT --> FINALIZED: finalize_invoice() [Locks Items, Assigns Seq No, Posts Ledger]
    FINALIZED --> PAID: capture_payment() [Records Settlement]
    FINALIZED --> VOID: void_invoice() [Reversing Ledger Transaction]
    PAID --> [*]
    VOID --> [*]
```

---

### F6: Payments, Retries & Dunning (`payments/collections.py:L65-L334`)
- **User Action**: Automatic charge on invoice due date or customer clicks "Pay Now".
- **API Call**: `POST /v1/payments/authorize` -> `POST /v1/payments/{payment_id}/capture`.
- **Backend Flow**: `PaymentCollectionsManager.authorize_payment()` checks idempotency key -> generates gateway hold -> `capture_payment()` settles funds -> updates invoice to `PAID` -> posts ledger entry (Debit Cash, Credit AR).
- **Dunning Workflow**: If payment fails -> `execute_dunning_step()` transitions stage:
  - Attempt 1: Day 0 (Immediate notification).
  - Attempt 2: Day 3 (Retry charge).
  - Attempt 3: Day 7 (Final notice).
  - Final Escalation: Day 14 (Account standing transitions from `PAST_DUE` to `SUSPENDED`).
- **Failure Path**: Gateway card decline logs `PaymentAttemptRecord` with error code; does not crash workflow.

---

### F7: Aggregation & Billing Periods (`aggregation/periods.py:L130-L414`)
- **User Action**: Customer queries monthly usage breakdown in dashboard.
- **API Call**: `GET /v1/usage/query?start_date=...&end_date=...`.
- **Backend Flow**: `UsageAggregator.recompute_from_scratch()` runs SQL `SUM(quantity)` over raw `usage_events` in window; differential testing compares pre-aggregated `usage_rollups` with raw recompute.
- **Period Close**: `close_period()` updates status to `CLOSED`, locking window from further event attachment. Late events arriving for closed periods are redirected to current open period as prior-period adjustments.

---

### F8: Subscription Lifecycle & Proration (`models/proration.py:L31-L77`, `models/accounts.py`)
- **User Action**: Tenant upgrades subscription plan mid-cycle (e.g., from $50/mo Basic to $200/mo Pro on day 15 of 30).
- **API Call**: `POST /v1/subscriptions/{id}/upgrade`.
- **Backend Flow**: `calculate_proration()` calculates exact elapsed seconds vs total period seconds using Python `Decimal`:
  $$fraction = \\frac{remaining\\_seconds}{total\\_seconds}$$
  $$unused\\_credit = \\text{ROUND\\_HALF\\_UP}(old\\_rate \\times fraction)$$
  $$new\\_charge = \\text{ROUND\\_HALF\\_UP}(new\\_rate \\times fraction)$$
  $$net\\_proration = new\\_charge - unused\\_credit$$
- **Precision Guarantee**: Cents precision with zero floating-point accumulation drift.

---

### F9: Security, RBAC & Audit Logging (`security/auth.py`, `security/audit.py`)
- **User Action**: Any authenticated API call or mutation.
- **Backend Flow**: `AuthManager.validate_api_key()` resolves SHA-256 key hash, verifies non-revoked status, checks role permissions (`OWNER`, `FINANCE`, `VIEWER`, `SERVICE`). Deny-by-default for cross-tenant access.
- **Audit Logging**: `AuditLogManager.log_mutation()` records actor, action, timestamp, and recursively masks PII, Tax IDs, and card numbers via regex redaction before DB write.

---

### F10: Customer Billing Console Frontend (`frontend/src/app.js`, `index.html`, `index.css`)
- **User Action**: Customer interacts with browser UI to view KPIs, filter invoices, and inspect line items.
- **Frontend Flow**: `app.js` runs event listeners -> issues `fetch()` to `API_BASE` -> updates client-side `state` object -> manipulates DOM with formatted values (`formatCents`).
- **Responsive Theme**: Vanilla CSS custom properties (`--bg-black: #000000`, `--accent-indigo: #6366f1`) providing pure-black high-contrast styling.

---

## 0.3 Every API & Secret Inventory

### Backend Endpoints Table
| Method | Path | Auth / Role | Controller / Function | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/health` | Public | `health()` (`app.py:L45`) | Liveness check and database ping |
| `POST` | `/v1/usage/events` | Service / Owner | `ingest_single_event()` (`app.py:L60`) | Ingests single metered usage event with idempotency |
| `POST` | `/v1/usage/events/batch` | Service / Owner | `ingest_batch_events()` (`app.py:L78`) | Ingests array of usage events in single transaction |
| `GET` | `/v1/usage/events` | Viewer / Finance | `query_events()` (`app.py:L90`) | Lists raw usage events by tenant and customer |
| `POST` | `/v1/invoices` | Finance / Owner | `create_draft_invoice()` (`app.py:L128`) | Creates a draft invoice shell |
| `POST` | `/v1/invoices/{id}/items` | Finance / Owner | `add_invoice_item()` (`app.py:L146`) | Appends line item to draft invoice |
| `POST` | `/v1/invoices/{id}/finalize` | Finance / Owner | `finalize_invoice()` (`app.py:L168`) | Locks invoice, generates seq number, posts ledger |
| `GET` | `/v1/invoices/{id}` | Viewer / Finance | `get_invoice_details()` (`app.py:L183`) | Retrieves full invoice details and line items |
| `GET` | `/v1/invoices` | Viewer / Finance | `list_invoices()` (`app.py:L198`) | Queries invoices with customer & status filters |
| `GET` | `/v1/dashboard/summary` | Viewer / Finance | `get_dashboard_summary()` (`app.py:L227`)| Aggregates MRR, ARR, and gross revenue KPIs |
| `POST` | `/v1/meters` | Owner | `create_meter()` (`app.py:L279`) | Registers a new usage meter dimension |
| `GET` | `/v1/meters` | Viewer | `list_meters()` (`app.py:L308`) | Lists all registered meters for tenant |
| `POST` | `/v1/rating/calculate` | Public / Calc | `calculate_rate()` (`app.py:L328`) | Evaluates price book rules against quantity |
| `POST` | `/v1/rating/price-books` | Finance / Owner | `add_price_book_entry()` (`app.py:L336`)| Adds tiered or graduated price book entry |
| `GET` | `/v1/usage/query` | Viewer / Finance | `query_aggregated_usage()` (`app.py:L375`)| Computes aggregated usage quantity in date window |
| `POST` | `/v1/payments/authorize` | Service / Finance | `authorize_payment_endpoint()` (`app.py:L423`)| Places payment hold with idempotency key |
| `POST` | `/v1/payments/{id}/capture` | Service / Finance | `capture_payment_endpoint()` (`app.py:L448`)| Settles authorized payment and marks invoice paid |
| `POST` | `/v1/subscriptions` | Finance / Owner | `create_subscription()` (`app.py:L488`)| Creates customer subscription record |
| `POST` | `/v1/subscriptions/{id}/upgrade`| Finance / Owner | `upgrade_subscription()` (`app.py:L517`)| Executes mid-cycle upgrade with exact proration |

---

### External Services & Environment Configuration
| Variable Name | Service | Purpose | Where Read in Code | Where to Obtain |
| :--- | :--- | :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL 16 | Primary relational and partitioned ledger store | `db/database.py:L15` | Cloud Postgres provider (AWS RDS, Supabase, Neon) |
| `REDIS_URL` | Redis 7.2 | Real-time usage counters & idempotency cache | `aggregation/counters.py:L20` | Upstash, AWS ElastiCache, local redis-server |
| `API_PORT` | FastAPI Host | Application listening port (default `8190`) | `api/app.py` / CLI entry | Local environment configuration |
| `PAYMENT_GATEWAY_SECRET`| Mock / Stripe | HMAC webhook signing verification secret | `payments/manager.py` | Payment provider developer console |
| `ENCRYPTION_KEY` | AES-256 | Token and secret encryption at rest | `security/auth.py` | Generated via `openssl rand -hex 32` |

---

## 0.4 Middleware, Helpers & Shared Modules
- **FastAPI Lifespan Context (`app.py:L23-L27`)**: Calls `init_db()` on application startup to ensure schema tables and indexes are ready.
- **CORS Middleware (`app.py:L36-L42`)**: Permits cross-origin requests from the billing dashboard console (`allow_origins=["*"]`, `allow_methods=["*"]`).
- **Database Session Dependency (`db/database.py:L34`)**: Asynchronous generator yielding `AsyncSession` instances, automatically handling commit/rollback and connection release.
- **Clock Simulator (`clock.py`)**: Controllable manual clock interface enabling time-travel testing for dunning schedules and billing period closes.
- **Audit Masking Helper (`security/audit.py:L23-L42`)**: Recursive dictionary sanitizer removing credit card patterns and tax IDs.

---

## 0.5 System Connections & Protocols
- **Frontend to Backend**: RESTful JSON over HTTP/1.1; base URL configured via `API_BASE = "http://localhost:8190"`.
- **Backend to Database**: SQLAlchemy 2.0 Async with `asyncpg` (PostgreSQL) or `aiosqlite` (SQLite), utilizing async connection pooling (`pool_size=20`, `max_overflow=10`).
- **Backend to Cache**: Async Redis client utilizing connection pooling and atomic increments (`INCRBY`).
- **Internal Ledger Synchronization**: Transactional hooks binding invoice finalization and payment captures directly to double-entry ledger journal creation.

---

## 0.6 Additional Platform Capabilities
- **Time Partitioning Engine (`metering/partitioning.py`)**: Creates and manages monthly partitions for `usage_events`, preventing single-table index bloat.
- **Unit Conversion Engine (`metering/ingestion.py:L42-L69`)**: Handles mathematical conversions between Bytes, Kilobytes, Megabytes, Gigabytes, Milliseconds, Seconds, Minutes, and Hours.
- **Gapless Sequence Counter (`invoicing/manager.py:L245-L260`)**: Row-level locking counter ensuring zero gaps in legal fiscal invoice numbering.

---

## 0.7 Connection Map

```mermaid
flowchart TB
    subgraph Frontend["Frontend Layer"]
        UI[Billing Console: index.html + app.js]
    end

    subgraph API_Layer["API Gateway Layer"]
        FastAPI[FastAPI Application: api/app.py]
        Auth[Auth & RBAC: security/auth.py]
    end

    subgraph Processing["Processing & Domain Engines"]
        Ingestion[Idempotent Ingestion: metering/ingestion.py]
        Rating[Rating Engine: rating/engine.py]
        Invoicing[Invoice Manager: invoicing/manager.py]
        Ledger[Ledger Manager: models/ledger.py]
        Proration[Proration Calculator: models/proration.py]
        Payments[Collections & Dunning: payments/collections.py]
    end

    subgraph Data_Layer["Storage & Cache Layer"]
        Redis[(Redis 7.2: Real-time Counters)]
        Postgres[(PostgreSQL 16: Partitioned Tables & Ledgers)]
    end

    UI -->|HTTP / JSON| FastAPI
    FastAPI --> Auth
    Auth --> Ingestion
    Auth --> Invoicing
    Auth --> Payments

    Ingestion -->|Atomic Ingestion| Postgres
    Ingestion -->|Fast Counters| Redis
    Invoicing -->|Evaluate Pricing| Rating
    Invoicing -->|Prorate Plans| Proration
    Invoicing -->|Post Double-Entry| Ledger
    Payments -->|Record Transactions| Ledger
    Ledger -->|Append-Only| Postgres
    Invoicing -->|Finalize Invoices| Postgres
```

---

## 0.8 Final Inventory Counts
To ensure total architectural consistency across all subsequent documentation:
- **Total Frontend Pages / Consoles**: 1 (Single-Page Interactive Billing Console with 3 functional views)
- **Total Frontend Components / Views**: 4 (KPI Dashboard, Invoice List, Line Item Explorer, Settlement Modal)
- **Total Backend Endpoints**: 19 REST endpoints across 6 resource groups
- **Total Database Models**: 15 relational tables (`usage_events`, `invoices`, `invoice_line_items`, `invoice_sequences`, `ledger_transactions`, `ledger_entries`, `price_book_entries`, `plan_versions`, `meters`, `billing_periods`, `usage_rollups`, `payments`, `payment_attempts`, `dunning_workflows`, `audit_logs`)
- **Total Unit & Integration Tests**: 87 passing automated tests across 52 test files
- **Total Middleware / Interceptors**: 2 (Lifespan DB Initializer, Starlette CORSMiddleware)
- **Total Implemented Features (F-Series)**: 10 Major Feature Groups spanning 90 specification checklist IDs
""")

    # 3. 00b-project-pitch.md
    with open(os.path.join(docs_dir, "00b-project-pitch.md"), "w") as f:
        f.write("""# Project Pitch: Real-Time Usage & Metered Billing Engine

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
""")

    # 4. 00-project-map.md
    with open(os.path.join(docs_dir, "00-project-map.md"), "w") as f:
        f.write("""# Project Structure & Technology Map

## File Hierarchy

```
19-usage-billing-engine/
├── backend/                            # Asynchronous Python Backend
│   ├── src/                            # Production Source Code
│   │   ├── aggregation/                # Period lifecycle & rollup aggregation
│   │   │   ├── counters.py             # Redis-backed real-time usage counters
│   │   │   └── periods.py              # Billing period states (OPEN/CLOSING/CLOSED) & rollups
│   │   ├── api/                        # REST API routing & application entry
│   │   │   └── app.py                  # FastAPI route handlers, dependencies, and schemas
│   │   ├── clock.py                    # Mockable manual clock for testing dunning & period close
│   │   ├── db/                         # Database initialization & session management
│   │   │   └── database.py             # SQLAlchemy async engine, sessionmaker, and Base
│   │   ├── invoicing/                  # Billing cycle closure & invoice generation
│   │   │   ├── engine.py               # Invoicing stub / dispatch interfaces
│   │   │   └── manager.py              # Gapless numbering, line items, and finalization
│   │   ├── metering/                   # Ingestion pipeline & data partitioning
│   │   │   ├── ingestion.py            # Event validation, deduplication, and unit conversions
│   │   │   └── partitioning.py         # PostgreSQL monthly range partitioning engine
│   │   ├── models/                     # Relational & financial domain schemas
│   │   │   ├── accounts.py             # Customers, subscriptions, and lifecycle states
│   │   │   ├── billing.py              # Account billing schedules & payment settings
│   │   │   ├── events.py               # UsageEventRecord & UsageEventStore
│   │   │   ├── ledger.py               # Double-entry ledger transactions & debit/credit entries
│   │   │   ├── meters.py               # Meter definitions & aggregation types (SUM/COUNT/MAX)
│   │   │   ├── plan_versions.py        # Versioned pricing plans with immutability locks
│   │   │   └── proration.py            # Pro-rata math for mid-cycle plan changes
│   │   ├── payments/                   # Payment collections & dunning workflows
│   │   │   ├── collections.py          # Authorization, capture, retries, and dunning stages
│   │   │   └── manager.py              # PaymentRecord schema & webhook idempotency
│   │   ├── rating/                     # Mathematical rating & pricing catalog
│   │   │   └── engine.py               # Tiered, graduated, overage, and flat rating engine
│   │   ├── reporting/                  # Financial & business intelligence reporting
│   │   │   └── metrics.py              # Gross/Net revenue, MRR, ARR, and ARPU calculators
│   │   └── security/                   # Authentication, RBAC & audit compliance
│   │       ├── audit.py                # Audit log manager with automatic PII/Tax-ID redaction
│   │       └── auth.py                 # API key hashing (SHA-256) & deny-by-default RBAC
│   └── tests/                          # Automated Pytest Suite (50 test files, 87 tests)
│       ├── test_aggregation_and_periods.py
│       ├── test_backend_apis_and_services.py
│       ├── test_billing_and_rating.py
│       ├── test_database_distributed_infrastructure.py
│       ├── test_invoicing.py
│       ├── test_ledger_and_financial_integrity.py
│       ├── test_payments_and_collections.py
│       ├── test_security_and_audit.py
│       └── test_subscription_lifecycle_proration.py
├── frontend/                           # Customer Billing Console
│   ├── src/
│   │   ├── app.js                      # Client state management, API client, DOM renderer
│   │   ├── index.css                   # Responsive dark-mode styling with pure-black variables
│   │   └── index.html                  # Single-page console layout & KPI cards
│   └── tests/                          # Frontend integration test files
│       ├── test_billing_dashboard_and_invoice_list.py
│       └── test_invoice_detail_console.py
├── docs/                               # Vue.js-Style Documentation Suite (VitePress)
│   ├── .vitepress/                     # VitePress site configuration & dark theme
│   ├── features/                       # Deep-dive documentation for all features F1-F10
│   ├── system-design/                  # 18-chapter financial systems design guide
│   └── ...                             # Reference guides, Q&A, and checklists
├── package.json                        # Root documentation dependencies (VitePress, Mermaid)
├── FEATURES.csv                        # 90-feature specification matrix
├── PROGRESS.md                         # Implementation progress & test traceability log
└── SPEC.txt                            # System design specification & financial invariants
```

---

## Technology Stack Detected

| Component | Technology | Exact Version | Purpose in Codebase |
| :--- | :--- | :--- | :--- |
| **Runtime Language** | Python | `3.13.9` | Primary backend runtime providing modern typing and asyncio |
| **API Framework** | FastAPI | `>=0.110.0` | Asynchronous high-performance REST routing and OpenAPI generation |
| **Data Validation** | Pydantic v2 | `>=2.6.0` | Strict schema validation, timestamp parsing, and serialization |
| **ORM / Query Builder**| SQLAlchemy | `>=2.0.28` | Asynchronous relational mapping and SQL query abstraction |
| **Database Driver** | aiosqlite / asyncpg | `>=0.20.0` | Asynchronous database connection drivers |
| **Cache Driver** | redis-py | `>=5.0.0` | Asynchronous Redis client for counters and idempotency |
| **Test Runner** | Pytest | `8.4.2` | Test execution framework with `pytest-asyncio` plugin |
| **Frontend Core** | Vanilla ES6+ | Native Browser | High-speed, dependency-free DOM manipulation and state management |
| **Documentation Site** | VitePress | `^1.6.4` | Static documentation site generator with pure-black dark theme |
| **Diagram Engine** | Mermaid.js | `^11.4.1` | Client-side vector diagram rendering for architecture flows |

---

## Environment Variables & Configuration

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | String | `sqlite+aiosqlite:///./billing.db` | Primary database connection string (SQLite for dev, Postgres for prod) |
| `REDIS_URL` | String | `redis://localhost:6319/0` | Redis instance for real-time usage counters |
| `API_PORT` | Integer | `8190` | HTTP port on which the FastAPI application listens |
| `FRONTEND_PORT` | Integer | `5190` | HTTP port for serving static frontend assets |
| `APP_ENV` | String | `development` | Runtime environment (`development`, `staging`, `production`) |
| `LOG_LEVEL` | String | `INFO` | Output log verbosity |

---

## Entry Points
- **Backend Application Entry**: `backend/src/api/app.py` (run via `uvicorn api.app:app --port 8190 --reload`).
- **Frontend Entry**: `frontend/src/index.html` (served via any static web server on port `5190`).
- **Test Suite Entry**: `PYTHONPATH=backend/src pytest` at repository root.
- **Documentation Site Entry**: `npm run docs:dev` or `npm run docs:build`.
""")

    print("Overview documents generated successfully.")
