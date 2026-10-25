# AI Architecture & Predictive Spend Analytics

`19-usage-billing-engine` incorporates statistical machine learning and predictive forecasting to help customers project end-of-month invoice costs and detect runaway consumption anomalies.

---

## Spend Anomaly Detection & Forecasting Pipeline

```mermaid
flowchart LR
    Telemetry[Raw Meter Stream] --> Aggregator[Tumbling Hourly Rollups]
    Aggregator --> Detector[Statistical Anomaly Detector: Z-Score & Holt-Winters]
    Detector -->|Usage Spike Detected| Alert[Trigger Alert & Webhook]
    Detector -->|Normal Usage| Forecaster[Run-Rate Spend Forecaster]
    Forecaster --> Dashboard[Display Accrued & Projected Invoice on Console]
```

---

## 1. Forecasting Algorithms Used
1. **Linear Run-Rate Extrapolation**:
   $$\text{Projected Total} = \frac{\text{Current Month Usage}}{\text{Elapsed Days}} \times \text{Total Month Days}$$
2. **Holt-Winters Triple Exponential Smoothing**:
   Accounts for weekly seasonality (lower weekend consumption) and trend acceleration when computing projected billable units.

---

## 2. Generative AI Dispute Assistant Architecture (LLM Copilot)
To reduce manual customer support costs for billing inquiries, an LLM copilot architecture was designed for invoice explanations:

```mermaid
sequenceDiagram
    autonumber
    actor Tenant as Customer
    participant UI as Billing Console
    participant AI as Dispute Service
    participant RAG as Retrieval Augmented Generation (Ledger & Events)
    participant LLM as OpenAI GPT-4o / Claude 3.5

    Tenant->>UI: "Why is my invoice $500 higher this month?"
    UI->>AI: Query Dispute API
    AI->>RAG: Retrieve invoice line items, prior month delta, and top 3 spikes
    RAG-->>AI: Grounded Financial Context
    AI->>LLM: System Prompt + Financial Context (PII Redacted)
    LLM-->>AI: Clear natural-language breakdown
    AI-->>UI: "Your usage increased by 42,000 API calls on Oct 14 during data migration."
```

- **Prompt Guardrails**: System prompts strictly forbid the model from guessing or negotiating invoice amounts. The model can only explain pre-computed mathematical deltas.
- **Data Privacy**: All customer PII, Tax IDs, and card details are scrubbed via `security/audit.py:redact_sensitive_info()` before payloads are transmitted to external LLM providers.
