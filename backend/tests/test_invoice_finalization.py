import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from invoicing.manager import InvoiceManager, InvoiceStatus

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
async def test_BIL_079_invoice_finalization(async_session):
    """
    BIL-079: Invoice finalization.
    Tests locking invoice from DRAFT -> FINALIZED, assigning immutable invoice number,
    and preventing modifications once finalized.
    """
    mgr = InvoiceManager(async_session)

    # 1. Draft invoice
    inv = await mgr.create_draft_invoice(
        invoice_id="inv-fin-001",
        tenant_id="tenant-acme",
        customer_id="cust-1"
    )
    await mgr.add_line_item(
        invoice_id="inv-fin-001",
        description="Compute Usage",
        quantity=10,
        unit_price_cents=500
    )

    # 2. Finalize
    finalized = await mgr.finalize_invoice("inv-fin-001")
    assert finalized.status == InvoiceStatus.FINALIZED
    assert finalized.invoice_number is not None
    assert finalized.finalized_at is not None

    # 3. Reject further line items after finalization
    with pytest.raises(ValueError, match="Cannot add line items to a non-draft invoice"):
        await mgr.add_line_item(
            invoice_id="inv-fin-001",
            description="Extra item",
            quantity=1,
            unit_price_cents=100
        )
