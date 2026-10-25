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
async def test_BIL_080_invoice_numbering(async_session):
    """
    BIL-080: Invoice numbering.
    Tests monotonic gapless invoice sequence generation per tenant and year.
    """
    mgr = InvoiceManager(async_session)

    # Tenant 1 sequences in 2026
    num1 = await mgr.get_next_invoice_number(tenant_id="tenant-1", year=2026)
    assert num1 == "INV-2026-0001"

    num2 = await mgr.get_next_invoice_number(tenant_id="tenant-1", year=2026)
    assert num2 == "INV-2026-0002"

    num3 = await mgr.get_next_invoice_number(tenant_id="tenant-1", year=2026)
    assert num3 == "INV-2026-0003"

    # Tenant 2 has independent sequence
    t2_num1 = await mgr.get_next_invoice_number(tenant_id="tenant-2", year=2026)
    assert t2_num1 == "INV-2026-0001"

    # Next year for Tenant 1 restarts from 1
    t1_2027 = await mgr.get_next_invoice_number(tenant_id="tenant-1", year=2027)
    assert t1_2027 == "INV-2027-0001"
