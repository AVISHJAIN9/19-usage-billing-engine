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
async def test_BIL_070_double_entry_accounting_hooks(async_session):
    """
    BIL-070: Double-entry accounting hooks.
    Tests automated ledger posting upon invoice issuance (AR debit, Revenue credit)
    and payment settlement (Cash debit, AR credit), ensuring zero net imbalance.
    """
    mgr = LedgerDatabaseManager(async_session)

    # 1. Invoice issuance hook ($150.00 = 15000 cents)
    tx_inv = await mgr.post_invoice_hook(
        tenant_id="tenant-fin",
        invoice_id="inv-1001",
        customer_id="cust-100",
        total_cents=15000
    )
    assert len(tx_inv.entries) == 2
    ar_balance_after_inv = await mgr.get_account_balance("tenant-fin", "AR:cust-100")
    assert ar_balance_after_inv["net_balance_cents"] == 15000

    # 2. Payment hook ($150.00 = 15000 cents)
    tx_pay = await mgr.post_payment_hook(
        tenant_id="tenant-fin",
        payment_id="pay-5001",
        customer_id="cust-100",
        amount_cents=15000
    )
    assert len(tx_pay.entries) == 2

    # After payment, AR net balance should be 0 (fully paid off)
    ar_balance_after_pay = await mgr.get_account_balance("tenant-fin", "AR:cust-100")
    assert ar_balance_after_pay["net_balance_cents"] == 0

    # Cash account should reflect 15000 cents
    cash_bal = await mgr.get_account_balance("tenant-fin", "CASH:operating")
    assert cash_bal["net_balance_cents"] == 15000
