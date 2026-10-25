# F3: Automated Invoicing & Gapless Numbering

## Overview & Architecture
The invoicing manager in `backend/src/invoicing/manager.py` coordinates period-end aggregation, immutable invoice generation, line-item tax calculations, and sequential numbering.

```mermaid
sequenceDiagram
    autonumber
    participant Scheduler as Billing Period Scheduler
    participant InvManager as InvoicingManager
    participant DB as PostgreSQL Database
    participant Ledger as Double-Entry Ledger

    Scheduler->>InvManager: Close Billing Period (tenant_id, period_id)
    InvManager->>DB: Aggregate Unbilled Usage Rollups
    InvManager->>DB: INSERT invoice (status='DRAFT', subtotal_cents, tax_cents)
    InvManager->>DB: Lock invoice_sequences row with FOR UPDATE
    DB-->>InvManager: Current Sequence Number
    InvManager->>DB: UPDATE invoice SET status='FINALIZED', invoice_number='INV-2026-0042'
    InvManager->>Ledger: record_transaction(Debit=Accounts Receivable, Credit=Revenue)
    Ledger-->>InvManager: Balanced Transaction Recorded
    InvManager-->>Scheduler: Finalized Immutable Invoice
```

## Say It Out Loud
> "I developed the invoicing engine in `invoicing/manager.py` to manage the complete lifecycle from draft usage aggregation to finalized customer bills. When a billing cycle closes, our system generates a draft invoice and appends itemized line items for metered usage, subscription base fees, discounts, and taxes.
> 
> When the invoice is finalized, the manager locks the invoice into an immutable state so no further edits can occur. It calculates total cents using the formula: subtotal minus discounts minus credits plus tax.
> 
> To satisfy strict accounting and legal compliance, it queries an invoice sequences table with row-level locking to assign a gapless sequential number formatted as INV-year-number, guaranteeing no numbers are skipped even under concurrent finalization requests.
> 
> Simultaneously, it triggers a double-entry ledger posting to debit Accounts Receivable and credit Revenue.
> 
> I chose this multi-stage lifecycle (Draft to Finalized to Paid or Void) because enterprise finance teams require the ability to review and adjust draft line items before locking legal fiscal records.
> 
> If someone attempts to modify a finalized invoice, the method raises a 400 Bad Request error.
> 
> A limitation is that invoice PDF rendering currently relies on the browser's print engine, which I plan to supplement with a server-side PDF generator."
