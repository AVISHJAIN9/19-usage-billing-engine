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
async def test_BIL_074_balance_calculation(async_session):
    """
    BIL-074: Balance calculation.
    Tests dynamic aggregation of cumulative debits, credits, and net balance for individual accounts.
    """
    mgr = LedgerDatabaseManager(async_session)

    # 1. Post debits to AR account ($200)
    await mgr.record_transaction(
        transaction_id="tx_bal_1",
        tenant_id="tenant-saas",
        description="Invoice #1",
        entries=[
            ("AR:cust-calc", EntryType.DEBIT, 20000),
            ("REV:api", EntryType.CREDIT, 20000)
        ]
    )

    # 2. Post partial credit / payment ($75)
    await mgr.record_transaction(
        transaction_id="tx_bal_2",
        tenant_id="tenant-saas",
        description="Partial Payment",
        entries=[
            ("CASH:operating", EntryType.DEBIT, 7500),
            ("AR:cust-calc", EntryType.CREDIT, 7500)
        ]
    )

    # Balance check: 20000 debits - 7500 credits = 12500 net balance
    bal = await mgr.get_account_balance("tenant-saas", "AR:cust-calc")
    assert bal["total_debits_cents"] == 20000
    assert bal["total_credits_cents"] == 7500
    assert bal["net_balance_cents"] == 12500
