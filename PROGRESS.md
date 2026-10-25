# Project Progress: 19-usage-billing-engine

**Total Features:** 90 | **TODO:** 0 | **WORKING:** 0 | **COMPLETED:** 90

*Last updated: 2026-10-24T16:23:44.191383+00:00*

### Area Database & Distributed Infrastructure

| ID | Feature | State | Started | Completed | Verification | Tests | Notes |
|---|---|---|---|---|---|---|---|
| BIL-001 | Usage event store | COMPLETED | 2026-10-24T10:56:20.233757+00:00 | 2026-10-24T10:59:24.067682+00:00 | REAL | backend/tests/test_usage_event_store.py::test_BIL_001_usage_event_store | Usage event store with dimension serialization and tenant idempotency |
| BIL-003 | Relational billing store | COMPLETED | 2026-10-24T10:56:20.328409+00:00 | 2026-10-24T10:59:57.211199+00:00 | REAL | backend/tests/test_relational_billing_store.py::test_BIL_003_relational_billing_store | Relational billing store for customer accounts and subscriptions |
| BIL-006 | Ledger database | COMPLETED | 2026-10-24T10:56:20.399811+00:00 | 2026-10-24T11:00:23.389506+00:00 | REAL | backend/tests/test_ledger_database.py::test_BIL_006_ledger_database | Double-entry append-only ledger database enforcing debit-credit conservation |
| BIL-005 | Payment database | COMPLETED | 2026-10-24T15:39:37.009770+00:00 | 2026-10-24T15:43:46.840327+00:00 | REAL | backend/tests/test_database_distributed_infrastructure.py::test_BIL_005_payment_database | Payment database schema and manager with positive amount checks, idempotency, and status lifecycle |
| BIL-009 | Indexes for usage queries | COMPLETED | 2026-10-24T15:39:37.086350+00:00 | 2026-10-24T15:43:52.464049+00:00 | REAL | backend/tests/test_database_distributed_infrastructure.py::test_BIL_009_indexes_for_usage_queries | Composite indexes for usage queries verified via EXPLAIN QUERY PLAN |
| BIL-010 | Partitioning | COMPLETED | 2026-10-24T15:39:37.165327+00:00 | 2026-10-24T15:43:58.629546+00:00 | REAL | backend/tests/test_database_distributed_infrastructure.py::test_BIL_010_partitioning | Monthly range partitioning engine with EXPLAIN proving query partition pruning |

### Area Accounts, Plans & Entitlements

| ID | Feature | State | Started | Completed | Verification | Tests | Notes |
|---|---|---|---|---|---|---|---|
| BIL-013 | Customer accounts | COMPLETED | 2026-10-24T11:06:50.944978+00:00 | 2026-10-24T11:07:02.997235+00:00 | REAL | backend/tests/test_customer_accounts.py | - |
| BIL-017 | Subscription model | COMPLETED | 2026-10-24T11:07:12.258995+00:00 | 2026-10-24T11:07:14.414563+00:00 | REAL | backend/tests/test_subscription_model.py | - |
| BIL-019 | Plan assignment | COMPLETED | 2026-10-24T11:07:14.496814+00:00 | 2026-10-24T11:07:15.706906+00:00 | REAL | backend/tests/test_plan_assignment.py | - |

### Area Usage Metering Core

| ID | Feature | State | Started | Completed | Verification | Tests | Notes |
|---|---|---|---|---|---|---|---|
| BIL-026 | Usage event ingestion | COMPLETED | 2026-10-24T11:09:19.822560+00:00 | 2026-10-24T11:09:20.776980+00:00 | REAL | backend/tests/test_usage_event_ingestion.py | - |
| BIL-027 | Event schema validation | COMPLETED | 2026-10-24T11:09:20.843000+00:00 | 2026-10-24T11:09:21.532474+00:00 | REAL | backend/tests/test_event_schema_validation.py | - |
| BIL-030 | Event deduplication | COMPLETED | 2026-10-24T11:09:21.597556+00:00 | 2026-10-24T11:09:22.275567+00:00 | REAL | backend/tests/test_event_deduplication.py | - |
| BIL-031 | Idempotency keys | COMPLETED | 2026-10-24T11:09:31.021049+00:00 | 2026-10-24T11:09:32.599976+00:00 | REAL | backend/tests/test_idempotency_keys.py | - |
| BIL-032 | Usage dimensions | COMPLETED | 2026-10-24T11:09:32.671299+00:00 | 2026-10-24T11:09:33.445208+00:00 | REAL | backend/tests/test_usage_dimensions.py | - |
| BIL-035 | Tenant attribution | COMPLETED | 2026-10-24T11:09:33.508454+00:00 | 2026-10-24T11:09:34.185834+00:00 | REAL | backend/tests/test_tenant_attribution.py | - |
| BIL-029 | Timestamp validation | COMPLETED | 2026-10-24T15:50:08.290436+00:00 | 2026-10-24T15:52:37.559078+00:00 | REAL | backend/tests/test_usage_metering_core.py::test_BIL_029_timestamp_validation | Usage timestamp boundary and clock drift validation with structured error codes |
| BIL-037 | Project attribution | COMPLETED | 2026-10-24T15:50:08.372575+00:00 | 2026-10-24T15:52:45.930520+00:00 | REAL | backend/tests/test_usage_metering_core.py::test_BIL_037_project_attribution | Metered usage attribution and aggregation by project_id within customer accounts |
| BIL-038 | Usage units | COMPLETED | 2026-10-24T15:50:08.449398+00:00 | 2026-10-24T15:52:52.405826+00:00 | REAL | backend/tests/test_usage_metering_core.py::test_BIL_038_usage_units_and_conversion | Explicit usage units model and conversion engine across storage, runtime, and tokens |

### Area Billing & Rating

| ID | Feature | State | Started | Completed | Verification | Tests | Notes |
|---|---|---|---|---|---|---|---|
| BIL-039 | Pricing plan model | COMPLETED | 2026-10-24T11:11:35.322807+00:00 | 2026-10-24T11:11:36.217747+00:00 | REAL | backend/tests/test_pricing_plan_model.py | - |
| BIL-041 | Price book | COMPLETED | 2026-10-24T11:11:36.280867+00:00 | 2026-10-24T11:11:36.991451+00:00 | REAL | backend/tests/test_price_book.py | - |
| BIL-042 | Metered pricing | COMPLETED | 2026-10-24T11:11:37.054594+00:00 | 2026-10-24T11:11:37.723071+00:00 | REAL | backend/tests/test_metered_pricing.py | - |
| BIL-043 | Flat subscription pricing | COMPLETED | 2026-10-24T11:11:37.786290+00:00 | 2026-10-24T11:11:38.439239+00:00 | REAL | backend/tests/test_flat_subscription_pricing.py | - |
| BIL-044 | Tiered pricing | COMPLETED | 2026-10-24T11:11:44.728262+00:00 | 2026-10-24T11:11:45.539274+00:00 | REAL | backend/tests/test_tiered_pricing.py | - |
| BIL-046 | Graduated pricing | COMPLETED | 2026-10-24T11:11:45.605378+00:00 | 2026-10-24T11:11:46.301015+00:00 | REAL | backend/tests/test_graduated_pricing.py | - |
| BIL-047 | Per-unit pricing | COMPLETED | 2026-10-24T11:11:46.364693+00:00 | 2026-10-24T11:11:47.111093+00:00 | REAL | backend/tests/test_per_unit_pricing.py | - |
| BIL-050 | Free tiers | COMPLETED | 2026-10-24T11:11:47.175524+00:00 | 2026-10-24T11:11:47.865531+00:00 | REAL | backend/tests/test_free_tiers.py | - |
| BIL-040 | Plan versioning | COMPLETED | 2026-10-24T15:53:09.864198+00:00 | 2026-10-24T15:56:58.854701+00:00 | REAL | backend/tests/test_billing_and_rating.py::test_BIL_040_plan_versioning_and_immutability | Immutable plan versioning with auto-incrementing versions and locked mutation prevention |
| BIL-045 | Volume pricing | COMPLETED | 2026-10-24T15:53:09.943810+00:00 | 2026-10-24T15:57:07.232815+00:00 | REAL | backend/tests/test_billing_and_rating.py::test_BIL_045_volume_pricing_hand_computed_table | Tiered volume pricing with hand-computed golden table verification |
| BIL-048 | Minimum charges | COMPLETED | 2026-10-24T15:53:10.015389+00:00 | 2026-10-24T15:57:15.736924+00:00 | REAL | backend/tests/test_billing_and_rating.py::test_BIL_048_minimum_charges_enforcement | Minimum charge floor enforcement verified against hand-computed test cases |
| BIL-049 | Maximum charges | COMPLETED | 2026-10-24T15:57:33.651799+00:00 | 2026-10-24T15:57:43.317419+00:00 | REAL | backend/tests/test_billing_and_rating.py::test_BIL_049_maximum_charges_enforcement | Maximum charge ceiling enforcement verified against hand-computed test cases |
| BIL-051 | Overage pricing | COMPLETED | 2026-10-24T15:57:33.725984+00:00 | 2026-10-24T15:57:53.609678+00:00 | REAL | backend/tests/test_billing_and_rating.py::test_BIL_051_overage_pricing_hand_computed_table | Overage pricing with included units and tiered excess rates verified against hand-computed tables |

### Area Aggregation & Periods

| ID | Feature | State | Started | Completed | Verification | Tests | Notes |
|---|---|---|---|---|---|---|---|
| BIL-054 | Monthly aggregation | COMPLETED | 2026-10-24T11:13:26.702235+00:00 | 2026-10-24T11:13:27.630945+00:00 | REAL | backend/tests/test_monthly_aggregation.py | - |
| BIL-055 | Billing-period lifecycle | COMPLETED | 2026-10-24T11:13:27.695269+00:00 | 2026-10-24T11:13:28.392142+00:00 | REAL | backend/tests/test_billing_period_lifecycle.py | - |
| BIL-057 | Usage rollups | COMPLETED | 2026-10-24T11:13:28.459546+00:00 | 2026-10-24T11:13:29.456773+00:00 | REAL | backend/tests/test_usage_rollups.py | - |
| BIL-064 | Period close | COMPLETED | 2026-10-24T11:13:29.521754+00:00 | 2026-10-24T11:13:30.279541+00:00 | REAL | backend/tests/test_period_close.py | - |
| BIL-052 | Hourly aggregation | COMPLETED | 2026-10-24T15:58:28.237898+00:00 | 2026-10-24T16:00:12.899242+00:00 | REAL | backend/tests/test_aggregation_and_periods.py::test_BIL_052_hourly_aggregation_differential_and_late_events | Hourly aggregation with late event reconciliation and differential test against raw recompute |
| BIL-053 | Daily aggregation | COMPLETED | 2026-10-24T15:58:28.313381+00:00 | 2026-10-24T16:00:22.844462+00:00 | REAL | backend/tests/test_aggregation_and_periods.py::test_BIL_053_daily_aggregation_differential_and_late_events | Daily aggregation with late event handling and differential validation against raw recompute |
| BIL-063 | Real-time usage counters | COMPLETED | 2026-10-24T15:58:28.387284+00:00 | 2026-10-24T16:00:32.848934+00:00 | REAL | backend/tests/test_aggregation_and_periods.py::test_BIL_063_realtime_usage_counters_and_postgres_reconciliation | Real-time usage counters with fast cache and Postgres reconciliation within documented bounds |

### Area Ledger & Financial Integrity

| ID | Feature | State | Started | Completed | Verification | Tests | Notes |
|---|---|---|---|---|---|---|---|
| BIL-070 | Double-entry accounting hooks | COMPLETED | 2026-10-24T11:15:18.633838+00:00 | 2026-10-24T11:15:19.533262+00:00 | REAL | backend/tests/test_double_entry_hooks.py | - |
| BIL-071 | Ledger transactions | COMPLETED | 2026-10-24T11:15:19.599556+00:00 | 2026-10-24T11:15:20.267519+00:00 | REAL | backend/tests/test_ledger_transactions.py | - |
| BIL-073 | Ledger reconciliation | COMPLETED | 2026-10-24T11:15:20.332919+00:00 | 2026-10-24T11:15:21.092025+00:00 | REAL | backend/tests/test_ledger_reconciliation.py | - |
| BIL-074 | Balance calculation | COMPLETED | 2026-10-24T11:15:27.656251+00:00 | 2026-10-24T11:15:28.454155+00:00 | REAL | backend/tests/test_balance_calculation.py | - |
| BIL-075 | Debit/credit entries | COMPLETED | 2026-10-24T11:15:28.520060+00:00 | 2026-10-24T11:15:29.232805+00:00 | REAL | backend/tests/test_debit_credit_entries.py | - |
| BIL-065 | Immutable usage ledger | COMPLETED | 2026-10-24T16:00:56.028998+00:00 | 2026-10-24T16:01:57.580784+00:00 | REAL | backend/tests/test_ledger_and_financial_integrity.py::test_BIL_065_immutable_usage_ledger_enforcement | Append-only immutable usage ledger enforced in DB triggers rejecting UPDATE and DELETE |
| BIL-066 | Charge ledger | COMPLETED | 2026-10-24T16:00:56.097207+00:00 | 2026-10-24T16:02:06.530253+00:00 | REAL | backend/tests/test_ledger_and_financial_integrity.py::test_BIL_066_charge_ledger_and_double_entry_balance | Charge ledger with immutable rated line items and double-entry balance verification |
| BIL-072 | Transaction IDs | COMPLETED | 2026-10-24T16:00:56.163537+00:00 | 2026-10-24T16:02:15.546840+00:00 | REAL | backend/tests/test_ledger_and_financial_integrity.py::test_BIL_072_unique_transaction_ids | Unique transaction IDs enforced with primary key and unique constraints |
| BIL-076 | Adjustment journal | COMPLETED | 2026-10-24T16:02:30.008883+00:00 | 2026-10-24T16:02:39.785253+00:00 | REAL | backend/tests/test_ledger_and_financial_integrity.py::test_BIL_076_adjustment_journal_preserves_original_transactions | Adjustment journal for non-destructive financial corrections preserving immutable transaction history |

### Area Invoicing

| ID | Feature | State | Started | Completed | Verification | Tests | Notes |
|---|---|---|---|---|---|---|---|
| BIL-077 | Invoice generation | COMPLETED | 2026-10-24T11:17:00.530134+00:00 | 2026-10-24T11:17:01.498891+00:00 | REAL | backend/tests/test_invoice_generation.py | - |
| BIL-079 | Invoice finalization | COMPLETED | 2026-10-24T11:17:01.567143+00:00 | 2026-10-24T11:17:02.295347+00:00 | REAL | backend/tests/test_invoice_finalization.py | - |
| BIL-080 | Invoice numbering | COMPLETED | 2026-10-24T11:17:02.362705+00:00 | 2026-10-24T11:17:03.065750+00:00 | REAL | backend/tests/test_invoice_numbering.py | - |
| BIL-081 | Invoice line items | COMPLETED | 2026-10-24T11:17:09.032914+00:00 | 2026-10-24T11:17:09.821376+00:00 | REAL | backend/tests/test_invoice_line_items.py | - |
| BIL-087 | Invoice totals | COMPLETED | 2026-10-24T11:17:09.883903+00:00 | 2026-10-24T11:17:10.574894+00:00 | REAL | backend/tests/test_invoice_totals.py | - |
| BIL-078 | Draft invoices | COMPLETED | 2026-10-24T16:03:06.970274+00:00 | 2026-10-24T16:04:39.950590+00:00 | REAL | backend/tests/test_invoicing.py::test_BIL_078_draft_invoices_lifecycle_and_immutability | Draft invoice lifecycle, mutation while in DRAFT, and immutability once FINALIZED |
| BIL-082 | Usage line-item generation | COMPLETED | 2026-10-24T16:03:07.050430+00:00 | 2026-10-24T16:04:50.294839+00:00 | REAL | backend/tests/test_invoicing.py::test_BIL_082_usage_line_item_generation | Metered usage line-item generation from rated usage with quantity and item amounts |
| BIL-083 | Subscription line items | COMPLETED | 2026-10-24T16:03:07.119919+00:00 | 2026-10-24T16:04:59.856577+00:00 | REAL | backend/tests/test_invoicing.py::test_BIL_083_subscription_line_items | Recurring subscription base fee line-item generation |
| BIL-084 | Discount line items | COMPLETED | 2026-10-24T16:05:14.605830+00:00 | 2026-10-24T16:05:26.780847+00:00 | REAL | backend/tests/test_invoicing.py::test_BIL_084_and_086_and_088_discounts_taxes_currencies_and_invariant | Discount line items deducted from subtotal following documented rule order |
| BIL-086 | Tax line items | COMPLETED | 2026-10-24T16:05:14.686527+00:00 | 2026-10-24T16:05:36.358478+00:00 | REAL | backend/tests/test_invoicing.py::test_BIL_084_and_086_and_088_discounts_taxes_currencies_and_invariant | Tax line items calculated on net taxable basis with integer half-up rounding |
| BIL-088 | Currency handling | COMPLETED | 2026-10-24T16:05:14.756289+00:00 | 2026-10-24T16:05:46.789366+00:00 | REAL | backend/tests/test_invoicing.py::test_BIL_084_and_086_and_088_discounts_taxes_currencies_and_invariant | ISO 4217 Currency handling in minor units with strict validation |

### Area Payments & Collections

| ID | Feature | State | Started | Completed | Verification | Tests | Notes |
|---|---|---|---|---|---|---|---|
| BIL-090 | Payment provider integration | COMPLETED | 2026-10-24T11:18:24.462775+00:00 | 2026-10-24T11:18:25.350500+00:00 | LOCAL_EQUIVALENT | backend/tests/test_payment_provider_integration.py | Relabeled REAL->LOCAL_EQUIVALENT: Payment provider integration verified against local sandbox gateway |
| BIL-095 | Payment webhooks | COMPLETED | 2026-10-24T11:18:25.413466+00:00 | 2026-10-24T11:18:26.118493+00:00 | LOCAL_EQUIVALENT | backend/tests/test_payment_webhooks.py | Relabeled REAL->LOCAL_EQUIVALENT: Payment webhooks verified against local webhook simulator |
| BIL-096 | Webhook idempotency | COMPLETED | 2026-10-24T11:18:26.182182+00:00 | 2026-10-24T11:18:26.914491+00:00 | REAL | backend/tests/test_webhook_idempotency.py | - |
| BIL-092 | Payment authorization | COMPLETED | 2026-10-24T16:06:13.753266+00:00 | 2026-10-24T16:10:15.721147+00:00 | REAL | backend/tests/test_payments_and_collections.py::test_BIL_092_and_093_payment_authorization_and_capture | Payment authorization with funds hold and idempotency enforcement |
| BIL-093 | Payment capture | COMPLETED | 2026-10-24T16:06:13.824622+00:00 | 2026-10-24T16:10:28.132220+00:00 | REAL | backend/tests/test_payments_and_collections.py::test_BIL_092_and_093_payment_authorization_and_capture | Payment capture validating against authorized amount and settling invoices |
| BIL-097 | Payment retries | COMPLETED | 2026-10-24T16:06:13.891738+00:00 | 2026-10-24T16:10:38.107560+00:00 | REAL | backend/tests/test_payments_and_collections.py::test_BIL_097_and_098_payment_retries_and_failure_handling | Idempotent payment retries with structured attempt tracking |
| BIL-098 | Failed-payment handling | COMPLETED | 2026-10-24T16:10:51.746980+00:00 | 2026-10-24T16:11:04.096997+00:00 | REAL | backend/tests/test_payments_and_collections.py::test_BIL_097_and_098_payment_retries_and_failure_handling | Failed-payment classification and reason code persistence |
| BIL-099 | Dunning workflow | COMPLETED | 2026-10-24T16:10:51.822660+00:00 | 2026-10-24T16:11:14.855897+00:00 | REAL | backend/tests/test_payments_and_collections.py::test_BIL_099_and_100_dunning_and_grace_period_manual_clock | Dunning schedule stage progression driven by injectable manual clock |
| BIL-100 | Grace period | COMPLETED | 2026-10-24T16:10:51.891241+00:00 | 2026-10-24T16:11:25.263837+00:00 | REAL | backend/tests/test_payments_and_collections.py::test_BIL_099_and_100_dunning_and_grace_period_manual_clock | Grace period enforcement transitioning past-due accounts to suspended status on manual clock |
| BIL-101 | Automatic collection | COMPLETED | 2026-10-24T16:11:41.183091+00:00 | 2026-10-24T16:11:52.940325+00:00 | REAL | backend/tests/test_payments_and_collections.py::test_BIL_101_automatic_collection_idempotent | Automatic collection of due invoices with idempotent settlement |

### Area Backend APIs & Services

| ID | Feature | State | Started | Completed | Verification | Tests | Notes |
|---|---|---|---|---|---|---|---|
| BIL-103 | Usage ingestion API | COMPLETED | 2026-10-24T11:19:54.604775+00:00 | 2026-10-24T11:19:55.777992+00:00 | REAL | backend/tests/test_usage_ingestion_api.py | - |
| BIL-108 | Invoice API | COMPLETED | 2026-10-24T11:19:55.842427+00:00 | 2026-10-24T11:19:56.818303+00:00 | REAL | backend/tests/test_invoice_api.py | - |
| BIL-104 | Meter API | COMPLETED | 2026-10-24T16:12:23.442391+00:00 | 2026-10-24T16:15:47.662208+00:00 | REAL | backend/tests/test_backend_apis_and_services.py::test_BIL_104_meter_api | Meter REST API endpoints for meter creation, lookup, and listing |
| BIL-106 | Rating API | COMPLETED | 2026-10-24T16:12:23.515574+00:00 | 2026-10-24T16:15:59.544211+00:00 | REAL | backend/tests/test_backend_apis_and_services.py::test_BIL_106_rating_api | Rating REST API for dynamic rate calculation and price book catalogs |
| BIL-107 | Usage query API | COMPLETED | 2026-10-24T16:12:23.582122+00:00 | 2026-10-24T16:16:13.268057+00:00 | REAL | backend/tests/test_backend_apis_and_services.py::test_BIL_107_usage_query_api | Usage query API providing aggregated metered metrics across time intervals |
| BIL-109 | Payment API | COMPLETED | 2026-10-24T16:16:26.712554+00:00 | 2026-10-24T16:16:39.853269+00:00 | REAL | backend/tests/test_backend_apis_and_services.py::test_BIL_109_payment_api | Payment authorization and capture REST endpoints with idempotency |
| BIL-110 | Subscription API | COMPLETED | 2026-10-24T16:16:26.812102+00:00 | 2026-10-24T16:16:50.122013+00:00 | REAL | backend/tests/test_backend_apis_and_services.py::test_BIL_110_subscription_api | Subscription REST API for creation, lookup, and mid-cycle plan upgrades with proration |

### Area Frontend & Billing Console

| ID | Feature | State | Started | Completed | Verification | Tests | Notes |
|---|---|---|---|---|---|---|---|
| BIL-146 | Invoice detail | COMPLETED | 2026-10-24T11:22:12.125075+00:00 | 2026-10-24T11:22:13.353302+00:00 | REAL | frontend/tests/test_invoice_detail_console.py | - |
| BIL-139 | Billing dashboard | COMPLETED | 2026-10-24T16:21:09.851110+00:00 | 2026-10-24T16:23:20.365564+00:00 | REAL | frontend/tests/test_billing_dashboard_and_invoice_list.py::test_BIL_139_dashboard_api | Billing executive dashboard with gross revenue, MRR, ARR, active subscriptions, and unpaid counters |
| BIL-145 | Invoice list | COMPLETED | 2026-10-24T16:21:09.934570+00:00 | 2026-10-24T16:23:44.184737+00:00 | REAL | frontend/tests/test_billing_dashboard_and_invoice_list.py::test_BIL_145_invoice_list_api_and_filtering | Interactive invoice list catalog with status filters and detail routing |

### Area Accounts

| ID | Feature | State | Started | Completed | Verification | Tests | Notes |
|---|---|---|---|---|---|---|---|
| BIL-018 | Subscription lifecycle | COMPLETED | 2026-10-24T15:44:16.511664+00:00 | 2026-10-24T15:47:19.705436+00:00 | REAL | backend/tests/test_subscription_lifecycle_proration.py::test_BIL_018_subscription_lifecycle | Subscription lifecycle state machine transitions across active, paused, canceled |
| BIL-020 | Plan upgrades | COMPLETED | 2026-10-24T15:44:16.598352+00:00 | 2026-10-24T15:47:25.470092+00:00 | REAL | backend/tests/test_subscription_lifecycle_proration.py::test_BIL_020_plan_upgrades_with_hand_computed_proration | Mid-cycle plan upgrade with pro-rata charge verified against hand-computed golden values |
| BIL-021 | Plan downgrades | COMPLETED | 2026-10-24T15:44:16.669735+00:00 | 2026-10-24T15:47:31.589062+00:00 | REAL | backend/tests/test_subscription_lifecycle_proration.py::test_BIL_021_plan_downgrades_with_hand_computed_credit | Mid-cycle plan downgrade with pro-rata credit verified against hand-computed golden values |
| BIL-022 | Plan cancellation | COMPLETED | 2026-10-24T15:47:47.850176+00:00 | 2026-10-24T15:49:38.360571+00:00 | REAL | backend/tests/test_subscription_lifecycle_proration.py::test_BIL_022_plan_cancellation_with_hand_computed_credit | Subscription cancellation with hand-computed pro-rata credit calculation |
| BIL-023 | Plan pause/resume | COMPLETED | 2026-10-24T15:47:47.950022+00:00 | 2026-10-24T15:49:44.281399+00:00 | REAL | backend/tests/test_subscription_lifecycle_proration.py::test_BIL_023_plan_pause_and_resume_period_extension | Subscription pause and resume with exact period duration extension |
| BIL-024 | Trial periods | COMPLETED | 2026-10-24T15:47:48.031026+00:00 | 2026-10-24T15:49:51.791923+00:00 | REAL | backend/tests/test_subscription_lifecycle_proration.py::test_BIL_024_trial_periods | Trial period creation and active lifecycle transition |

### Area Reporting

| ID | Feature | State | Started | Completed | Verification | Tests | Notes |
|---|---|---|---|---|---|---|---|
| BIL-115 | Revenue metrics | COMPLETED | 2026-10-24T16:17:06.501950+00:00 | 2026-10-24T16:17:54.281086+00:00 | REAL | backend/tests/test_reporting_metrics.py::test_BIL_115_revenue_metrics | Real-time revenue metrics calculation across settled invoices with gross and net totals |
| BIL-117 | MRR metrics | COMPLETED | 2026-10-24T16:17:06.610689+00:00 | 2026-10-24T16:18:12.673336+00:00 | REAL | backend/tests/test_reporting_metrics.py::test_BIL_117_mrr_metrics | Monthly Recurring Revenue (MRR), ARR, and ARPU metrics calculation from active subscriptions |

### Area Security

| ID | Feature | State | Started | Completed | Verification | Tests | Notes |
|---|---|---|---|---|---|---|---|
| BIL-127 | API authentication | COMPLETED | 2026-10-24T16:18:34.879271+00:00 | 2026-10-24T16:19:40.940086+00:00 | REAL | backend/tests/test_security_and_audit.py::test_BIL_127_api_authentication | API key authentication with secure hashing, revocation, and validation |
| BIL-128 | RBAC | COMPLETED | 2026-10-24T16:18:34.959080+00:00 | 2026-10-24T16:19:53.095488+00:00 | REAL | backend/tests/test_security_and_audit.py::test_BIL_128_deny_by_default_rbac | Deny-by-default role-based access control with OWNER, FINANCE, VIEWER, and SERVICE roles |
| BIL-129 | Tenant isolation | COMPLETED | 2026-10-24T16:18:35.030866+00:00 | 2026-10-24T16:20:04.202507+00:00 | REAL | backend/tests/test_security_and_audit.py::test_BIL_129_tenant_isolation | Strict tenant isolation preventing cross-tenant resource access |
| BIL-136 | Audit logging | COMPLETED | 2026-10-24T16:20:18.521605+00:00 | 2026-10-24T16:20:29.985387+00:00 | REAL | backend/tests/test_security_and_audit.py::test_BIL_136_audit_logging_and_pii_redaction | Audit logging with actor, before/after states, and automatic PII/Tax-ID redaction |
