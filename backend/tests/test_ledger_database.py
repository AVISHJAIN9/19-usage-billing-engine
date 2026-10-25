import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from models.ledger import LedgerDatabaseManager, EntryType

@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        yield session
    await engine.dispose()

@pytest.mark.asyncio
async def test_BIL_006_ledger_database(async_session):
    """
    BIL-006: Ledger database.
    Enforces double-entry financial accounting:
    - Sigma(debits) == Sigma(credits)
    - Minimum 2 entries per transaction
    - Rejects unbalanced transactions
    - Accurate balance calculation
    """
    mgr = LedgerDatabaseManager(async_session)

    # 1. Balanced invoice recognition:
    # Debit: Accounts Receivable $150.00 (15000 cents)
    # Credit: Usage Revenue $150.00 (15000 cents)
    tx = await mgr.record_transaction(
        transaction_id="tx-inv-1001",
        tenant_id="tenant-fin",
        description="Invoice #1001 issued",
        entries=[
            ("accounts_receivable", EntryType.DEBIT, 15000),
            ("revenue_usage", EntryType.CREDIT, 15000)
        ],
        reference_id="inv-1001"
    )
    assert tx.transaction_id == "tx-inv-1001"
    assert len(tx.entries) == 2

    # Check account balances
    ar_bal = await mgr.get_account_balance("tenant-fin", "accounts_receivable")
    assert ar_bal["total_debits_cents"] == 15000
    assert ar_bal["net_balance_cents"] == 15000

    rev_bal = await mgr.get_account_balance("tenant-fin", "revenue_usage")
    assert rev_bal["total_credits_cents"] == 15000
    assert rev_bal["net_balance_cents"] == -15000

    # 2. Balanced multi-leg payment collection:
    # Debit: Cash $150.00 (15000 cents)
    # Credit: Accounts Receivable $150.00 (15000 cents)
    tx_pay = await mgr.record_transaction(
        transaction_id="tx-pay-2001",
        tenant_id="tenant-fin",
        description="Payment received for invoice #1001",
        entries=[
            ("cash", EntryType.DEBIT, 15000),
            ("accounts_receivable", EntryType.CREDIT, 15000)
        ]
    )
    assert tx_pay.transaction_id == "tx-pay-2001"

    # AR balance is now settled back to 0!
    ar_bal_settled = await mgr.get_account_balance("tenant-fin", "accounts_receivable")
    assert ar_bal_settled["net_balance_cents"] == 0

    # 3. Unbalanced transaction -> strictly rejected!
    with pytest.raises(ValueError) as exc:
        await mgr.record_transaction(
            transaction_id="tx-unbalanced",
            tenant_id="tenant-fin",
            description="Illegal unbalanced entry",
            entries=[
                ("accounts_receivable", EntryType.DEBIT, 10000),
                ("revenue_usage", EntryType.CREDIT, 5000)
            ]
        )
    assert "Double-entry invariant violated" in str(exc.value)

    # 4. Less than 2 entries -> rejected!
    with pytest.raises(ValueError):
        await mgr.record_transaction(
            transaction_id="tx-single",
            tenant_id="tenant-fin",
            description="Single entry",
            entries=[
                ("cash", EntryType.DEBIT, 5000)
            ]
        )
