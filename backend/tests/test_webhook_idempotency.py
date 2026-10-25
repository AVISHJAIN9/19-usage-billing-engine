import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from invoicing.manager import InvoiceManager
from payments.manager import PaymentManager

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
async def test_BIL_096_webhook_idempotency(async_session):
    """
    BIL-096: Webhook idempotency.
    Tests deduplication of identical webhook delivery events, ensuring duplicates
    are marked DUPLICATE and rejected from re-execution.
    """
    inv_mgr = InvoiceManager(async_session)
    pay_mgr = PaymentManager(async_session)

    inv = await inv_mgr.create_draft_invoice(
        invoice_id="inv-idem-001",
        tenant_id="tenant-saas",
        customer_id="cust-idem"
    )
    await inv_mgr.add_line_item(
        invoice_id="inv-idem-001",
        description="Subscription",
        quantity=1,
        unit_price_cents=2500
    )

    payload = {
        "invoice_id": "inv-idem-001",
        "customer_id": "cust-idem",
        "amount_cents": 2500,
        "payment_id": "pay_idem_1",
        "provider_tx_id": "pi_idem_1"
    }

    # First delivery: PROCESSED
    res1 = await pay_mgr.handle_webhook(
        event_id="evt_idem_duplicate_test",
        tenant_id="tenant-saas",
        event_type="payment_intent.succeeded",
        payload=payload
    )
    assert res1.status == "PROCESSED"

    # Second delivery with SAME event_id: DUPLICATE
    res2 = await pay_mgr.handle_webhook(
        event_id="evt_idem_duplicate_test",
        tenant_id="tenant-saas",
        event_type="payment_intent.succeeded",
        payload=payload
    )
    assert res2.status == "DUPLICATE"
    assert "already processed" in res2.message
