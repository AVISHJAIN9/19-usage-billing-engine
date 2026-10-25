"""
Tests for Invoicing Engine:
- BIL-078: Draft invoices (lifecycle & mutability)
- BIL-082: Usage line items
- BIL-083: Subscription line items
- BIL-084: Discount line items
- BIL-086: Tax line items
- BIL-088: Currency handling
- Invariant: totals = subtotal - discounts - credits + tax (hand-computed)
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from db.database import Base
from invoicing.engine import (
    InvoiceManager,
    InvoiceStatus,
    LineItemType
)


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
async def test_BIL_078_draft_invoices_lifecycle_and_immutability(async_session: AsyncSession):
    manager = InvoiceManager(async_session)

    # 1. Create draft invoice
    inv = await manager.create_draft_invoice(
        tenant_id="tenant-1",
        customer_id="cust-1",
        currency="USD"
    )
    assert inv.status == InvoiceStatus.DRAFT
    assert inv.total_cents == 0

    # 2. Add line item to draft invoice
    await manager.add_subscription_line_item(inv.invoice_id, "starter-plan", 2900)
    updated = await manager.get_invoice(inv.invoice_id)
    assert updated.total_cents == 2900

    # 3. Finalize invoice
    finalized = await manager.finalize_invoice(inv.invoice_id)
    assert finalized.status == InvoiceStatus.FINALIZED
    assert finalized.finalized_at is not None

    # 4. Attempt to add line items to finalized invoice must fail
    with pytest.raises(ValueError, match="Cannot modify immutable invoice"):
        await manager.add_usage_line_item(inv.invoice_id, "api_calls", 100, 500)


@pytest.mark.asyncio
async def test_BIL_082_usage_line_item_generation(async_session: AsyncSession):
    manager = InvoiceManager(async_session)
    inv = await manager.create_draft_invoice("tenant-1", "cust-2", currency="EUR")

    # Add usage item
    item = await manager.add_usage_line_item(
        invoice_id=inv.invoice_id,
        event_type="tokens_generated",
        quantity=5000,
        amount_cents=7500,
        description="LLM token generation (5000 units)"
    )

    assert item.item_type == LineItemType.USAGE
    assert item.quantity == 5000
    assert item.amount_cents == 7500

    reloaded = await manager.get_invoice(inv.invoice_id)
    assert reloaded.subtotal_cents == 7500
    assert reloaded.total_cents == 7500


@pytest.mark.asyncio
async def test_BIL_083_subscription_line_items(async_session: AsyncSession):
    manager = InvoiceManager(async_session)
    inv = await manager.create_draft_invoice("tenant-1", "cust-3", currency="USD")

    # Add subscription item
    item = await manager.add_subscription_line_item(
        invoice_id=inv.invoice_id,
        plan_id="enterprise-annual",
        base_fee_cents=120000,
        description="Enterprise Annual License"
    )

    assert item.item_type == LineItemType.SUBSCRIPTION
    assert item.amount_cents == 120000

    reloaded = await manager.get_invoice(inv.invoice_id)
    assert reloaded.subtotal_cents == 120000
    assert reloaded.total_cents == 120000


@pytest.mark.asyncio
async def test_BIL_084_and_086_and_088_discounts_taxes_currencies_and_invariant(async_session: AsyncSession):
    """
    Hand-computed golden invoice test:
      Currency: GBP (BIL-088)
      Subscription: Base plan = 10,000 cents ($100.00)
      Usage: API requests = 5,000 cents ($50.00)
      Subtotal = 10,000 + 5,000 = 15,000 cents ($150.00)

      Discount (BIL-084): 2,000 cents ($20.00 promo code)
      Taxable amount = 15,000 - 2,000 = 13,000 cents ($130.00)

      Tax (BIL-086): 8.25% (825 basis points) on 13,000 cents
        13,000 * 0.0825 = 1,072.5 -> rounded to 1,073 cents

      Total = subtotal - discounts - credits + tax
            = 15,000 - 2,000 - 0 + 1,073
            = 14,073 cents ($140.73)
    """
    manager = InvoiceManager(async_session)

    # BIL-088 Currency validation: invalid currency rejected
    with pytest.raises(ValueError, match="Unsupported ISO currency"):
        await manager.create_draft_invoice("tenant-1", "cust-4", currency="XYZ_FAKE")

    # Valid currency GBP
    inv = await manager.create_draft_invoice("tenant-1", "cust-4", currency="GBP")
    assert inv.currency == "GBP"

    # Add Subscription and Usage
    await manager.add_subscription_line_item(inv.invoice_id, "pro-plan", 10000)
    await manager.add_usage_line_item(inv.invoice_id, "api_calls", 1000, 5000)

    # Add Discount (BIL-084)
    await manager.add_discount_line_item(inv.invoice_id, 2000, description="Spring Promo")

    # Add Tax (BIL-086) - 8.25% (825 bps)
    await manager.add_tax_line_item(inv.invoice_id, tax_rate_bps=825, description="VAT")

    finalized = await manager.finalize_invoice(inv.invoice_id)

    # Verify exact hand-computed values
    assert finalized.subtotal_cents == 15000
    assert finalized.discount_cents == 2000
    assert finalized.credit_cents == 0
    assert finalized.tax_cents == 1073
    assert finalized.total_cents == 14073
    assert finalized.total_cents == (finalized.subtotal_cents - finalized.discount_cents - finalized.credit_cents + finalized.tax_cents)
