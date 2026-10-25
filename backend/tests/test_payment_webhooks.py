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
async def test_BIL_095_payment_webhooks(async_session):
    """
    BIL-095: Payment webhooks.
    Tests handling payment_intent.succeeded webhook and updating invoice settlement.
    """
    inv_mgr = InvoiceManager(async_session)
    pay_mgr = PaymentManager(async_session)

    # Create draft and line item ($80.00 = 8000 cents)
    inv = await inv_mgr.create_draft_invoice(
        invoice_id="inv-wh-001",
        tenant_id="tenant-saas",
        customer_id="cust-webhook"
    )
    await inv_mgr.add_line_item(
        invoice_id="inv-wh-001",
        description="Database Hosting",
        quantity=2,
        unit_price_cents=4000
    )

    # Process inbound webhook
    webhook_payload = {
        "invoice_id": "inv-wh-001",
        "customer_id": "cust-webhook",
        "amount_cents": 8000,
        "payment_id": "pay_wh_888",
        "provider_tx_id": "pi_stripe_webhook_999"
    }

    result = await pay_mgr.handle_webhook(
        event_id="evt_wh_001",
        tenant_id="tenant-saas",
        event_type="payment_intent.succeeded",
        payload=webhook_payload
    )

    assert result.status == "PROCESSED"

    # Check invoice status is updated to PAID
    updated_inv = await inv_mgr.get_invoice("inv-wh-001")
    assert updated_inv.status == InvoiceStatus.PAID

    # Verify payment record
    pay_rec = await pay_mgr.get_payment("pay_wh_888")
    assert pay_rec is not None
    assert pay_rec.status == PaymentStatus.SUCCEEDED
    assert pay_rec.amount_cents == 8000
