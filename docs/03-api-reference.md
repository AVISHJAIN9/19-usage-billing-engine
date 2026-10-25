# Complete API Reference

All requests accept and return `application/json`. Timestamps follow ISO-8601 UTC format. Financial values represent exact integer cents ($10.50 = 1050 cents).

---

## 1. Usage Metering & Ingestion

### `POST /v1/usage/events`
Ingests a single metered consumption event with deduplication.

- **Auth Required**: `Bearer <API_KEY>` (Role: `SERVICE` or `OWNER`)
- **Headers**: `Content-Type: application/json`
- **Request Body**:
```json
{
  "tenant_id": "tenant-saas",
  "customer_id": "cust-enterprise-42",
  "event_type": "api_requests",
  "quantity": 500,
  "idempotency_key": "idemp_evt_99120",
  "timestamp": "2026-10-25T10:00:00Z",
  "project_id": "proj-analytics-prod",
  "unit": "COUNT",
  "dimensions": {
    "region": "us-east-1",
    "endpoint": "/v1/inference"
  }
}
```
- **Validation Rules**:
  - `quantity`: Must be $\ge 0$.
  - `idempotency_key`: Non-empty alphanumeric string.
  - `timestamp`: Must be within -90 days and +1 hour from current server time.
- **Success Response (`200 OK`)**:
```json
{
  "status": "ACCEPTED",
  "event_id": "evt-77bfa2100",
  "tenant_id": "tenant-saas",
  "idempotency_key": "idemp_evt_99120",
  "error": null
}
```
- **Duplicate Response (`200 OK`)**:
```json
{
  "status": "DUPLICATE",
  "event_id": "evt-77bfa2100",
  "tenant_id": "tenant-saas",
  "idempotency_key": "idemp_evt_99120",
  "error": null
}
```
- **Error Response (`422 Unprocessable Entity`)**:
```json
{
  "detail": "Event rejected: TIMESTAMP_TOO_OLD: Timestamp is older than allowed window of 90 days"
}
```

---

### `POST /v1/usage/events/batch`
Ingests an array of up to 1,000 usage events within a single database transaction.

- **Auth Required**: `Bearer <API_KEY>` (Role: `SERVICE` or `OWNER`)
- **Request Body**: Array of `IngestEventPayload` objects.
- **Success Response (`200 OK`)**: Array of `IngestionResponse` objects.

---

### `GET /v1/usage/query`
Calculates ground-truth aggregated usage quantity for a customer over a time window.

- **Auth Required**: `Bearer <API_KEY>` (Role: `VIEWER`, `FINANCE`, `OWNER`)
- **Query Parameters**:
  - `tenant_id` (string, required): Organization identifier.
  - `customer_id` (string, required): Customer identifier.
  - `event_type` (string, required): Metric name (e.g. `api_requests`).
  - `start_date` (string, required): ISO-8601 start date.
  - `end_date` (string, required): ISO-8601 end date.
- **Success Response (`200 OK`)**:
```json
{
  "tenant_id": "tenant-saas",
  "customer_id": "cust-enterprise-42",
  "event_type": "api_requests",
  "start_date": "2026-10-01T00:00:00Z",
  "end_date": "2026-10-31T23:59:59Z",
  "total_quantity": 482500
}
```

---

## 2. Invoicing & Billing Lifecycle

### `POST /v1/invoices`
Initializes a new draft invoice shell for an account.

- **Request Body**:
```json
{
  "invoice_id": "inv_oct_2026_01",
  "tenant_id": "tenant-saas",
  "customer_id": "cust-enterprise-42",
  "period_id": "period_2026_10",
  "due_days": 30
}
```
- **Success Response (`200 OK`)**:
```json
{
  "id": "inv_oct_2026_01",
  "tenant_id": "tenant-saas",
  "customer_id": "cust-enterprise-42",
  "invoice_number": null,
  "status": "DRAFT",
  "subtotal_cents": 0,
  "discount_cents": 0,
  "tax_cents": 0,
  "total_cents": 0,
  "due_date": "2026-11-24T10:00:00Z",
  "line_items": []
}
```

---

### `POST /v1/invoices/{invoice_id}/items`
Appends an itemized charge to an existing draft invoice.

- **Request Body**:
```json
{
  "description": "API Gateway Metered Consumption (October)",
  "quantity": 10000,
  "unit_price_cents": 2,
  "event_type": "api_requests"
}
```
- **Success Response (`200 OK`)**:
```json
{
  "id": "item_88192a",
  "invoice_id": "inv_oct_2026_01",
  "item_type": "USAGE",
  "description": "API Gateway Metered Consumption (October)",
  "quantity": 10000,
  "unit_price_cents": 2,
  "amount_cents": 20000
}
```

---

### `POST /v1/invoices/{invoice_id}/finalize`
Locks invoice line items, calculates fiscal totals, assigns a gapless sequential number, and posts a double-entry ledger transaction.

- **Success Response (`200 OK`)**:
```json
{
  "id": "inv_oct_2026_01",
  "tenant_id": "tenant-saas",
  "customer_id": "cust-enterprise-42",
  "invoice_number": "INV-2026-0042",
  "status": "FINALIZED",
  "subtotal_cents": 20000,
  "discount_cents": 0,
  "tax_cents": 1600,
  "total_cents": 21600,
  "finalized_at": "2026-10-25T11:00:00Z",
  "line_items": [
    {
      "description": "API Gateway Metered Consumption (October)",
      "amount_cents": 20000
    }
  ]
}
```

---

## 3. Rating & Pricing Catalog

### `POST /v1/rating/calculate`
Evaluates pricing catalog rules against a given quantity in real time.

- **Request Body**:
```json
{
  "entry": {
    "id": "pb_graduated_api",
    "tenant_id": "tenant-saas",
    "plan_id": "plan_pro",
    "event_type": "api_requests",
    "pricing_type": "GRADUATED_BRACKET",
    "flat_fee_cents": 500,
    "free_units": 1000,
    "tiers": [
      { "up_to": 10000, "unit_price_cents": 2 },
      { "up_to": null, "unit_price_cents": 1 }
    ]
  },
  "quantity": 15000
}
```
- **Success Response (`200 OK`)**:
```json
{
  "event_type": "api_requests",
  "pricing_type": "GRADUATED_BRACKET",
  "total_quantity": 15000,
  "free_units_applied": 1000,
  "billable_quantity": 14000,
  "subtotal_cents": 2200,
  "flat_fee_cents": 500,
  "total_cents": 2700,
  "min_charge_applied": false,
  "max_charge_applied": false,
  "explanation": "Graduated: 10000 @ 2c, 4000 @ 1c + 500 flat"
}
```

---

## 4. Payments, Collections & Subscriptions

### `POST /v1/payments/authorize`
Places an authorization hold on customer funds.

- **Request Body**:
```json
{
  "payment_id": "pay_9921",
  "tenant_id": "tenant-saas",
  "customer_id": "cust-enterprise-42",
  "invoice_id": "inv_oct_2026_01",
  "amount_cents": 21600,
  "idempotency_key": "pay_idemp_772"
}
```

### `POST /v1/payments/{payment_id}/capture`
Settles the authorized payment and updates invoice status to `PAID`.

---

### `POST /v1/subscriptions/{subscription_id}/upgrade`
Executes an immediate mid-cycle subscription plan upgrade with exact second-level proration.

- **Request Body**:
```json
{
  "new_plan_id": "plan_enterprise_v2",
  "new_plan_rate_cents": 20000,
  "old_plan_rate_cents": 5000,
  "as_of": "2026-10-15T12:00:00Z"
}
```
- **Success Response (`200 OK`)**:
```json
{
  "subscription": {
    "subscription_id": "sub_4410",
    "plan_id": "plan_enterprise_v2",
    "status": "ACTIVE"
  },
  "proration": {
    "old_plan_price_cents": 5000,
    "new_plan_price_cents": 20000,
    "fraction_remaining": 0.516129,
    "unused_credit_cents": 2581,
    "new_charge_cents": 10323,
    "net_proration_cents": 7742
  }
}
```
