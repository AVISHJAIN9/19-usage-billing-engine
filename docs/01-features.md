# Feature Inventory & Architectural Traces

This document provides the complete, numbered inventory of all major features implemented in `19-usage-billing-engine`, tracing each feature from user interaction to database persistence and financial reconciliation.

---

## Feature Matrix Overview

| Feature ID | Feature Name | Core Layer | Primary Source File | Primary Endpoint | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **F1** | Usage Event Store | Database / Models | `backend/src/models/events.py` | `POST /v1/usage/events` | Implemented |
| **F2** | Idempotent Ingestion Pipeline | Metering Core | `backend/src/metering/ingestion.py` | `POST /v1/usage/events` | Implemented |
| **F3** | Multi-Tiered Rating Engine | Rating Core | `backend/src/rating/engine.py` | `POST /v1/rating/calculate` | Implemented |
| **F4** | Double-Entry Financial Ledger | Ledger / Integrity | `backend/src/models/ledger.py` | Internal / Financial Sync | Implemented |
| **F5** | Automated Invoicing Engine | Invoicing | `backend/src/invoicing/manager.py` | `POST /v1/invoices` | Implemented |
| **F6** | Payments, Retries & Dunning | Payments | `backend/src/payments/collections.py` | `POST /v1/payments/authorize`| Implemented |
| **F7** | Aggregation & Billing Periods | Aggregation | `backend/src/aggregation/periods.py` | `GET /v1/usage/query` | Implemented |
| **F8** | Proration & Subscription Lifecycle| Accounts / Models | `backend/src/models/proration.py` | `POST /v1/subscriptions/{id}/upgrade`| Implemented |
| **F9** | Deny-by-Default RBAC & Audit | Security | `backend/src/security/auth.py` | Internal / Auth Middleware | Implemented |
| **F10**| Customer Billing Console | Frontend Console | `frontend/src/app.js` | Web Console (`5190`) | Implemented |

---

## F1: Usage Event Store & Dimension Storage
Granular metered usage records with multi-dimensional metadata, tenant isolation, and composite unique idempotency constraints.

- **Source Code**: `backend/src/models/events.py:L14-L157`
- **APIs Involved**: `POST /v1/usage/events, GET /v1/usage/events`
- **Data Touched**: Table: usage_events (event_id, tenant_id, customer_id, event_type, quantity, dimensions_json, idempotency_key, timestamp, received_at). Indexes: ix_tenant_idem (unique), ix_tenant_cust_time, ix_usage_tenant_cust_type_time.
- **Edge Cases**: Negative quantity rejected via database check constraint `chk_usage_quantity_nonneg`. Replayed idempotency keys return existing record without duplicate insertion.
- **Security**: Tenant ID indexed on all queries, preventing cross-tenant information leakage. Dimensions stored as serialized JSON string to prevent SQL injection.
- **Performance**: Composite indexing allows index-only or index-range scans across tenant, customer, and timestamp dimensions. Time-partitioned in PostgreSQL.
- **Known Limitations**: Dimensions are limited to 1024 characters; large unstructured metadata must be offloaded to external blob storage.

### Say It Out Loud
> "I built the usage event store in models/events.py to act as the single source of truth for all customer consumption. When raw telemetry arrives, my store validates that the usage quantity is non-negative and serializes custom metadata like project IDs or compute regions into a JSON column.
To guarantee that network retries never lead to duplicate charges, I created a composite unique index on tenant ID and idempotency key directly in PostgreSQL. If an event with the same key arrives again, my query detects the existing record and returns it immediately instead of inserting a duplicate.
I chose a relational schema with B-tree composite indexes over a NoSQL document database because financial billing demands ACID consistency and strict unique constraints across concurrent requests.
If the database connection drops or a negative quantity is submitted, the transaction rolls back cleanly and returns a structured error to the caller.
One limitation is that our dimension column is capped at 1024 bytes, so for clients needing massive telemetry payloads, I would introduce an external blob reference."

---

## F2: High-Throughput Idempotent Ingestion Pipeline
Validates schema formats, checks timestamp clock drift boundaries, and performs cryptographic deduplication.

- **Source Code**: `backend/src/metering/ingestion.py:L123-L313`
- **APIs Involved**: `POST /v1/usage/events, POST /v1/usage/events/batch`
- **Data Touched**: Reads and writes to usage_events table.
- **Edge Cases**: Rejects events with timestamps older than 90 days or more than 1 hour into the future with structured error codes `TIMESTAMP_TOO_OLD` and `TIMESTAMP_IN_FUTURE`.
- **Security**: Pydantic field validators sanitize string inputs, rejecting whitespace or SQL control characters.
- **Performance**: Batch ingestion endpoint processes up to 1,000 events in a single database transaction, reducing network roundtrip overhead.
- **Known Limitations**: Synchronous database deduplication can become a bottleneck at >50,000 requests/second without an upfront Redis key cache.

### Say It Out Loud
> "I designed the ingestion pipeline in metering/ingestion.py to absorb millions of raw consumption events while guaranteeing exactly-once accounting. When a client service reports API calls or compute runtimes, the pipeline first runs strict Pydantic validation to verify field formats and check that quantities are positive.
Next, it performs a timestamp drift check: events with timestamps older than 90 days or more than one hour into the future are rejected to prevent backdated billing fraud. Then it queries the idempotency index. If the event is new, it persists it and returns status ACCEPTED; if it has already been processed, it acknowledges it with status DUPLICATE so the caller knows it was received without double-counting.
I chose this synchronous database verification model rather than an eventual consistency queue because billing accuracy cannot tolerate race conditions during period close.
When payload validation fails, the pipeline returns a 422 Unprocessable Entity with an explicit machine-readable code like TIMESTAMP_TOO_OLD.
A known trade-off is that checking the database on every event limits single-node throughput, which is why I would add a Redis bloom filter or key-value cache for deduplication at higher scale."

---

## F3: Multi-Tiered Dynamic Rating Engine
Mathematical evaluation of consumption units against diverse pricing structures: flat, per-unit, volume-tiered, graduated brackets, and overage limits.

- **Source Code**: `backend/src/rating/engine.py:L85-L193`
- **APIs Involved**: `POST /v1/rating/calculate, POST /v1/rating/price-books, GET /v1/rating/price-books`
- **Data Touched**: Table: price_book_entries (id, tenant_id, plan_id, event_type, pricing_type, flat_fee_cents, free_units, unit_price_cents, min_charge_cents, max_charge_cents, included_units, overage_unit_price_cents, tiers_json).
- **Edge Cases**: Handles quantities spanning multiple graduated tiers; enforces minimum monthly charge floor if calculated total is below floor, and caps at maximum charge ceiling if configured.
- **Security**: Tenant-scoped price book entries prevent unauthorized pricing modifications across customer organizations.
- **Performance**: Pure in-memory mathematical rating with zero database I/O during calculation, executing in sub-microsecond time.
- **Known Limitations**: Does not currently support dynamic currency exchange rate conversions at rating time; price books are configured in a single base currency.

### Say It Out Loud
> "I built the rating engine in rating/engine.py to handle complex enterprise SaaS pricing models without requiring manual calculations or code changes. When usage is rated, the engine deducts any free tier allowance first, then branches into the appropriate pricing algorithm.
For graduated bracket pricing, it slices the billable volume into successive tiers—for instance, charging the first 1,000 units at 5 cents and subsequent units at 3 cents. For volume pricing, it evaluates total volume to select a single discounted rate applied across all units. It also supports overage pricing with base allowances, and automatically enforces contract minimum charge floors and maximum charge ceilings.
Crucially, all math is done in exact integer cents or fixed-point decimal arithmetic, completely avoiding binary floating-point rounding errors.
I chose a pure functional rating engine design so that pricing can be evaluated both in batch during monthly invoicing and on-the-fly when customers request real-time cost estimates.
If an invalid pricing configuration or negative quantity is passed, the engine throws an immediate ValueError.
A current limitation is that currency conversion happens downstream rather than inside the rating engine, which I would unify in the next release."

---

## F4: Append-Only Double-Entry Financial Ledger
Immutable accounting ledger enforcing the fundamental bookkeeping invariant: sum of debits strictly equals sum of credits across at least two entries.

- **Source Code**: `backend/src/models/ledger.py:L63-L436`
- **APIs Involved**: `Internal domain service invoked by invoicing, payments, and refunds.`
- **Data Touched**: Tables: ledger_transactions (transaction_id, tenant_id, reference_id, description, posted_at), ledger_entries (entry_id, transaction_id, account_id, entry_type, amount_cents). Check constraint: amount_cents > 0.
- **Edge Cases**: Transactions with fewer than 2 entries or unbalanced debit/credit sums are rejected before database commit.
- **Security**: Append-only design; UPDATE and DELETE operations are prohibited at both application and database trigger levels.
- **Performance**: Indexed by transaction_id and account_id, enabling fast balance reconciliations via SQL aggregate functions.
- **Known Limitations**: High-volume transaction streams require periodic account balance snapshots to prevent unbounded table scan times during historical queries.

### Say It Out Loud
> "I engineered the double-entry accounting ledger in models/ledger.py to provide complete financial auditability and eliminate silent balance drift. Every monetary event in the system—whether it is finalizing an invoice, collecting a credit card payment, or granting a promotional credit—must write a balanced double-entry transaction.
My record_transaction method enforces two non-negotiable rules: first, every transaction must contain at least two entries, and second, the sum of all debits must strictly equal the sum of all credits in integer cents. If an invoice for $100 is finalized, it writes a debit of 10,000 cents to Accounts Receivable and a credit of 10,000 cents to Revenue.
I chose double-entry bookkeeping over a simple mutable balance column because single-entry ledgers make it impossible to audit where funds originated or detect software corruption after the fact.
If any component attempts to post an unbalanced transaction, my code raises a ValueError and the database transaction is aborted immediately.
One limitation is that computing account balances requires summing historical entries, which I would optimize at higher scale by introducing daily materialized balance checkpoints."

---

## F5: Automated Invoicing Engine & Gapless Numbering
Billing cycle reconciliation, itemized line-item aggregation, tax/discount calculation, and gapless sequential numbering per tenant.

- **Source Code**: `backend/src/invoicing/manager.py:L140-L421`
- **APIs Involved**: `POST /v1/invoices, POST /v1/invoices/{id}/items, POST /v1/invoices/{id}/finalize, GET /v1/invoices/{id}, GET /v1/invoices`
- **Data Touched**: Tables: invoices (id, tenant_id, customer_id, period_id, invoice_number, status, subtotal_cents, discount_cents, credit_cents, tax_cents, total_cents, due_date, finalized_at), invoice_line_items, invoice_sequences.
- **Edge Cases**: Strict immutability: once status is `FINALIZED`, adding line items or modifying amounts is permanently locked. Finalization acquires row-level lock on `invoice_sequences` to prevent sequence number gaps.
- **Security**: Tenant-scoped queries ensure customers cannot inspect invoices belonging to other organizations.
- **Performance**: Subtotal, tax, and discount arithmetic performed in integer cents; single atomic transaction finalizes invoice and posts ledger entry.
- **Known Limitations**: PDF generation is handled by client-side HTML print styles rather than server-side headless Chromium rendering.

### Say It Out Loud
> "I developed the invoicing engine in invoicing/manager.py to manage the complete lifecycle from draft usage aggregation to finalized customer bills. When a billing cycle closes, our system generates a draft invoice and appends itemized line items for metered usage, subscription base fees, discounts, and taxes.
When the invoice is finalized, the manager locks the invoice into an immutable state so no further edits can occur. It calculates total cents using the formula: subtotal minus discounts minus credits plus tax.
To satisfy strict accounting and legal compliance, it queries an invoice sequences table with row-level locking to assign a gapless sequential number formatted as INV-year-number, guaranteeing no numbers are skipped even under concurrent finalization requests.
Simultaneously, it triggers a double-entry ledger posting to debit Accounts Receivable and credit Revenue.
I chose this multi-stage lifecycle (Draft to Finalized to Paid or Void) because enterprise finance teams require the ability to review and adjust draft line items before locking legal fiscal records.
If someone attempts to modify a finalized invoice, the method raises a 400 Bad Request error.
A limitation is that invoice PDF rendering currently relies on the browser's print engine, which I plan to supplement with a server-side PDF generator."

---

## F6: Payment Collections, Retries & Dunning Lifecycle
Two-step authorization and capture, idempotent retries, failure tracking, and manual clock-driven dunning schedules.

- **Source Code**: `backend/src/payments/collections.py:L65-L334`
- **APIs Involved**: `POST /v1/payments/authorize, POST /v1/payments/{id}/capture`
- **Data Touched**: Tables: payments, payment_attempts, dunning_workflows. States: DunningStage (ATTEMPT_1, ATTEMPT_2, ATTEMPT_3, FINAL_ESCALATION, COMPLETED), AccountStanding (GOOD, PAST_DUE, SUSPENDED).
- **Edge Cases**: Declined card attempts log detailed error codes; dunning schedule automatically transitions account from PAST_DUE to SUSPENDED once grace period expires.
- **Security**: Never stores raw credit card numbers or CVVs; operates strictly with gateway reference tokens.
- **Performance**: Idempotent payment attempts prevent accidental double-charging during network timeouts.
- **Known Limitations**: Gateway integration currently connects to an internal sandbox rather than live Stripe or Adyen production APIs.

### Say It Out Loud
> "I built the collections and dunning engine in payments/collections.py to automate payment settlements and recover revenue from failed transactions. When an invoice comes due, our system issues a two-step payment authorization followed by capture.
If a payment fails due to an expired card or insufficient funds, the system does not simply disconnect the customer; instead, it enters an automated dunning workflow. It schedules retries across a defined schedule—immediately on Day 0, followed by retries on Day 3 and Day 7, and a final escalation on Day 14.
During this window, the account is marked PAST_DUE, giving the customer a grace period to update their payment method. If the grace period expires without settlement, the account standing transitions to SUSPENDED.
I chose a two-step authorization and capture model because it allows us to verify funds before locking invoices, and enables partial captures if disputes arise.
Every payment attempt logs an idempotency key and attempt record, guaranteeing that network glitches cannot cause a customer to be charged twice.
A current limitation is that we use a local gateway sandbox for tests, which I would connect to Stripe Billing and webhooks for live production operations."

---

## F7: Aggregation Engine & Billing Period Lifecycle
Monthly and hourly usage aggregation, period state transitions (OPEN -> CLOSING -> CLOSED), and differential recompute verification.

- **Source Code**: `backend/src/aggregation/periods.py:L130-L414`
- **APIs Involved**: `GET /v1/usage/query`
- **Data Touched**: Tables: billing_periods (period_id, tenant_id, customer_id, start_date, end_date, status, closed_at), usage_rollups (id, tenant_id, customer_id, event_type, granularity, bucket_start, bucket_end, total_quantity, event_count).
- **Edge Cases**: Late-arriving events for an already CLOSED period are automatically routed to the current open billing period as prior-period adjustments.
- **Security**: Tenant and customer query filters prevent cross-tenant usage aggregation.
- **Performance**: Hourly and daily rollups pre-aggregate high-volume streams, allowing instant dashboard queries without full table scans.
- **Known Limitations**: Hourly rollups require background cron or trigger execution to remain fresh.

### Say It Out Loud
> "I designed the aggregation and periods engine in aggregation/periods.py to manage the lifecycle of billing cycles and aggregate high-volume telemetry. A customer's consumption is divided into distinct billing periods that transition from OPEN to CLOSING and finally CLOSED.
While a period is open, incoming events increment pre-aggregated hourly rollups so dashboard queries return in milliseconds. However, during end-of-month closing, our engine runs a differential test: it executes recompute_from_scratch, which performs a direct SQL sum over raw usage events to prove that pre-aggregated rollups match raw telemetry exactly.
If out-of-order events arrive after a billing period has already closed, the system does not modify historical invoices; instead, it rolls them into the active period as a prior-period adjustment.
I chose to maintain both pre-aggregated rollups and immutable raw events because fast UI queries require caching, but financial audits demand a verifiable raw paper trail.
If dates are inverted or overlapping periods are submitted, the manager raises a clean validation error.
A trade-off is that storing both raw events and rollups increases database storage footprint, which is managed via table partitioning."

---

## F8: Subscription Lifecycle & Exact Proration Engine
Subscription state machine and second-exact pro-rata financial adjustments for mid-cycle upgrades, downgrades, and cancellations.

- **Source Code**: `backend/src/models/proration.py:L31-L77`
- **APIs Involved**: `POST /v1/subscriptions, POST /v1/subscriptions/{id}/upgrade, GET /v1/subscriptions/{id}`
- **Data Touched**: Tables: subscriptions, plan_versions. ProrationResult dataclass (unused_credit_cents, new_charge_cents, net_proration_cents, fraction_remaining).
- **Edge Cases**: Upgrades occurring on the first or last second of a cycle calculate 0% or 100% fractions cleanly; Decimal quantize ensures exact cent totals.
- **Security**: Effective timestamps are clamped between period_start and period_end to prevent negative proration fractions.
- **Performance**: In-memory decimal calculations run in under 10 microseconds.
- **Known Limitations**: Assumes a continuous uniform second distribution across the month rather than day-based calendar variations.

### Say It Out Loud
> "I engineered the proration engine in models/proration.py to eliminate billing disputes when customers upgrade or downgrade subscription plans mid-month. When a customer upgrades from a $50 plan to a $200 plan halfway through the month, calculating the charge by hand or using floating-point math causes rounding discrepancies.
My calculate_proration function computes the exact total seconds and remaining seconds in the billing window. It calculates the remaining fraction using Python's Decimal module and computes two values: the unused credit from the previous plan and the new plan charge for the remaining duration. Both are quantized to integer cents using standard financial ROUND_HALF_UP arithmetic.
The difference gives the net proration cents, which is added directly as a credit or charge line item on the customer's next invoice.
I chose second-level precision with Decimal arithmetic over daily integer ratios because cloud services need exact pro-rata calculations when upgrades happen at any time of day.
If an invalid time range is passed where end is before start, the function raises a ValueError.
One limitation is that leap seconds are not modeled, which has negligible financial impact but is documented in our spec."

---

## F9: Deny-by-Default RBAC & Sanitized Audit Logging
Role-based access control, cryptographic API key authentication, and audit log generation with automated PII and Tax-ID redaction.

- **Source Code**: `backend/src/security/auth.py, backend/src/security/audit.py`
- **APIs Involved**: `Internal security middleware and admin endpoints.`
- **Data Touched**: Tables: api_keys (key_id, tenant_id, key_hash, role, is_revoked, created_at), audit_logs (audit_id, tenant_id, actor, action, resource_type, resource_id, before_state, after_state, created_at).
- **Edge Cases**: Revoked keys immediately return 401 Unauthorized; cross-tenant requests return 403 Forbidden under deny-by-default policy.
- **Security**: Raw API keys are never stored; only SHA-256 hashes are persisted. Audit logs recursively redact tax IDs, credit cards, and passwords.
- **Performance**: Fast hash lookups on indexed `key_hash` column execute in <2ms.
- **Known Limitations**: Does not currently support temporary STS session tokens or OAuth2 JWT validation.

### Say It Out Loud
> "I built the security and audit layer in security/auth.py and security/audit.py to meet enterprise compliance standards like SOC 2 and GDPR. The authentication system uses cryptographically generated API keys. The raw key is shown only once to the user upon creation; our database stores only the SHA-256 hash, ensuring that even a database dump cannot expose plaintext credentials.
We implement strict deny-by-default RBAC across four distinct roles: Owner, Finance, Viewer, and Service. For example, a Service role can ingest usage events but cannot view customer invoices, while a Finance role can finalize invoices and capture payments.
Additionally, our audit logger tracks every state mutation with the actor, action, and before-and-after states. Before writing to the database, a recursive sanitizer scans all payload keys and strings using regular expressions, automatically redacting tax IDs, Social Security numbers, and credit card numbers with [REDACTED].
I chose this built-in RBAC and audit framework over generic third-party auth because financial billing systems require deep domain-level permission scopes.
If an unauthorized role attempts a mutation, the system rejects it with a 403 Forbidden.
A limitation is that keys are currently static; I plan to introduce automated 90-day key rotation in the next milestone."

---

## F10: Customer Billing Console & Real-Time KPI Dashboard
Single-page responsive customer billing portal displaying live revenue KPIs, invoice catalogs, itemized line items, and settlement status.

- **Source Code**: `frontend/src/app.js, frontend/src/index.html, frontend/src/index.css`
- **APIs Involved**: `GET /v1/dashboard/summary, GET /v1/invoices, GET /v1/invoices/{id}, POST /v1/invoices/{id}/finalize`
- **Data Touched**: Client-side state object (tenantId, customerId, invoiceId, invoicesList, dashboardSummary).
- **Edge Cases**: Handles empty invoice lists and server offline states gracefully with visual warning indicators.
- **Security**: Input sanitization prevents DOM-based XSS when rendering customer-provided descriptions.
- **Performance**: Zero external runtime dependencies; pure vanilla JavaScript and CSS ensures instant loading (<100ms) and minimal memory footprint.
- **Known Limitations**: Does not use a client-side routing framework (like React Router); views are toggled via DOM section visibility.

### Say It Out Loud
> "I created the customer billing console in frontend/src/app.js, index.html, and index.css to give tenant administrators and finance teams real-time visibility into their billing operations. The console features a responsive KPI dashboard that displays gross revenue, Monthly Recurring Revenue, Annual Recurring Revenue, and unpaid invoice totals.
Users can filter through an interactive invoice catalog by status—such as Draft, Finalized, or Paid—and click on any invoice to inspect a complete line-item breakdown showing exact quantities, unit rates, subtotal, discounts, and taxes.
Finance managers can also click to finalize draft invoices directly from the UI, updating the status and displaying the newly assigned legal sequential number in real time.
I chose vanilla JavaScript, HTML5, and pure CSS custom properties over a heavy frontend framework to keep the bundle size practically zero, eliminate build step complexity, and ensure the console loads in under 100 milliseconds.
If the backend API is unreachable, the console displays non-intrusive fallback indicators without crashing.
A limitation is that views are switched by toggling CSS display styles rather than URL hash routing, which I would enhance with a lightweight client router in the future."

---
