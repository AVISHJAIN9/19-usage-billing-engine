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
async def test_BIL_077_invoice_generation(async_session):
    """
    BIL-077: Invoice generation.
    Tests draft invoice creation for customer and billing period with default terms.
    """
    mgr = InvoiceManager(async_session)

    inv = await mgr.create_draft_invoice(
        invoice_id="inv-draft-001",
        tenant_id="tenant-saas",
        customer_id="cust-enterprise",
        period_id="period-october",
        due_days=30
    )

    assert inv.id == "inv-draft-001"
    assert inv.tenant_id == "tenant-saas"
    assert inv.customer_id == "cust-enterprise"
    assert inv.status == InvoiceStatus.DRAFT
    assert inv.subtotal_cents == 0
    assert inv.total_cents == 0
    assert inv.invoice_number is None
