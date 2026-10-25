# F4: Append-Only Double-Entry Ledger & Credit Wallet

## Overview & Architecture
The financial ledger in `backend/src/models/ledger.py` enforces double-entry bookkeeping rules for all monetary transactions, including prepaid customer credit balances.

```mermaid
flowchart LR
    InvoiceFinal[Finalize Invoice: $100] --> PostTx[Ledger.record_transaction()]
    subgraph Balanced Double-Entry Transaction
        PostTx --> DebitAR[Debit: Accounts Receivable (10,000 cents)]
        PostTx --> CreditRev[Credit: Revenue (10,000 cents)]
    end
    DebitAR --> VerifySum{Sum(Debits) == Sum(Credits)?}
    CreditRev --> VerifySum
    VerifySum -->|Equal| CommitPost[Commit Ledger Entry to DB]
    VerifySum -->|Not Equal| AbortPost[Raise ValueError: Unbalanced Transaction]
```

## Say It Out Loud
> "I engineered the double-entry accounting ledger in `models/ledger.py` to provide complete financial auditability and eliminate silent balance drift. Every monetary event in the system—whether it is finalizing an invoice, collecting a credit card payment, or granting a promotional credit—must write a balanced double-entry transaction.
> 
> My `record_transaction` method enforces two non-negotiable rules: first, every transaction must contain at least two entries, and second, the sum of all debits must strictly equal the sum of all credits in integer cents. If an invoice for $100 is finalized, it writes a debit of 10,000 cents to Accounts Receivable and a credit of 10,000 cents to Revenue.
> 
> I chose double-entry bookkeeping over a simple mutable balance column because single-entry ledgers make it impossible to audit where funds originated or detect software corruption after the fact.
> 
> If any component attempts to post an unbalanced transaction, my code raises a ValueError and the database transaction is aborted immediately.
> 
> One limitation is that computing account balances requires summing historical entries, which I would optimize at higher scale by introducing daily materialized balance checkpoints."
