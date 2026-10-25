# Project Type Detection & Adaptation Track

## Step 0 Pre-Check: Codebase Analysis & Classification

This document records the formal inspection and architectural classification of `19-usage-billing-engine`.

---

### Detection Evidence

A comprehensive inspection of `/Users/avishjain/avishjain9-repos/19-usage-billing-engine` was conducted across filesystem structure, dependencies, configuration files, and source code:

| Artifact Checked | Findings / Content | Classification Evidence |
| :--- | :--- | :--- |
| **Directory Name** | `19-usage-billing-engine` | High-throughput metered billing, rating, and double-entry financial engine. |
| **Backend Implementation** | `backend/src/` (`api/app.py`, `metering/`, `rating/`, `invoicing/`, `models/`, `payments/`, `security/`) | Python 3.13, FastAPI REST API framework, SQLAlchemy 2.0 Async, Pydantic v2 validation. |
| **Database Architecture** | `backend/src/db/database.py`, `backend/src/models/` | PostgreSQL 16 (production time-partitioned tables) / SQLite (`aiosqlite` testing), Redis counters. |
| **Frontend Implementation** | `frontend/src/` (`app.js`, `index.html`, `index.css`) | Vanilla ES6+ JavaScript, CSS3 responsive grid with dark mode theme variables, HTML5. |
| **Test Suite** | `backend/tests/` (50 test files), `frontend/tests/` (2 test files) | 87 passing unit & integration tests executed via `pytest-asyncio`. |
| **Package Manifests** | Root `package.json` (`vitepress`, `mermaid`), `backend/` Python imports | Node.js documentation toolchain + Pure Python asynchronous backend. |

---

### Formal Classification

- **Primary Classification**: **Track C: Non-MERN Backend & Financial Systems Engine**
  - **Backend**: Python 3.13, FastAPI, SQLAlchemy 2.0 (Async), Pydantic v2, PostgreSQL 16, Redis.
  - **Frontend**: Vanilla JavaScript (ES6+), HTML5, CSS3 Billing Dashboard & Invoice Inspector.
- **Financial Architecture Specializations**:
  - High-throughput idempotent usage event ingestion pipeline (`metering/ingestion.py`).
  - Multi-tier dynamic rating engine (`rating/engine.py`: volume, graduated, overage, free tiers).
  - Append-only double-entry bookkeeping ledger (`models/ledger.py`) with debit-credit conservation.
  - Automated billing cycle reconciliation, invoice finalization, and gapless sequential numbering (`invoicing/manager.py`).
  - Two-step payment authorization/capture, dunning workflow, and grace period lifecycle (`payments/collections.py`).

---

### Track Adaptation & Document Mapping Rules

Per the adaptation instructions for Track C:
1. **MERN Terminology Substitution**:
   - Replaced MongoDB / Mongoose with **PostgreSQL 16 time-partitioned tables**, SQLAlchemy 2.0 async sessions, and raw SQL indexing.
   - Replaced Express middleware with **FastAPI dependencies and Starlette CORS middleware**.
   - Replaced React Redux / Context with **Vanilla ES6+ state management and DOM updates**.
2. **Deep Dives Applied**:
   - Concurrency control: Row-level locking (`SELECT ... FOR UPDATE`) for gapless invoice numbering.
   - Financial invariants: Strict integer cents / Decimal `ROUND_HALF_UP` arithmetic, eliminating floating-point rounding drift.
   - Double-entry accounting: Every ledger transaction enforces `len(entries) >= 2` and `sum(debits) == sum(credits)`.
   - Data partitioning: Monthly range partitioning on `usage_events` with verified query plan partition pruning.
