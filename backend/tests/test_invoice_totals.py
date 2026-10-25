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
async def test_BIL_087_invoice_totals(async_session):
    """
    BIL-087: Invoice totals.
    Validates mathematical financial invariants:
      subtotal = sum(line_items)
      total = subtotal - discount + tax
    All calculated in integer cents.
    """
    mgr = InvoiceManager(async_session)

    inv = await mgr.create_draft_invoice(
        invoice_id="inv-totals-001",
        tenant_id="tenant-math",
        customer_id="cust-math"
    )

    # Line item 1: 3000 cents ($30.00)
    await mgr.add_line_item(
        invoice_id="inv-totals-001",
        description="Seat Licenses",
        quantity=3,
        unit_price_cents=1000
    )
    # Line item 2: 7000 cents ($70.00)
    await mgr.add_line_item(
        invoice_id="inv-totals-001",
        description="Premium Add-on",
        quantity=1,
        unit_price_cents=7000
    )

    # Subtotal is 3000 + 7000 = 10000 cents
    # Apply discount of 1500 cents ($15.00) and tax of 850 cents ($8.50)
    # Total = 10000 - 1500 + 850 = 9350 cents ($93.50)
    updated = await mgr.recalculate_totals(
        invoice_id="inv-totals-001",
        discount_cents=1500,
        tax_cents=850
    )

    assert updated.subtotal_cents == 10000
    assert updated.discount_cents == 1500
    assert updated.tax_cents == 850
    assert updated.total_cents == 9350
    # Invariant verification:
    assert updated.total_cents == updated.subtotal_cents - updated.discount_cents + updated.tax_cents
