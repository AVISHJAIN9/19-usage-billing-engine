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
async def test_BIL_071_ledger_transactions(async_session):
    """
    BIL-071: Ledger transactions.
    Tests recording multi-legged atomic financial transactions and querying them.
    """
    mgr = LedgerDatabaseManager(async_session)

    # 3-legged transaction: Customer pays 10,000 cents with 9,700 net cash and 300 processing fee
    tx = await mgr.record_transaction(
        transaction_id="tx_multi_001",
        tenant_id="tenant-fin",
        description="Customer subscription payment with gateway fee",
        entries=[
            ("CASH:bank", EntryType.DEBIT, 9700),
            ("EXPENSE:gateway_fee", EntryType.DEBIT, 300),
            ("AR:cust-abc", EntryType.CREDIT, 10000)
        ]
    )

    assert tx.transaction_id == "tx_multi_001"
    assert len(tx.entries) == 3

    # Query transaction
    fetched = await mgr.get_transaction("tx_multi_001")
    assert fetched is not None
    assert fetched.description == "Customer subscription payment with gateway fee"
    assert len(fetched.entries) == 3
