# Financial Systems Design: Metered Billing & Rating Engine

Welcome to the comprehensive Systems Design guide for `19-usage-billing-engine`. This documentation series analyzes how an enterprise financial metering, rating, and invoicing platform operates under extreme scale.

---

## System Design Chapter Index

| Chapter | Topic | Focus & Architectural Scope |
| :--- | :--- | :--- |
| **14.1** | [Requirements & Capacity Estimation](./14.1-requirements-and-estimation.md) | Functional/Non-functional requirements and mathematical load modeling. |
| **14.2** | [Architecture Styles & Ingestion Pipes](./14.2-architecture-styles.md) | Modular monolith, event-driven streaming, and service decomposition. |
| **14.3** | [Networking & Communication Protocols](./14.3-networking-and-communication.md) | Reverse proxies, HTTP/1.1 vs HTTP/2/3, REST vs gRPC vs SSE. |
| **14.4** | [Load Balancing & Tenant Partitioning](./14.4-load-balancing-and-scaling.md) | Layer 7 load balancing, tenant hashing, and horizontal worker autoscaling. |
| **14.5** | [Databases & Immutable Financial Ledgers](./14.5-databases-and-storage.md) | PostgreSQL range partitioning, double-entry schemas, and B-tree indexing. |
| **14.6** | [Caching & Idempotency Key Stores](./14.6-caching.md) | Write-Through Redis caches, Bloom filters, and cache stampede prevention. |
| **14.7** | [Messaging, Queues & Stream Processing](./14.7-messaging-and-queues.md) | Kafka / Redis Streams event log, tumbling aggregation windows, and DLQs. |
| **14.8** | [Consistency, Concurrency & Locking](./14.8-consistency-and-concurrency.md) | ACID transactions, `SELECT ... FOR UPDATE`, and debit-credit conservation. |
| **14.9** | [Reliability, Resilience & Audits](./14.9-reliability-and-resilience.md) | Circuit breakers, retry backoff, and daily differential reconciliation jobs. |
| **14.10**| [API Design & Rate Limiting](./14.10-api-design-and-rate-limiting.md) | Idempotency headers, batch ingestion, and token bucket rate limiters. |
| **14.11**| [Security, Multi-Tenancy & SOX Compliance](./14.11-security-architecture.md) | Row-level tenant isolation, SHA-256 API keys, and automated PII scrubbing. |
| **14.12**| [Search, Anomaly Detection & AI](./14.12-search-and-ai-architecture.md) | Holt-Winters spend forecasting and LLM dispute explanation copilots. |
| **14.13**| [Real-Time Telemetry & Drawdowns](./14.13-real-time-systems.md) | Redis atomic counters and sub-second prepaid credit wallet drawdowns. |
| **14.14**| [Observability & Operations](./14.14-observability-and-operations.md) | Structured audit logs, Prometheus metrics, and deployment pipelines. |
| **14.15**| [Performance Engineering & Precision](./14.15-performance-engineering.md) | Fixed-point integer cents vs IEEE 754 floats and benchmark analysis. |
| **14.16**| [Cost Modeling & Infrastructure Scaling](./14.16-cost-and-trade-offs.md) | Financial cost breakdown at current scale vs 100x ($340 vs $3,200/mo). |
| **14.17**| [Classic System Design Scenarios](./14.17-classic-system-design.md) | Designing AWS CloudWatch Billing, Stripe Invoicing, and Rate Limiters. |
| **ADR**  | [Architecture Decision Records (ADR)](./decisions.md) | Formal log of all major architectural decisions and trade-offs. |
