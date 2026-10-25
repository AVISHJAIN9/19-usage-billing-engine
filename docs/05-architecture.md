# System Architecture & Scalability

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
- **100x Load**: 50,000 events/second ($4.3 \text{ billion events/month}$), 1,000,000 monthly invoices.

### Top 3 Bottlenecks & Architectural Remedies

| Bottleneck Rank | Vulnerable Component | Failure Mode at 100x | Senior Engineer Remediation |
| :--- | :--- | :--- | :--- |
| **1** | **Synchronous PostgreSQL Ingestion** | B-tree index contention on `ix_tenant_idem` causes database lock exhaustion. | Introduce Apache Kafka or AWS Kinesis buffer in front of workers, batching DB writes into multi-row 1,000-event inserts. |
| **2** | **Invoice Sequence Row Locking** | `SELECT ... FOR UPDATE` on `invoice_sequences` serializes finalization to ~100 invoices/sec. | Partition sequence counters by tenant shard or allocate pre-fetched block ranges (Hi/Lo sequence algorithm). |
| **3** | **Differential Usage Recompute** | Running SQL `SUM(quantity)` across 50M raw rows during period close causes query timeouts. | Transition to continuous tumbling stream aggregates in Redis / Apache Flink, using PostgreSQL only for cold storage. |
