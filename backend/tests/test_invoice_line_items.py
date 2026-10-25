import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from invoicing.manager import InvoiceManager

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
async def test_BIL_081_invoice_line_items(async_session):
    """
    BIL-081: Invoice line items.
    Tests adding detailed line items with quantity, unit prices, and subtotal computation.
    """
    mgr = InvoiceManager(async_session)

    inv = await mgr.create_draft_invoice(
        invoice_id="inv-items-001",
        tenant_id="tenant-items",
        customer_id="cust-items"
    )

    li1 = await mgr.add_line_item(
        invoice_id="inv-items-001",
        description="Base Plan Fee",
        quantity=1,
        unit_price_cents=5000,
        event_type="subscription.base"
    )
    assert li1.amount_cents == 5000

    li2 = await mgr.add_line_item(
        invoice_id="inv-items-001",
        description="API Calls Overage",
        quantity=200,
        unit_price_cents=10,
        event_type="api.calls"
    )
    assert li2.amount_cents == 2000

    fetched = await mgr.get_invoice("inv-items-001")
    assert len(fetched.line_items) == 2
    assert fetched.subtotal_cents == 7000
