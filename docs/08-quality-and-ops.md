# Engineering Quality, Testing & Operations

## 1. Automated Testing Pyramid
The repository maintains a rigorous test suite comprising 87 automated tests across 52 test files, achieving comprehensive coverage across core financial and ingestion modules.

| Test Layer | Test Count | Key Scenarios Covered |
| :--- | :--- | :--- |
| **Unit Tests** | 48 tests | Decimal rounding precision, graduated bracket tier math, unit conversions, timestamp drift window rejection. |
| **Integration Tests** | 29 tests | End-to-end event ingestion through database persistence, invoice finalization, ledger balance verification. |
| **Differential Tests** | 10 tests | Proof that recomputed raw event sums strictly equal pre-aggregated hourly and daily rollups. |

### Running the Test Suite
```bash
PYTHONPATH=backend/src pytest -v
```

---

## 2. Concurrency & Race Condition Safeguards
- **Gapless Invoice Numbering**: Uses PostgreSQL `SELECT ... FOR UPDATE` on `invoice_sequences` to serialize concurrent finalization requests, preventing duplicate or skipped numbers.
- **Idempotency Keys**: Database-level composite unique index (`ix_tenant_idem`) catches concurrent duplicate requests at the storage engine level, returning cached responses safely.
- **Atomic Balance Updates**: Double-entry ledger transactions post both debit and credit entries inside a single atomic database transaction.

---

## 3. Production Deployment & Monitoring
- **Containerization**: Standard multi-stage `Dockerfile` running Python 3.13 on Debian slim with non-root user execution.
- **Prometheus Metrics**:
  - `billing_events_ingested_total{tenant_id, status}`: Rate of incoming events.
  - `billing_rating_latency_seconds`: Time taken to evaluate price books.
  - `billing_invoices_finalized_total`: Counter of finalized billing cycles.
  - `billing_ledger_imbalance_errors`: Alert gauge triggering immediate P0 alarm if debits $\neq$ credits.
