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
async def test_BIL_075_debit_credit_entries(async_session):
    """
    BIL-075: Debit/credit entries.
    Validates entry constraints: strictly positive integer amounts and rejection of non-positive entries.
    """
    mgr = LedgerDatabaseManager(async_session)

    # 1. Reject negative amount
    with pytest.raises(ValueError, match="must be strictly positive"):
        await mgr.record_transaction(
            transaction_id="tx_err_1",
            tenant_id="tenant-x",
            description="Invalid negative amount",
            entries=[
                ("ACC1", EntryType.DEBIT, -100),
                ("ACC2", EntryType.CREDIT, -100)
            ]
        )

    # 2. Reject zero amount
    with pytest.raises(ValueError, match="must be strictly positive"):
        await mgr.record_transaction(
            transaction_id="tx_err_2",
            tenant_id="tenant-x",
            description="Invalid zero amount",
            entries=[
                ("ACC1", EntryType.DEBIT, 0),
                ("ACC2", EntryType.CREDIT, 0)
            ]
        )

    # 3. Reject unbalanced entries
    with pytest.raises(ValueError, match="Double-entry invariant violated"):
        await mgr.record_transaction(
            transaction_id="tx_err_3",
            tenant_id="tenant-x",
            description="Unbalanced transaction",
            entries=[
                ("ACC1", EntryType.DEBIT, 1000),
                ("ACC2", EntryType.CREDIT, 999)
            ]
        )
