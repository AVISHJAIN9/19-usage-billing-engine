# Project Structure & Technology Map

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
