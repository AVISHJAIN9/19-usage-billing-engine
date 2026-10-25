# Technical Interview Questions & Answers (150+ Questions)

This comprehensive interview guide prepares engineers to defend every design decision, algorithmic choice, and financial invariant implemented in `19-usage-billing-engine`.

---

## 1. Project Overview & Executive Pitch

### Q1: Walk me through your project in 3 minutes.
**Answer**:
"I built **19-Usage-Billing-Engine**, an asynchronous metered billing and financial rating engine written in Python 3.13, FastAPI, PostgreSQL 16, and Vanilla JavaScript.
The platform solves the central challenge of usage-based pricing: converting high-frequency consumption events—like API calls, database storage, and compute seconds—into mathematically exact, audit-compliant customer invoices.
At the ingestion layer, client microservices emit usage events with cryptographic idempotency keys. In `metering/ingestion.py`, our pipeline validates the payload schema, verifies that timestamps fall within a valid 90-day window, and checks a composite database index. If network timeouts cause a client to retry, the duplicate is recognized in constant time and acknowledged without double-billing.
At the rating layer, in `rating/engine.py`, our engine evaluates raw usage against versioned price books. It supports diverse billing models: flat subscriptions, per-unit metering, volume discounts, and graduated slab tiers. All calculations are executed in integer minor units (cents) or fixed-point Decimal arithmetic with `ROUND_HALF_UP`, completely eliminating floating-point rounding drift.
At the accounting layer, in `models/ledger.py`, the system maintains an immutable double-entry ledger. Every invoice finalization or payment capture writes a balanced transaction requiring that the sum of debits strictly equals the sum of credits across at least two entries.
At period close, in `invoicing/manager.py`, the engine locks customer meters, aggregates line items, applies taxes and discounts, and uses row-level locking on sequence counters to assign a gapless legal invoice number like `INV-2026-0042`.
The customer console provides real-time visibility into MRR, ARR, and line-item breakdowns. The entire codebase is verified by 87 automated tests running via Pytest."

### Q2: Give me your 60-second elevator pitch.
**Answer**:
"I designed and built an enterprise metered billing and rating engine that processes millions of raw consumption events into exact customer invoices. It features an idempotent ingestion pipeline that guarantees exactly-once accounting under network retries, a mathematical rating engine supporting complex tiered and graduated pricing models, and an append-only double-entry ledger that strictly enforces debit-credit conservation. It handles gapless invoice numbering, second-exact mid-cycle subscription proration, and automated dunning workflows."

### Q3: What core business problem does this engine solve?
**Answer**:
"As companies shift from flat SaaS subscriptions to usage-based pricing, billing errors become their largest revenue risk. Out-of-order event delivery causes missing charges, network retries cause double-billing, floating-point rounding errors lead to discrepancies on tax filings, and mid-cycle plan upgrades result in customer disputes. This engine eliminates these risks through database-level idempotency, exact integer arithmetic, and double-entry accounting guarantees."

### Q4: Who are the primary users of this system?
**Answer**:
"There are three primary personas:
1. **Developer Services**: Microservices reporting consumption via high-throughput HTTP endpoints.
2. **Finance & Accounting Teams**: Internal staff managing pricing tiers, auditing ledger journals, and finalizing invoices.
3. **Tenant Customers**: B2B clients viewing real-time accrued charges and downloading finalized invoices."

### Q5: What makes metered billing fundamentally harder than traditional subscription billing?
**Answer**:
"In subscription billing, charges are static and known in advance (e.g., $50 on the 1st of every month). In metered billing:
1. Volume is unpredictable and arrives in millions of discrete events.
2. Events arrive out of order and across network boundaries.
3. Rating logic is non-linear (graduated tiers where price changes dynamically as volume increases).
4. Billing periods must lock usage before rating to prevent race conditions from concurrent incoming events."

### Q6: What is the hardest function in the codebase? Explain it line by line.
**Answer**:
"The hardest function is `calculate_proration()` in `models/proration.py:L31-L77`.
- **Lines 42-49**: Normalizes all datetimes (`period_start`, `period_end`, `effective_time`) to UTC and clamps the effective time within the period boundaries to prevent negative time intervals.
- **Lines 51-56**: Calculates `total_seconds` and `remaining_seconds` as `Decimal` objects:
  `remaining_seconds = Decimal(str((period_end - effective_time).total_seconds()))`.
  Using `str()` conversion is critical because converting a float directly into `Decimal` retains IEEE 754 precision artifacts.
- **Line 56**: Computes the exact time fraction: `fraction = remaining_seconds / total_seconds`.
- **Line 59**: Computes unused credit from the old plan:
  `(Decimal(old_plan_price_cents) * fraction).quantize(Decimal('1'), rounding=ROUND_HALF_UP)`.
  This calculates the exact cents owed back to the customer, rounded using bankers' rounding standards.
- **Line 61**: Computes new plan charge for the remaining period:
  `(Decimal(new_plan_price_cents) * fraction).quantize(Decimal('1'), rounding=ROUND_HALF_UP)`.
- **Lines 63-65**: Subtracts `unused_credit` from `new_charge` to yield `net_proration_cents`. This produces exact integer cents with zero rounding drift."

### Q7: What bugs did you encounter during development and how did you resolve them?
**Answer**:
"The most difficult bug was a race condition in gapless invoice numbering. Under concurrent finalization requests, multiple workers read the same sequence number from the database and attempted to insert duplicate invoice numbers, causing unique constraint violations.
I solved this in `invoicing/manager.py:L245` by introducing a dedicated `invoice_sequences` table and acquiring an exclusive row lock using SQLAlchemy's `.with_for_update()`. This serialized the finalization queue without locking the entire invoices table."

### Q8: What would you change if you rebuilt this system from scratch?
**Answer**:
"I would place an Apache Kafka or AWS Kinesis stream in front of the ingestion pipeline. Currently, events hit FastAPI and perform synchronous PostgreSQL inserts. While adequate up to 5,000 events/second, scaling to 100,000 events/second requires streaming ingestion where events are batched into micro-shards before hitting relational storage."

### Q9: Why did you choose Python and FastAPI instead of Go or Node.js?
**Answer**:
"FastAPI gave us asynchronous performance comparable to Node.js via uvloop, but with two decisive advantages for fintech:
1. Pydantic v2's compile-time data validation for incoming telemetry.
2. Python's native `Decimal` module and data-science ecosystem for pricing modeling and spend forecasting."

### Q10: How do you prevent floating-point rounding errors in calculations?
**Answer**:
"We enforce a zero-float policy across all financial paths. All balances, unit prices, line items, and totals are represented as integer minor units (cents) stored in SQL `BIGINT` columns. Where fractional rates occur (e.g. $0.0015 per API call), we use Python's `Decimal` type with explicit `.quantize(Decimal('1'), rounding=ROUND_HALF_UP)`."

### Q11: How is multi-tenancy handled in this architecture?
**Answer**:
"We implement row-level multi-tenancy. Every core database table (`usage_events`, `invoices`, `ledger_transactions`, `api_keys`) includes an indexed `tenant_id` column. All database queries must include `WHERE tenant_id = :tenant_id`, and our authentication layer enforces deny-by-default cross-tenant isolation."

### Q12: How does the system handle late or out-of-order events?
**Answer**:
"Events carry an event timestamp representing when consumption occurred, distinct from ingestion timestamp. If an event arrives for an open billing period, it is aggregated normally. If it arrives after that period has closed, our period engine routes the event into the customer's *current* open period as a prior-period adjustment line item."

### Q13: What is the difference between volume pricing and graduated pricing?
**Answer**:
"In **Volume Pricing**, the achieved tier determines the price for *all* units. For example, if Tier 1 (1-100) is $0.10 and Tier 2 (101+) is $0.05, consuming 150 units costs $150 \times $0.05 = $7.50$.
In **Graduated (Bracket) Pricing**, usage is sliced across progressive tiers. The first 100 units cost $0.10 ($10), and the remaining 50 units cost $0.05 ($2.50), totaling $12.50."

### Q14: How do you ensure legal compliance with gapless invoice numbering?
**Answer**:
"Fiscal regulations in Germany, France, and other jurisdictions require that invoice numbers have no gaps (e.g., `INV-2026-0001`, `0002`). We maintain an `invoice_sequences` row per tenant and year. During finalization, the worker acquires an exclusive row lock (`SELECT ... FOR UPDATE`), increments the counter, and assigns the number within the same transaction that finalizes the invoice."

### Q15: How does the double-entry ledger maintain integrity if a worker crashes?
**Answer**:
"Every ledger transaction and its constituent entries (at least 2 entries) are inserted inside a single ACID database transaction. If the worker crashes or debits do not equal credits, the database rolls back the transaction, leaving no partial or orphaned ledger entries."

---

## 2. System Architecture & High-Scale Design

### Q16: Describe the high-level architecture of the platform.
**Answer**:
"It is a layered asynchronous architecture:
1. **API Gateway Layer**: FastAPI application managing auth, rate limiting, and REST routing.
2. **Ingestion & Validation Engine**: Asynchronous pipeline validating schemas and checking idempotency.
3. **Rating & Pricing Engine**: Pure in-memory rating logic calculating tiered and graduated totals.
4. **Billing & Invoicing Manager**: Manages period lifecycles, locks meters, and aggregates invoices.
5. **Double-Entry Ledger**: Append-only transaction journal enforcing balance conservation.
6. **Storage Layer**: PostgreSQL 16 time-partitioned tables and Redis for real-time counters."

### Q17: Why is the express/FastAPI app separated from the server runner?
**Answer**:
"In `api/app.py`, the `FastAPI()` application instance, routers, and middleware are defined without calling `uvicorn.run()`. This separation allows test suites (like `pytest`) to mount the app directly via `httpx.AsyncClient` without binding to physical network ports, and enables production deployments to run multi-worker process managers like Gunicorn."

### Q18: How do you partition the usage events table in PostgreSQL?
**Answer**:
"We use PostgreSQL declarative range partitioning by month on the `timestamp` column:
`CREATE TABLE usage_events (...) PARTITION BY RANGE (timestamp);`
Partitions are created for each calendar month (e.g., `usage_events_2026_10`). When querying by date range, PostgreSQL performs partition pruning, scanning only relevant month tables rather than a multi-billion row table."

### Q19: What happens when usage event volume grows from 500/sec to 50,000/sec?
**Answer**:
"At 50,000/sec:
1. Synchronous database writes would saturate disk IOPS.
2. We decouple ingestion by placing Apache Kafka in front of workers.
3. Workers batch 1,000 events into single SQL `INSERT ... VALUES` statements.
4. Redis Bloom filters are used for sub-millisecond idempotency deduplication before touching PostgreSQL."

### Q20: Explain the CAP theorem trade-offs in this billing engine.
**Answer**:
"Billing engines are firmly CP systems (Consistency and Partition Tolerance). In financial accounting, an inconsistent state (like double-charging a customer or losing track of ledger balances) is legally and commercially unacceptable. If a network partition occurs between database replicas, we reject writes rather than accept unverified usage."

### Q21: What is differential testing and how do you use it for aggregation?
**Answer**:
"Differential testing verifies an optimized system against an unoptimized reference implementation. In `aggregation/periods.py`, we pre-aggregate usage into hourly rollups for fast UI queries. During period close, our test executes `recompute_from_scratch()`, which executes a direct SQL `SUM()` over raw usage events, proving mathematically that cached rollups equal raw telemetry."

### Q22: What caching strategy is applied to usage counters?
**Answer**:
"We use a Write-Through caching strategy with Redis. When events are ingested, raw events are written to PostgreSQL while Redis atomic counters (`INCRBY`) are updated for real-time dashboard meters. The database remains the authoritative persistent source of truth."

### Q23: How do you prevent cache stampede during end-of-month billing?
**Answer**:
"When hundreds of billing periods close simultaneously, workers do not query dynamic cache keys. Instead, closing periods read from immutable database snapshots using cursor-based pagination, completely avoiding cache stampede or thundering herd problems."

### Q24: What is the purpose of the manual clock simulator in `clock.py`?
**Answer**:
"Billing schedules (like 30-day invoice due dates and 14-day dunning grace periods) cannot be tested reliably using `time.sleep()`. The `ManualClock` provides an injectable time provider that allows automated test suites to fast-forward days or weeks in milliseconds to verify dunning state transitions deterministically."

### Q25: Why is the usage ledger append-only?
**Answer**:
"In financial accounting, you never delete or update historical entries. If an invoice was billed incorrectly, modifying the original record destroys the audit trail. Instead, an append-only ledger records a new *reversing entry* or adjustment transaction, ensuring full traceability for SOC 1 and SOX compliance."

---

## 3. Core Feature Implementations & Code Deep Dives

### Q26: Explain the graduated tier rating algorithm in `rating/engine.py`.
**Answer**:
"The algorithm sorts tiers by upper bound (`up_to`). It maintains a `remaining` counter equal to billable units. For each tier, it computes the bracket size (`up_to - prev_bound`). It charges `min(remaining, bracket_size)` at that tier's unit price, decrements `remaining`, and advances `prev_bound`. Any remaining units past the highest bound are charged at the unbounded top tier rate."

### Q27: How does `convert_usage_unit` handle incompatible unit conversions?
**Answer**:
"In `metering/ingestion.py:L42-L69`, the converter maintains discrete multiplier tables for storage (Bytes to GB) and time (Milliseconds to Hours). If a caller attempts to convert an incompatible dimension—such as Megabytes to Seconds—the function detects that the units belong to different multiplier tables and raises a `ValueError('Incompatible unit conversion')`."

### Q28: How does the system enforce minimum charge floors and maximum caps?
**Answer**:
"In `rating/engine.py:L166-L178`, after calculating line item subtotal and flat fees:
1. If `min_charge_cents > 0` and `total_cents < min_charge_cents`, total is clamped to `min_charge_cents` and `min_charge_applied` flag is set to true.
2. If `max_charge_cents` is defined and `total_cents > max_charge_cents`, total is clamped to `max_charge_cents` and `max_charge_applied` flag is set to true."

### Q29: What happens when an idempotency key is submitted with a different payload?
**Answer**:
"Our unique index `ix_tenant_idem` enforces uniqueness on `(tenant_id, idempotency_key)`. If a duplicate key arrives, the system queries the existing event and verifies attributes. If parameters differ, it returns the original cached record or raises an idempotency conflict error, preventing payload substitution attacks."

### Q30: How does `SubscriptionLifecycleManager` handle plan version immutability?
**Answer**:
"In `models/plan_versions.py`, when an invoice is finalized against a plan version, the plan record's `is_locked` boolean is set to true. Any subsequent attempt to modify rates or tiers on that plan ID automatically increments the version counter (`v1 -> v2`), ensuring historical invoices remain tied to immutable snapshots."

### Q31: How does the dunning engine transition accounts from `PAST_DUE` to `SUSPENDED`?
**Answer**:
"In `payments/collections.py:L65-L334`, each dunning record stores a `grace_period_until` timestamp (e.g. 14 days after invoice due date). When `execute_dunning_step()` is invoked, if the current timestamp exceeds `grace_period_until` and payment remains uncollected, `account.standing` is updated to `SUSPENDED` and an audit entry is generated."

### Q32: Explain the two-step payment authorization and capture flow.
**Answer**:
"1. `authorize_payment()` contacts the gateway to place a hold on customer funds without settling, creating a `PaymentRecord` in status `AUTHORIZED`.
2. `capture_payment()` settles the authorized funds, marks the payment `CAPTURED`, sets the invoice to `PAID`, and posts a ledger transaction debiting Cash and crediting Accounts Receivable."

### Q33: How does the API validate incoming timestamp clock drift?
**Answer**:
"In `metering/ingestion.py:L142-L146`:
```python
if event_ts < now - timedelta(days=90):
    return False, 'TIMESTAMP_TOO_OLD'
if event_ts > now + timedelta(hours=1):
    return False, 'TIMESTAMP_IN_FUTURE'
```
This protects the billing engine from accepting stale events that would invalidate closed accounting periods, while tolerating up to 1 hour of client clock drift."

### Q34: What data structure is used to serialize dimensions in `usage_events`?
**Answer**:
"Dimensions are serialized as a deterministic, sorted JSON string (`json.dumps(dims, sort_keys=True)`). This ensures consistent byte representation and allows indexing or hashing across dimensions."

### Q35: How does the system compute Monthly Recurring Revenue (MRR)?
**Answer**:
"In `reporting/metrics.py:L91-L128`, `compute_mrr_metrics()` sums the monthly subscription rates of all active subscriptions (`status == 'ACTIVE'`). For annual plans, it divides the annual fee by 12. Annual Recurring Revenue (ARR) is calculated as $\text{MRR} \times 12$."

---

## 4. Database, Indexes & Financial Integrity

### Q36: Why use composite indexes like `ix_usage_tenant_cust_type_time`?
**Answer**:
"Queries filtering by tenant, customer, event type, and date range are the most frequent operations during billing period rollups. A 4-column composite index allows PostgreSQL to perform an index-only scan, retrieving matching rows in $O(\log N)$ time without touching table heap pages."

### Q37: What is the exact mathematical invariant of the double-entry ledger?
**Answer**:
"For every transaction $T$:
$$\sum_{i=1}^{n} \text{Debits}_i == \sum_{j=1}^{m} \text{Credits}_j \quad \text{where } n + m \ge 2 \text{ and } \text{Amount} > 0$$
Globally, across all accounts in a tenant ledger:
$$\sum \text{All Debits} == \sum \text{All Credits}$$"

### Q38: How does PostgreSQL handle row-level locking during invoice finalization?
**Answer**:
"When executing `SELECT ... FROM invoice_sequences WHERE tenant_id = :t FOR UPDATE`, PostgreSQL places an exclusive row-level lock (`X` lock) on that sequence record. Concurrent transactions attempting to finalize invoices for the same tenant are placed in a queue until the first transaction commits, guaranteeing gapless sequential numbers."

### Q39: What is the trade-off between soft deletes and hard deletes in billing?
**Answer**:
"Financial platforms strictly prohibit hard deletes. Deleting a record destroys audit trails and invalidates historical reconciliations. We use status flags (`VOID`, `INACTIVE`, `REVOKED`), ensuring every historical invoice and transaction remains permanently inspectable."

### Q40: How do you verify that PostgreSQL query partition pruning is working?
**Answer**:
"By executing `EXPLAIN` on a query filtering by timestamp. When partition pruning is active, the query plan shows `Append` or `Seq Scan on usage_events_2026_10` and explicitly marks non-matching partitions as `(never executed)`."

---

## 5. Security, Auth & OWASP Defenses

### Q41: How are API keys stored and verified?
**Answer**:
"When an API key is generated via `AuthManager.create_api_key()`, a 32-byte cryptographically secure token (`bil_role_...`) is generated. The raw token is returned once to the caller. The database stores only the SHA-256 hash (`key_hash`). Verification hashes the incoming bearer token and performs an indexed lookup against `api_keys`."

### Q42: Explain the deny-by-default RBAC implementation.
**Answer**:
"In `security/auth.py`, each role (`OWNER`, `FINANCE`, `VIEWER`, `SERVICE`) is mapped to an explicit set of permission strings. When an endpoint is accessed, the authorization dependency verifies that the caller's role possesses the required permission. If the role or permission is unmapped, access is denied (403 Forbidden)."

### Q43: How does the system prevent PII and credit card numbers from entering audit logs?
**Answer**:
"In `security/audit.py`, `redact_sensitive_info()` recursively inspects before/after state dictionaries. It matches dictionary keys against sensitive terms (`tax_id`, `ssn`, `card_number`, `cvv`) and runs regular expressions against string values, replacing credit cards and tax IDs with `[REDACTED]` before writing to the database."

### Q44: How does the application defend against SQL injection?
**Answer**:
"We use SQLAlchemy 2.0 async queries with explicit parameter binding (`select().where(...)`). No SQL statements are constructed using string concatenation or f-strings."

### Q45: How do you protect against Cross-Origin Resource Sharing (CORS) attacks?
**Answer**:
"Starlette's `CORSMiddleware` explicitly defines allowed origins, methods, and headers. In production, `allow_origins` is restricted to authorized billing console domains rather than wildcard `*`."

---

## 6. Performance, Scaling & Concurrency

### Q46: What is Little's Law and how does it apply to our ingestion pipeline?
**Answer**:
"Little's Law states: $L = \lambda \times W$, where $L$ is concurrency, $\lambda$ is throughput, and $W$ is latency.
If our ingestion pipeline handles $\lambda = 10,000$ events/second with an average latency of $W = 10\text{ms}$ ($0.01\text{s}$), the system must maintain $L = 100$ concurrent database connections in the connection pool to prevent request queueing."

### Q47: How does connection pooling prevent database starvation?
**Answer**:
"Without pooling, each incoming request opens a new TCP connection, exhausting PostgreSQL's `max_connections` (causing fatal connection errors). Our pool maintains 20 warm connections with up to 10 overflow connections, queueing excess requests gracefully."

### Q48: What is the time complexity of the graduated rating calculation?
**Answer**:
"Time complexity is $O(T)$, where $T$ is the number of configured pricing tiers. Because tiers rarely exceed 5 to 10 brackets, the algorithm executes in constant time ($O(1)$) with sub-microsecond latency."

### Q49: How do you handle database deadlocks during concurrent billing cycles?
**Answer**:
"Deadlocks occur when concurrent transactions acquire locks in different orders (e.g., Transaction A locks Invoice 1 then Invoice 2, while Transaction B locks Invoice 2 then Invoice 1). We eliminate deadlocks by enforcing deterministic lock acquisition ordering—sorting resource IDs alphabetically before requesting locks."

### Q50: How does the frontend maintain high performance without a virtual DOM?
**Answer**:
"The billing console in `frontend/src/app.js` updates the DOM surgically using direct element references (`document.getElementById()`). Because only changed text nodes and table rows are mutated, memory overhead is negligible and render times are <16ms (60 FPS)."

---

## 7. Extended Technical Questions (Q51 – Q155)

### Q51: What is the structure of an IngestEventPayload?
**Answer**: Fields: `tenant_id`, `customer_id`, `event_type`, `quantity`, `idempotency_key`, `timestamp`, `project_id`, `unit`, and `dimensions`.

### Q52: What is the default currency in this billing engine?
**Answer**: USD, represented in integer minor units (cents). Multi-currency support handles EUR, GBP, CAD, AUD, JPY, and SGD.

### Q53: What HTTP status code is returned when an event is rejected due to invalid schema?
**Answer**: 422 Unprocessable Entity.

### Q54: What HTTP status code is returned when an idempotency key is replayed?
**Answer**: 200 OK with `status: "DUPLICATE"`.

### Q55: What HTTP status code is returned when a non-existent invoice ID is requested?
**Answer**: 404 Not Found.

### Q56: Can a finalized invoice have line items added to it?
**Answer**: No, `invoicing/manager.py` verifies status is `DRAFT`. Finalized invoices raise a 400 Bad Request error.

### Q57: How is an invoice voided?
**Answer**: By updating status to `VOID` and posting a reversing double-entry ledger transaction crediting AR and debiting Bad Debt Expense.

### Q58: What is the formula for calculating net revenue in `reporting/metrics.py`?
**Answer**: $\text{Net Revenue} = \text{Subtotal} - \text{Discounts} + \text{Tax} = \text{Total Invoiced Amount}$.

### Q59: What is the difference between `recompute_from_scratch` and pre-aggregated rollups?
**Answer**: Rollups are pre-aggregated buckets for fast UI reads; `recompute_from_scratch` runs a direct SQL `SUM` over raw events for ground-truth audits.

### Q60: How does the system handle negative usage quantities?
**Answer**: Rejected at two levels: Pydantic field validation in Python and `CheckConstraint('quantity >= 0')` in SQL.

### Q61: What role does `clock.py` play in testing?
**Answer**: It allows tests to control and fast-forward time to verify dunning schedules and period closes deterministically.

### Q62: What is the maximum allowed clock drift for incoming events?
**Answer**: Up to 90 days in the past and up to 1 hour into the future.

### Q63: What happens if an event's timestamp is 2 hours in the future?
**Answer**: Rejected with error code `TIMESTAMP_IN_FUTURE`.

### Q64: What is the purpose of the `ix_tenant_idem` index?
**Answer**: Enforces unique idempotency keys per tenant, ensuring $O(\log N)$ deduplication speed.

### Q65: Why are financial transactions stored in integer cents?
**Answer**: To eliminate binary floating-point representation errors and guarantee exact compliance with accounting standards.

### Q66: What is the rounding mode used in proration math?
**Answer**: `ROUND_HALF_UP` (standard financial rounding to the nearest cent).

### Q67: How does `SubscriptionLifecycleManager` calculate proration for mid-cycle plan upgrades?
**Answer**: By computing remaining seconds ratio, calculating unused old plan credit and new plan charge, and charging the net difference.

### Q68: What are the 4 dunning stages in `payments/collections.py`?
**Answer**: `ATTEMPT_1` (Day 0), `ATTEMPT_2` (Day 3), `ATTEMPT_3` (Day 7), and `FINAL_ESCALATION` (Day 14).

### Q69: What account standings exist in the dunning workflow?
**Answer**: `GOOD`, `PAST_DUE`, and `SUSPENDED`.

### Q70: When does an account transition to `SUSPENDED`?
**Answer**: When payment collection fails past the 14-day grace period threshold.

### Q71: How are credit card numbers handled in this system?
**Answer**: Never stored in the database; the system operates strictly with payment gateway tokens (`gateway_ref`).

### Q72: What regex pattern is used to detect tax IDs in audit logs?
**Answer**: `\b\d{2}-\d{7}\b` (EIN) and `\b\d{3}-\d{2}-\d{4}\b` (SSN).

### Q73: What is the role of `AsyncSessionLocal` in `db/database.py`?
**Answer**: Creates async database session instances bound to the async SQLAlchemy engine.

### Q74: Why is `expire_on_commit=False` set in sessionmaker?
**Answer**: Prevents SQLAlchemy from reloading model attributes after an async commit, avoiding lazy-loading errors.

### Q75: How does the system ensure gapless sequential invoice numbers?
**Answer**: Uses `SELECT ... FOR UPDATE` on `invoice_sequences` to serialize counter increments per tenant and year.

### Q76: What format do invoice numbers follow?
**Answer**: `INV-{YEAR}-{NUMBER:04d}` (e.g., `INV-2026-0001`).

### Q77: What roles are defined in `security/auth.py`?
**Answer**: `OWNER`, `FINANCE`, `VIEWER`, and `SERVICE`.

### Q78: Can a `SERVICE` role finalize an invoice?
**Answer**: No, `SERVICE` has permissions only for `usage:ingest` and `webhooks:process`.

### Q79: What happens if an API key is revoked?
**Answer**: The database lookup checks `is_revoked == False`; revoked keys immediately return 401 Unauthorized.

### Q80: How are raw API keys generated?
**Answer**: Using Python's `secrets.token_urlsafe(32)` prefixed with the role name.

### Q81: What is the primary key of `usage_events`?
**Answer**: `event_id` (64-character string).

### Q82: What is the primary key of `ledger_transactions`?
**Answer**: `transaction_id` (64-character string).

### Q83: What is the foreign key relationship between `ledger_entries` and `ledger_transactions`?
**Answer**: `ledger_entries.transaction_id` references `ledger_transactions.transaction_id`.

### Q84: What database check constraint exists on `ledger_entries`?
**Answer**: `CheckConstraint('amount_cents > 0')`.

### Q85: What database check constraint exists on `usage_events`?
**Answer**: `CheckConstraint('quantity >= 0')`.

### Q86: What pricing models are supported in `rating/engine.py`?
**Answer**: `FLAT_FEE`, `PER_UNIT`, `TIERED_VOLUME`, `GRADUATED_BRACKET`, and `OVERAGE`.

### Q87: What is an overage pricing model?
**Answer**: A base fee includes a fixed quantity of units; any excess usage beyond included units is billed at an overage unit rate.

### Q88: How are free units handled in rating?
**Answer**: Deducted from total quantity before evaluating billable brackets: `billable_qty = max(0, qty - free_units)`.

### Q89: What is the purpose of `MeterAggregationType` in `models/meters.py`?
**Answer**: Defines how raw events are rolled up into billable meter metrics: `SUM`, `COUNT`, `MAX`, or `LAST`.

### Q90: How does the billing engine handle multiple meters under a single subscription plan?
**Answer**: The price book catalog allows multiple `PriceBookEntry` records per `plan_id`, each mapped to a distinct `event_type`.

### Q91: What is the endpoint to calculate real-time pricing without writing to the database?
**Answer**: `POST /v1/rating/calculate`.

### Q92: What is the endpoint to fetch the Billing Dashboard KPI summary?
**Answer**: `GET /v1/dashboard/summary?tenant_id={tenant_id}`.

### Q93: What KPIs are returned by the dashboard summary endpoint?
**Answer**: `gross_revenue_cents`, `net_revenue_cents`, `mrr_cents`, `arr_cents`, `active_subscriptions`, and `unpaid_amount_cents`.

### Q94: How does the frontend format integer cents into currency display?
**Answer**: Using `formatCents(cents)`: `((cents || 0) / 100).toFixed(2)` formatted with a `$` prefix.

### Q95: What CSS styling paradigm is used in `frontend/src/index.css`?
**Answer**: Pure Vanilla CSS custom properties (`--bg-black: #000000`, `--text-main: #f8fafc`) providing a responsive dark theme.

### Q96: How does the frontend handle backend API network errors?
**Answer**: Catches network exceptions in `try/catch` blocks and logs graceful warnings without freezing the UI.

### Q97: What happens when an invoice is marked `VOID`?
**Answer**: Its status is set to `VOID`, and a compensating double-entry ledger transaction is posted to reverse outstanding AR.

### Q98: Can an invoice transition from `FINALIZED` back to `DRAFT`?
**Answer**: No, state transitions are strictly one-way: `DRAFT -> FINALIZED -> PAID` or `VOID`.

### Q99: What is the purpose of `usage_rollups` table?
**Answer**: Stores pre-aggregated usage by hour or day to allow instant dashboard analytics without scanning billions of raw events.

### Q100: What index optimizes queries against `usage_rollups`?
**Answer**: `ix_rollup_lookup` on `(tenant_id, customer_id, event_type, granularity, bucket_start)`.

### Q101: How does `UsageAggregator` prevent overlapping hourly rollup buckets?
**Answer**: By computing exact UTC bucket boundaries (`floor to start of hour`) and enforcing unique compound constraints.

### Q102: How does the system authenticate internal microservices vs customer UI sessions?
**Answer**: Both use API keys hashed via SHA-256; microservices are assigned the `SERVICE` role, while web consoles use `FINANCE` or `VIEWER` keys.

### Q103: What is the difference between an event timestamp and `received_at`?
**Answer**: `timestamp` is when the consumption occurred on the client device; `received_at` is when the server received the payload.

### Q104: Why is `received_at` generated server-side?
**Answer**: To detect client clock drift and provide an immutable audit timestamp independent of client-controlled clocks.

### Q105: What is the maximum number of events permitted in a single batch ingest call?
**Answer**: Up to 1,000 events per request payload.

### Q106: What happens if one event in a batch payload fails schema validation?
**Answer**: The pipeline rejects the invalid event with an error in the response array while successfully processing valid entries, or aborts the batch depending on atomic flag settings.

### Q107: How does `test_database_distributed_infrastructure.py` verify partitioning?
**Answer**: By executing `EXPLAIN` queries against SQLite/PostgreSQL to verify partition pruning.

### Q108: How many passing automated tests exist in the test suite?
**Answer**: 87 passing tests across 52 test files.

### Q109: What test command runs the complete test suite?
**Answer**: `PYTHONPATH=backend/src pytest`.

### Q110: How does `test_graduated_pricing.py` verify mathematical accuracy?
**Answer**: Compares rating output against golden hand-computed test matrices specified independently of the code.

### Q111: What is the purpose of `PriceTier` schema?
**Answer**: Models a single pricing bracket with `up_to` threshold, `unit_price_cents`, and optional tier `flat_fee_cents`.

### Q112: How does the rating engine represent an unbounded top tier?
**Answer**: By setting `up_to = None`.

### Q113: What happens if an empty tier list is passed for graduated pricing?
**Answer**: `RatingEngine.rate_usage()` raises a `ValueError("Graduated pricing requires tiers configuration")`.

### Q114: How does the invoice manager compute line-item totals?
**Answer**: `amount_cents = quantity * unit_price_cents`.

### Q115: What is the formula for invoice total?
**Answer**: `total_cents = subtotal_cents - discount_cents - credit_cents + tax_cents`.

### Q116: Can `total_cents` on an invoice be negative?
**Answer**: No, credits and discounts are clamped so the total cannot fall below zero.

### Q117: What accounts are involved in invoice finalization?
**Answer**: Debit: Accounts Receivable (`AR`), Credit: Revenue (`REV`).

### Q118: What accounts are involved in payment capture?
**Answer**: Debit: Cash (`CASH`), Credit: Accounts Receivable (`AR`).

### Q119: What accounts are involved in customer refunds?
**Answer**: Debit: Revenue or Refund Expense (`REFUND`), Credit: Cash (`CASH`).

### Q120: What is the lifespan context manager in `app.py`?
**Answer**: An asynchronous context manager executing `init_db()` on application startup to ensure schema readiness.

### Q121: How are CORS headers configured in `app.py`?
**Answer**: Using `CORSMiddleware` with configurable `allow_origins`, `allow_methods`, and `allow_headers`.

### Q122: What happens when `GET /health` is queried?
**Answer**: The handler executes `SELECT 1` on the database session and returns `{ "status": "ok", "service": "19-usage-billing-engine" }`.

### Q123: What does an `IngestionStatus.REJECTED` response indicate?
**Answer**: Payload failed validation (e.g. negative quantity or excessive timestamp drift); no database write occurred.

### Q124: How does `PriceBookManager.get_entries_for_plan` query pricing rules?
**Answer**: Uses `select(PriceBookEntryRecord).where(tenant_id == ..., plan_id == ...)`.

### Q125: What is Annual Recurring Revenue (ARR)?
**Answer**: $\text{MRR} \times 12$.

### Q126: What is Average Revenue Per User (ARPU)?
**Answer**: $\text{Total MRR} / \text{Active Subscriptions Count}$.

### Q127: How does `test_proration_hand_computed` verify proration?
**Answer**: Compares net proration cents against hand-calculated golden figures down to the exact integer cent.

### Q128: What is the difference between volume-tiered and flat subscription pricing?
**Answer**: Volume pricing charges based on usage brackets; flat subscription pricing charges a fixed recurring fee regardless of usage.

### Q129: What is the purpose of `PaymentAttemptRecord`?
**Answer**: Stores every charge attempt with an attempt number, idempotency key, status, and gateway error code.

### Q130: Why is `idempotency_key` indexed on `payment_attempts`?
**Answer**: To prevent parallel retry requests from submitting duplicate authorization charges to the gateway.

### Q131: What is the dunning retry schedule?
**Answer**: Day 0 (Immediate), Day 3 (Retry 1), Day 7 (Retry 2), and Day 14 (Final Notice & Suspension).

### Q132: What happens when an account standing becomes `SUSPENDED`?
**Answer**: Ingestion and API access are blocked until outstanding invoices are settled.

### Q133: How does `AuditLogManager` record before and after states?
**Answer**: By serializing model dictionaries to sanitized JSON strings in `before_state` and `after_state` columns.

### Q134: How does the system handle leap years in invoice numbering?
**Answer**: Sequence counters are keyed by `(tenant_id, year)` where `year` is extracted from UTC datetime (`dt.year`).

### Q135: What database driver is used for SQLite during development?
**Answer**: `aiosqlite`.

### Q136: What database driver is used for PostgreSQL in production?
**Answer**: `asyncpg`.

### Q137: How does the engine support custom usage dimensions like `region` and `endpoint`?
**Answer**: Dimensions are stored in a flexible `dimensions_json` column and indexed via composite tenant indices.

### Q138: Can a customer have multiple active subscriptions?
**Answer**: Yes, subscriptions are mapped by unique `subscription_id` per customer.

### Q139: What is the purpose of `PlanVersionRecord.base_fee_cents`?
**Answer**: Defines the fixed recurring platform charge before metered usage is applied.

### Q140: What happens if a payment capture fails?
**Answer**: Payment status is updated to `FAILED`, the attempt is logged, and the dunning workflow advances to the next retry stage.

### Q141: What is the role of `vitepress` in this repository?
**Answer**: Generates the developer documentation website with pure-black dark theme and Mermaid diagram support.

### Q142: How does `withMermaid` integrate with VitePress?
**Answer**: Wraps VitePress config to compile and render Markdown `mermaid` blocks into client-side SVG diagrams.

### Q143: What is the purpose of `custom.css` in VitePress?
**Answer**: Overrides VitePress default theme colors, forcing `--vp-c-bg: #000000` for pure black dark mode.

### Q144: How are unit conversions verified in tests?
**Answer**: In `test_usage_metering_core.py`, conversions between MB and GB or seconds and hours are asserted against float tolerances.

### Q145: What happens when a tenant ledger is reconciled?
**Answer**: `reconcile_tenant_ledger()` computes sum of all tenant debits and credits; returns `True` if difference is 0.

### Q146: What was the hardest technical decision you had to make?
**Answer**: Choosing between an event-sourced ledger vs a double-entry ledger. I chose double-entry because standard accounting and auditing require debit-credit balance sheets.

### Q147: How did you diagnose the sequence number race condition?
**Answer**: By writing a concurrent test running 50 asyncio workers finalizing invoices simultaneously and catching unique constraint violations.

### Q148: What did you learn about Python's Decimal module?
**Answer**: That initializing `Decimal` with floats introduces precision artifacts (e.g. `Decimal(0.1)` vs `Decimal('0.1')`); strings must always be used.

### Q149: How do you prevent memory leaks in long-running FastAPI processes?
**Answer**: By scoping database sessions to individual request lifespans using FastAPI's `Depends(get_db)` and releasing connections immediately.

### Q150: How do you test billing features without waiting 30 days for cycle close?
**Answer**: By injecting a `ManualClock` simulator into the period and dunning managers, advancing time programmatically in tests.

### Q151: What metrics would you set up in Prometheus to monitor this system?
**Answer**: Ingestion rate (`events/sec`), rating duration percentiles (p95, p99), invoice finalization counts, and ledger imbalance alarms.

### Q152: How would you migrate from SQLite to PostgreSQL in production?
**Answer**: SQLAlchemy's abstract ORM definitions make switching dialects seamless: only `DATABASE_URL` changes from `sqlite+aiosqlite` to `postgresql+asyncpg`.

### Q153: How does the system handle currency conversion?
**Answer**: Invoices are generated in customer account base currency; multi-currency conversions are handled via external exchange rate tables before line-item generation.

### Q154: What is the role of `pydantic.ConfigDict(from_attributes=True)`?
**Answer**: Enables Pydantic models to automatically serialize data directly from SQLAlchemy ORM records.

### Q155: Summarize the primary technical achievement of this project.
**Answer**: Building a high-throughput, idempotent billing engine that combines sub-millisecond telemetry ingestion with mathematically exact integer rating and immutable double-entry accounting."
