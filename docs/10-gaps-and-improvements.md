# Gaps & Roadmap Improvements

This document prioritizes architectural enhancements and missing enterprise features ranked by operational impact.

---

## Priority Matrix

| Priority | Feature / Gap | Current State | Target State & Suggested Fix |
| :--- | :--- | :--- | :--- |
| **P0** | **Streaming Buffer (Kafka / Kinesis)** | Synchronous DB inserts | Deploy Apache Kafka in front of FastAPI ingestion nodes; workers consume in micro-batches of 1,000 events. |
| **P0** | **Production Payment Gateway Webhooks**| Sandbox mock gateway | Wire Stripe / Adyen webhook listeners with HMAC-SHA256 signature verification and replay tables. |
| **P1** | **Automated Multi-Jurisdiction Tax** | Fixed tax rate line items | Integrate Stripe Tax or Avalara AvaTax API to dynamically compute sales tax and VAT based on customer address. |
| **P1** | **Redis Bloom Filter Deduplication** | DB B-tree index checks | Add Redis scalable Bloom filter to reject duplicate idempotency keys in memory before querying PostgreSQL. |
| **P2** | **Server-Side PDF Invoicing** | Browser print stylesheet | Implement headless Chromium worker (Playwright / Weasyprint) generating signed PDF/A archival documents. |
| **P2** | **Materialized Ledger Checkpoints** | Historical entry summing | Create daily scheduled worker computing account balance snapshots to accelerate balance reconciliation. |
| **P3** | **Interactive Pricing Sandbox** | Static UI console | Build drag-and-drop React pricing builder allowing product managers to simulate revenue across tier changes. |
