# Security Architecture & OWASP Top 10 Audit

Financial billing platforms are primary targets for credential stuffing, unauthorized balance manipulation, and invoice tampering. This document audits `19-usage-billing-engine` against the OWASP Top 10.

---

## OWASP Top 10 Mapping & Defenses

| Vulnerability | Status in Code | Defense Mechanism Implemented |
| :--- | :--- | :--- |
| **A01: Broken Access Control** | **Protected** | Deny-by-default RBAC (`security/auth.py`). All database queries explicitly filter by `tenant_id`, preventing cross-tenant data leakage. |
| **A02: Cryptographic Failures** | **Protected** | API keys are hashed with SHA-256 before storage (`AuthManager._hash_key`); plaintext keys are never persisted. |
| **A03: Injection** | **Protected** | SQLAlchemy parameterized queries eliminate SQL injection; Pydantic model validators sanitize inputs. |
| **A04: Insecure Design** | **Protected** | Double-entry ledger enforces balance conservation; negative quantities rejected at DB schema level. |
| **A05: Security Misconfiguration** | **Protected** | Debug mode disabled in production; Starlette CORS restricted to authorized billing console origins. |
| **A06: Vulnerable Components** | **Protected** | Python 3.13 and updated Pydantic v2 libraries scanned via `pip-audit`. |
| **A07: Identification & Auth** | **Protected** | Random 32-byte cryptographically secure tokens (`secrets.token_urlsafe`); revoked keys rejected immediately. |
| **A08: Software & Data Integrity** | **Protected** | Finalized invoices and ledger transactions are immutable; updates and deletes prohibited. |
| **A09: Logging & Monitoring** | **Protected** | Audit logger (`security/audit.py`) records all mutations, automatically masking PII, Tax IDs, and card numbers. |
| **A10: SSRF** | **Protected** | External webhook URLs validated against strict allowlists before dispatch. |

---

## Financial Ledger Immutability & Anti-Tamper Controls
1. **Append-Only Enforcement**: The `ledger_entries` table permits only `INSERT` statements. Corrections must be submitted as new reversing entries referencing the original transaction.
2. **Check Constraints**: Schemas enforce `amount_cents > 0` on ledger entries and `quantity >= 0` on usage events, preventing negative balance manipulation.
3. **Automated PII Redaction**: Before any audit record is persisted, `redact_sensitive_info()` recursively scrubs tax IDs, SSNs, credit card numbers, and passwords using regular expression filters.
