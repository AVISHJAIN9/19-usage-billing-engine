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
async def test_BIL_073_ledger_reconciliation(async_session):
    """
    BIL-073: Ledger reconciliation.
    Tests automated full-ledger reconciliation across multiple posted transactions,
    verifying total debits == total credits and variance == 0.
    """
    mgr = LedgerDatabaseManager(async_session)

    # Post multiple balanced transactions
    await mgr.record_transaction(
        transaction_id="tx_rec_1",
        tenant_id="tenant-audit",
        description="Sale 1",
        entries=[
            ("AR:c1", EntryType.DEBIT, 5000),
            ("REV:sales", EntryType.CREDIT, 5000)
        ]
    )
    await mgr.record_transaction(
        transaction_id="tx_rec_2",
        tenant_id="tenant-audit",
        description="Sale 2",
        entries=[
            ("AR:c2", EntryType.DEBIT, 12000),
            ("REV:sales", EntryType.CREDIT, 12000)
        ]
    )
    await mgr.record_transaction(
        transaction_id="tx_rec_3",
        tenant_id="tenant-audit",
        description="Payment 1",
        entries=[
            ("CASH:operating", EntryType.DEBIT, 5000),
            ("AR:c1", EntryType.CREDIT, 5000)
        ]
    )

    # Reconcile ledger
    report = await mgr.reconcile_ledger("tenant-audit")
    assert report["is_balanced"] is True
    assert report["total_transactions"] == 3
    assert report["total_debits_cents"] == 22000
    assert report["total_credits_cents"] == 22000
    assert report["variance_cents"] == 0
