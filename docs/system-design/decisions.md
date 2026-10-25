# Architecture Decision Records (ADR Log)

This log records all fundamental design and architecture decisions made in `19-usage-billing-engine`.

---

| ADR ID | Decision Title | Chosen Option | Alternatives Considered | Deciding Factors | Trade-offs Accepted | Revisit When |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **ADR-01** | **Monetary Unit Representation** | **Integer Minor Units (Cents) + Decimal** | IEEE 754 Floats, String Math | Elimination of binary floating-point rounding errors | Explicit conversion required when displaying dollars in UI | Multi-currency requiring fractional minor units (e.g. crypto/tokens) |
| **ADR-02** | **Primary Database Engine** | **PostgreSQL 16 with Range Partitioning** | MongoDB, MySQL, DynamoDB, CockroachDB | Strict ACID guarantees, row-level locking, and native table partitioning | Vertical primary node capacity limits | Ingestion exceeds 50,000 QPS sustainably |
| **ADR-03** | **Architecture Style** | **Modular Monolith** | Distributed Microservices, Serverless | Single atomic database commit across invoices and double-entry ledger | Ingestion and invoicing share server resources | Telemetry ingestion requires independent auto-scaling clusters |
| **ADR-04** | **Ledger Bookkeeping Paradigm** | **Append-Only Double-Entry Journal** | Single-Entry Mutable Balances | Complete auditability; debit-credit conservation guarantees | Higher storage growth; balance calculation requires summing entries | Historical entries exceed 500 million rows (requires materialized snapshots) |
| **ADR-05** | **Idempotency Deduplication** | **Database Unique Index (`ix_tenant_idem`)** | In-Memory Set, Client Session Tokens | Persistence across server restarts and crashes | Synchronous database write latency on every event | Ingestion latency requirements drop below 5 milliseconds |
| **ADR-06** | **Invoice Sequence Numbering** | **Row-Level Lock (`SELECT ... FOR UPDATE`)** | Distributed UUIDs, Unchecked Auto-Increment | Legal fiscal requirement for gapless sequence numbers | Serialized queue under concurrent invoice finalizations | Finalizations exceed 500 invoices per second per tenant |
| **ADR-07** | **Proration Calculation Granularity**| **Second-Exact Ratio with `ROUND_HALF_UP`** | Day-based ratios, Half-month brackets | Fair billing for mid-cycle upgrades at any hour of day | Slightly higher arithmetic calculation overhead | Never; standard financial practice |
| **ADR-08** | **Audit Log Security & PII** | **Recursive Regex Sanitization** | Storing Raw Diffs, External KMS field encryption | Prevention of credit card and tax ID leakage into logs | Regex scanning overhead on mutation writes | High-throughput bulk administrative migrations |
| **ADR-09** | **Billing Console Framework** | **Vanilla ES6+ JavaScript, HTML5 & CSS** | React 18, Vue 3, Next.js | Zero build step complexity, instant load time (<100ms), 10KB bundle size | Manual DOM manipulation instead of reactive component state | Console features expand to complex multi-screen enterprise portal |
| **ADR-10** | **Documentation Toolchain** | **VitePress with withMermaid Plugin** | Docusaurus, MkDocs, GitBook | Fast Vue.js-style static rendering with pure-black dark theme and Mermaid diagrams | Node.js toolchain required for documentation builds | Never; VitePress provides superior developer documentation experience |
