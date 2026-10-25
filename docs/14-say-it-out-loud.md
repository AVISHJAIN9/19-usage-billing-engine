# Say It Out Loud: Complete Spoken Rehearsal Scripts

This document gathers all first-person spoken interview scripts in one place, allowing the developer to rehearse explaining every feature out loud without notes.

---

## 30-Second Elevator Pitch
> "I designed and built 19-Usage-Billing-Engine, an enterprise-grade metered billing, rating, and invoicing platform in Python FastAPI, PostgreSQL, and React. It solves the critical financial risk of usage-based pricing by providing an idempotent ingestion pipeline that guarantees exactly-once billing under network retries. It features a multi-tiered rating engine supporting graduated and volume pricing calculated to exact integer cents, an append-only double-entry ledger that strictly enforces debit-credit conservation, and automated billing cycle reconciliation with gapless invoice numbering."

---

## Feature 1: Usage Event Store (`models/events.py`)
> "I built the usage event store in models/events.py to act as the single source of truth for all customer consumption. When raw telemetry arrives, my store validates that the usage quantity is non-negative and serializes custom metadata like project IDs or compute regions into a JSON column.
> To guarantee that network retries never lead to duplicate charges, I created a composite unique index on tenant ID and idempotency key directly in PostgreSQL. If an event with the same key arrives again, my query detects the existing record and returns it immediately instead of inserting a duplicate.
> I chose a relational schema with B-tree composite indexes over a NoSQL document database because financial billing demands ACID consistency and strict unique constraints across concurrent requests.
> If the database connection drops or a negative quantity is submitted, the transaction rolls back cleanly and returns a structured error to the caller.
> One limitation is that our dimension column is capped at 1024 bytes, so for clients needing massive telemetry payloads, I would introduce an external blob reference."

---

## Feature 2: Idempotent Ingestion Pipeline (`metering/ingestion.py`)
> "I designed the ingestion pipeline in metering/ingestion.py to absorb millions of raw consumption events while guaranteeing exactly-once accounting. When a client service reports API calls or compute runtimes, the pipeline first runs strict Pydantic validation to verify field formats and check that quantities are positive.
> Next, it performs a timestamp drift check: events with timestamps older than 90 days or more than one hour into the future are rejected to prevent backdated billing fraud. Then it queries the idempotency index. If the event is new, it persists it and returns status ACCEPTED; if it has already been processed, it acknowledges it with status DUPLICATE so the caller knows it was received without double-counting.
> I chose this synchronous database verification model rather than an eventual consistency queue because billing accuracy cannot tolerate race conditions during period close.
> When payload validation fails, the pipeline returns a 422 Unprocessable Entity with an explicit machine-readable code like TIMESTAMP_TOO_OLD.
> A known trade-off is that checking the database on every event limits single-node throughput, which is why I would add a Redis bloom filter or key-value cache for deduplication at higher scale."

---

## Feature 3: Multi-Tiered Dynamic Rating Engine (`rating/engine.py`)
> "I built the rating engine in rating/engine.py to handle complex enterprise SaaS pricing models without requiring manual calculations or code changes. When usage is rated, the engine deducts any free tier allowance first, then branches into the appropriate pricing algorithm.
> For graduated bracket pricing, it slices the billable volume into successive tiers—for instance, charging the first 1,000 units at 5 cents and subsequent units at 3 cents. For volume pricing, it evaluates total volume to select a single discounted rate applied across all units. It also supports overage pricing with base allowances, and automatically enforces contract minimum charge floors and maximum charge ceilings.
> Crucially, all math is done in exact integer cents or fixed-point decimal arithmetic, completely avoiding binary floating-point rounding errors.
> I chose a pure functional rating engine design so that pricing can be evaluated both in batch during monthly invoicing and on-the-fly when customers request real-time cost estimates.
> If an invalid pricing configuration or negative quantity is passed, the engine throws an immediate ValueError.
> A current limitation is that currency conversion happens downstream rather than inside the rating engine, which I would unify in the next release."

---

## Feature 4: Append-Only Double-Entry Ledger (`models/ledger.py`)
> "I engineered the double-entry accounting ledger in models/ledger.py to provide complete financial auditability and eliminate silent balance drift. Every monetary event in the system—whether it is finalizing an invoice, collecting a credit card payment, or granting a promotional credit—must write a balanced double-entry transaction.
> My record_transaction method enforces two non-negotiable rules: first, every transaction must contain at least two entries, and second, the sum of all debits must strictly equal the sum of all credits in integer cents. If an invoice for $100 is finalized, it writes a debit of 10,000 cents to Accounts Receivable and a credit of 10,000 cents to Revenue.
> I chose double-entry bookkeeping over a simple mutable balance column because single-entry ledgers make it impossible to audit where funds originated or detect software corruption after the fact.
> If any component attempts to post an unbalanced transaction, my code raises a ValueError and the database transaction is aborted immediately.
> One limitation is that computing account balances requires summing historical entries, which I would optimize at higher scale by introducing daily materialized balance checkpoints."

---

## Feature 5: Invoicing Engine & Gapless Numbering (`invoicing/manager.py`)
> "I developed the invoicing engine in invoicing/manager.py to manage the complete lifecycle from draft usage aggregation to finalized customer bills. When a billing cycle closes, our system generates a draft invoice and appends itemized line items for metered usage, subscription base fees, discounts, and taxes.
> When the invoice is finalized, the manager locks the invoice into an immutable state so no further edits can occur. It calculates total cents using the formula: subtotal minus discounts minus credits plus tax.
> To satisfy strict accounting and legal compliance, it queries an invoice sequences table with row-level locking to assign a gapless sequential number formatted as INV-year-number, guaranteeing no numbers are skipped even under concurrent finalization requests.
> Simultaneously, it triggers a double-entry ledger posting to debit Accounts Receivable and credit Revenue.
> I chose this multi-stage lifecycle (Draft to Finalized to Paid or Void) because enterprise finance teams require the ability to review and adjust draft line items before locking legal fiscal records.
> If someone attempts to modify a finalized invoice, the method raises a 400 Bad Request error.
> A limitation is that invoice PDF rendering currently relies on the browser's print engine, which I plan to supplement with a server-side PDF generator."

---

## Feature 6: Payments, Retries & Dunning (`payments/collections.py`)
> "I built the collections and dunning engine in payments/collections.py to automate payment settlements and recover revenue from failed transactions. When an invoice comes due, our system issues a two-step payment authorization followed by capture.
> If a payment fails due to an expired card or insufficient funds, the system does not simply disconnect the customer; instead, it enters an automated dunning workflow. It schedules retries across a defined schedule—immediately on Day 0, followed by retries on Day 3 and Day 7, and a final escalation on Day 14.
> During this window, the account is marked PAST_DUE, giving the customer a grace period to update their payment method. If the grace period expires without settlement, the account standing transitions to SUSPENDED.
> I chose a two-step authorization and capture model because it allows us to verify funds before locking invoices, and enables partial captures if disputes arise.
> Every payment attempt logs an idempotency key and attempt record, guaranteeing that network glitches cannot cause a customer to be charged twice.
> A current limitation is that we use a local gateway sandbox for tests, which I would connect to Stripe Billing and webhooks for live production operations."

---

## Feature 7: Aggregation & Billing Periods (`aggregation/periods.py`)
> "I designed the aggregation and periods engine in aggregation/periods.py to manage the lifecycle of billing cycles and aggregate high-volume telemetry. A customer's consumption is divided into distinct billing periods that transition from OPEN to CLOSING and finally CLOSED.
> While a period is open, incoming events increment pre-aggregated hourly rollups so dashboard queries return in milliseconds. However, during end-of-month closing, our engine runs a differential test: it executes recompute_from_scratch, which performs a direct SQL sum over raw usage events to prove that pre-aggregated rollups match raw telemetry exactly.
> If out-of-order events arrive after a billing period has already closed, the system does not modify historical invoices; instead, it rolls them into the active period as a prior-period adjustment.
> I chose to maintain both pre-aggregated rollups and immutable raw events because fast UI queries require caching, but financial audits demand a verifiable raw paper trail.
> If dates are inverted or overlapping periods are submitted, the manager raises a clean validation error.
> A trade-off is that storing both raw events and rollups increases database storage footprint, which is managed via table partitioning."

---

## Feature 8: Subscription Lifecycle & Proration (`models/proration.py`)
> "I engineered the proration engine in models/proration.py to eliminate billing disputes when customers upgrade or downgrade subscription plans mid-month. When a customer upgrades from a $50 plan to a $200 plan halfway through the month, calculating the charge by hand or using floating-point math causes rounding discrepancies.
> My calculate_proration function computes the exact total seconds and remaining seconds in the billing window. It calculates the remaining fraction using Python's Decimal module and computes two values: the unused credit from the previous plan and the new plan charge for the remaining duration. Both are quantized to integer cents using standard financial ROUND_HALF_UP arithmetic.
> The difference gives the net proration cents, which is added directly as a credit or charge line item on the customer's next invoice.
> I chose second-level precision with Decimal arithmetic over daily integer ratios because cloud services need exact pro-rata calculations when upgrades happen at any time of day.
> If an invalid time range is passed where end is before start, the function raises a ValueError.
> One limitation is that leap seconds are not modeled, which has negligible financial impact but is documented in our spec."

---

## Feature 9: Security, RBAC & Audit Logging (`security/auth.py`, `security/audit.py`)
> "I built the security and audit layer in security/auth.py and security/audit.py to meet enterprise compliance standards like SOC 2 and GDPR. The authentication system uses cryptographically generated API keys. The raw key is shown only once to the user upon creation; our database stores only the SHA-256 hash, ensuring that even a database dump cannot expose plaintext credentials.
> We implement strict deny-by-default RBAC across four distinct roles: Owner, Finance, Viewer, and Service. For example, a Service role can ingest usage events but cannot view customer invoices, while a Finance role can finalize invoices and capture payments.
> Additionally, our audit logger tracks every state mutation with the actor, action, and before-and-after states. Before writing to the database, a recursive sanitizer scans all payload keys and strings using regular expressions, automatically redacting tax IDs, Social Security numbers, and credit card numbers with [REDACTED].
> I chose this built-in RBAC and audit framework over generic third-party auth because financial billing systems require deep domain-level permission scopes.
> If an unauthorized role attempts a mutation, the system rejects it with a 403 Forbidden.
> A limitation is that keys are currently static; I plan to introduce automated 90-day key rotation in the next milestone."

---

## Feature 10: Customer Billing Console Frontend (`frontend/src/app.js`)
> "I created the customer billing console in frontend/src/app.js, index.html, and index.css to give tenant administrators and finance teams real-time visibility into their billing operations. The console features a responsive KPI dashboard that displays gross revenue, Monthly Recurring Revenue, Annual Recurring Revenue, and unpaid invoice totals.
> Users can filter through an interactive invoice catalog by status—such as Draft, Finalized, or Paid—and click on any invoice to inspect a complete line-item breakdown showing exact quantities, unit rates, subtotal, discounts, and taxes.
> Finance managers can also click to finalize draft invoices directly from the UI, updating the status and displaying the newly assigned legal sequential number in real time.
> I chose vanilla JavaScript, HTML5, and pure CSS custom properties over a heavy frontend framework to keep the bundle size practically zero, eliminate build step complexity, and ensure the console loads in under 100 milliseconds.
> If the backend API is unreachable, the console displays non-intrusive fallback indicators without crashing.
> A limitation is that views are switched by toggling CSS display styles rather than URL hash routing, which I would enhance with a lightweight client router in the future."

---

## Rehearsal Checklist

Tick each box once you have explained the feature out loud, without referring to notes, under the recommended time:

- [ ] **30-Second Project Elevator Pitch** (<30 seconds)
- [ ] **2-Minute Technical Architecture Pitch** (<2 minutes)
- [ ] **F1: Usage Event Store & Idempotency** (<90 seconds)
- [ ] **F2: Idempotent Ingestion Pipeline** (<90 seconds)
- [ ] **F3: Multi-Tiered Rating Engine** (<90 seconds)
- [ ] **F4: Append-Only Double-Entry Ledger** (<90 seconds)
- [ ] **F5: Invoicing Engine & Gapless Numbering** (<90 seconds)
- [ ] **F6: Payments, Retries & Dunning Schedule** (<90 seconds)
- [ ] **F7: Aggregation Engine & Period Lifecycle** (<90 seconds)
- [ ] **F8: Subscription Lifecycle & Exact Proration** (<90 seconds)
- [ ] **F9: Security, RBAC & Sanitized Audit Logging** (<90 seconds)
- [ ] **F10: Customer Billing Console Frontend** (<90 seconds)
