import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from invoicing.manager import InvoiceManager, InvoiceStatus
from payments.manager import PaymentManager, PaymentStatus

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
async def test_BIL_090_payment_provider_integration(async_session):
    """
    BIL-090: Payment provider integration.
    Tests recording customer payment execution and settling invoice to PAID.
    """
    inv_mgr = InvoiceManager(async_session)
    pay_mgr = PaymentManager(async_session)

    # 1. Create and finalize invoice ($50.00 = 5000 cents)
    inv = await inv_mgr.create_draft_invoice(
        invoice_id="inv-pay-001",
        tenant_id="tenant-pay",
        customer_id="cust-pay"
    )
    await inv_mgr.add_line_item(
        invoice_id="inv-pay-001",
        description="Monthly Cloud Plan",
        quantity=1,
        unit_price_cents=5000
    )
    finalized = await inv_mgr.finalize_invoice("inv-pay-001")
    assert finalized.status == InvoiceStatus.FINALIZED

    # 2. Process payment of 5000 cents
    payment = await pay_mgr.create_and_settle_payment(
        payment_id="pay-rec-1",
        tenant_id="tenant-pay",
        customer_id="cust-pay",
        invoice_id="inv-pay-001",
        amount_cents=5000,
        provider_tx_id="ch_stripe_mock_12345"
    )

    assert payment.id == "pay-rec-1"
    assert payment.status == PaymentStatus.SUCCEEDED
    assert payment.provider_tx_id == "ch_stripe_mock_12345"

    # 3. Verify invoice is now PAID
    updated_inv = await inv_mgr.get_invoice("inv-pay-001")
    assert updated_inv.status == InvoiceStatus.PAID
