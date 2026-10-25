"""
Tests for Ledger & Financial Integrity:
- BIL-065: Immutable usage ledger (DB triggers revoke UPDATE/DELETE)
- BIL-066: Charge ledger (immutable line item charges & balancing double-entry transactions)
- BIL-072: Unique transaction IDs
- BIL-076: Adjustment journal (non-destructive financial corrections)
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.exc import DBAPIError

from db.database import Base
from models.ledger import (
    LedgerTransactionRecord,
    LedgerEntryRecord,
    UsageLedgerRecord,
    ChargeLedgerRecord,
    AdjustmentJournalRecord,
    LedgerDatabaseManager,
    ChargeLedgerManager,
    AdjustmentJournalManager,
    apply_immutability_triggers,
    EntryType
)


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        await apply_immutability_triggers(session)
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_BIL_065_immutable_usage_ledger_enforcement(async_session: AsyncSession):
    # Insert row into usage_ledger
    row = UsageLedgerRecord(
        ledger_id="ledg-001",
        tenant_id="tenant-1",
        customer_id="cust-1",
        event_type="api_calls",
        quantity=500,
        transaction_id="tx_001"
    )
    async_session.add(row)
    await async_session.commit()

    # Attempt to UPDATE must be rejected by the DB trigger
    with pytest.raises(DBAPIError, match="strictly immutable"):
        await async_session.execute(
            text("UPDATE usage_ledger SET quantity = 999 WHERE ledger_id = 'ledg-001'")
        )
        await async_session.commit()
    await async_session.rollback()

    # Attempt to DELETE must be rejected by the DB trigger
    with pytest.raises(DBAPIError, match="cannot be deleted"):
        await async_session.execute(
            text("DELETE FROM usage_ledger WHERE ledger_id = 'ledg-001'")
        )
        await async_session.commit()
    await async_session.rollback()


@pytest.mark.asyncio
async def test_BIL_066_charge_ledger_and_double_entry_balance(async_session: AsyncSession):
    manager = ChargeLedgerManager(async_session)

    charge, tx = await manager.record_charge(
        tenant_id="tenant-acme",
        customer_id="cust-10",
        event_type="model_tokens",
        amount_cents=12500,
        currency="USD"
    )

    assert charge.amount_cents == 12500
    assert charge.transaction_id == tx.transaction_id

    # Verify double-entry balance: sum(debits) == sum(credits)
    total_debits = sum(e.amount_cents for e in tx.entries if e.entry_type == "DEBIT")
    total_credits = sum(e.amount_cents for e in tx.entries if e.entry_type == "CREDIT")
    assert total_debits == total_credits == 12500

    # Charge ledger rows are also protected by triggers
    with pytest.raises(DBAPIError, match="strictly immutable"):
        await async_session.execute(
            text(f"UPDATE charge_ledger SET amount_cents = 0 WHERE charge_id = '{charge.charge_id}'")
        )
        await async_session.commit()
    await async_session.rollback()


@pytest.mark.asyncio
async def test_BIL_072_unique_transaction_ids(async_session: AsyncSession):
    ledger = LedgerDatabaseManager(async_session)

    # Record first transaction
    tx1 = await ledger.record_transaction(
        transaction_id="tx_unique_001",
        tenant_id="tenant-1",
        description="First tx",
        entries=[
            ("AR:cust", EntryType.DEBIT, 5000),
            ("REV:api", EntryType.CREDIT, 5000)
        ]
    )
    assert tx1.transaction_id == "tx_unique_001"

    # Recording duplicate transaction_id must fail unique primary key constraint
    with pytest.raises(DBAPIError):
        await ledger.record_transaction(
            transaction_id="tx_unique_001",
            tenant_id="tenant-1",
            description="Duplicate tx",
            entries=[
                ("AR:cust", EntryType.DEBIT, 2000),
                ("REV:api", EntryType.CREDIT, 2000)
            ]
        )
    await async_session.rollback()


@pytest.mark.asyncio
async def test_BIL_076_adjustment_journal_preserves_original_transactions(async_session: AsyncSession):
    charge_mgr = ChargeLedgerManager(async_session)
    adj_mgr = AdjustmentJournalManager(async_session)

    # 1. Post initial charge
    charge, orig_tx = await charge_mgr.record_charge(
        tenant_id="tenant-acme",
        customer_id="cust-20",
        event_type="bandwidth",
        amount_cents=8000
    )

    # 2. Customer dispute: issue a partial credit memo of 3000 cents
    adj_rec, adj_tx = await adj_mgr.post_adjustment(
        tenant_id="tenant-acme",
        customer_id="cust-20",
        original_transaction_id=orig_tx.transaction_id,
        amount_cents=3000,
        reason="Overbilled SLA downtime credit",
        actor="finance_admin@acme.com",
        adjustment_type="CREDIT_MEMO"
    )

    # Assert adjustment record links to original tx
    assert adj_rec.original_transaction_id == orig_tx.transaction_id
    assert adj_rec.amount_cents == 3000

    # Assert new balancing transaction satisfies Sigma debits == Sigma credits
    total_debits = sum(e.amount_cents for e in adj_tx.entries if e.entry_type == "DEBIT")
    total_credits = sum(e.amount_cents for e in adj_tx.entries if e.entry_type == "CREDIT")
    assert total_debits == total_credits == 3000

    # Assert original transaction is completely unchanged
    ledger = LedgerDatabaseManager(async_session)
    reloaded_orig = await ledger.get_transaction(orig_tx.transaction_id)
    assert reloaded_orig is not None
    assert sum(e.amount_cents for e in reloaded_orig.entries if e.entry_type == "DEBIT") == 8000
