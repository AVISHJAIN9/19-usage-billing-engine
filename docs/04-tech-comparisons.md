# Technology Choices & Exhaustive Comparisons

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
