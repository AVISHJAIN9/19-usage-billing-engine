"""
Tests for Reporting & Analytics:
- BIL-115: Revenue metrics
- BIL-117: MRR metrics
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from db.database import Base
from invoicing.manager import InvoiceRecord, InvoiceStatus
from models.accounts import SubscriptionRecordV2, SubscriptionStatus
from reporting.metrics import FinancialMetricsReporter


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
async def test_BIL_115_revenue_metrics(async_session: AsyncSession):
    reporter = FinancialMetricsReporter(async_session)

    # Invoices: 2 PAID, 1 DRAFT (DRAFT must not be counted in settled revenue)
    now = datetime.now(timezone.utc)
    inv1 = InvoiceRecord(
        id="inv-rev-1",
        tenant_id="tenant-rev",
        customer_id="cust-1",
        status=InvoiceStatus.PAID.value,
        subtotal_cents=10000,
        discount_cents=1000,
        tax_cents=800,
        total_cents=9800,
        due_date=now
    )
    inv2 = InvoiceRecord(
        id="inv-rev-2",
        tenant_id="tenant-rev",
        customer_id="cust-2",
        status=InvoiceStatus.PAID.value,
        subtotal_cents=20000,
        discount_cents=3000,
        tax_cents=1500,
        total_cents=18500,
        due_date=now
    )
    inv_draft = InvoiceRecord(
        id="inv-rev-draft",
        tenant_id="tenant-rev",
        customer_id="cust-3",
        status=InvoiceStatus.DRAFT.value,
        subtotal_cents=50000,
        discount_cents=0,
        tax_cents=0,
        total_cents=50000,
        due_date=now
    )
    async_session.add_all([inv1, inv2, inv_draft])
    await async_session.commit()

    metrics = await reporter.compute_revenue_metrics("tenant-rev")
    assert metrics.paid_invoice_count == 2
    assert metrics.total_discounts_cents == 4000
    assert metrics.total_tax_cents == 2300
    assert metrics.net_revenue_cents == (9800 + 18500) == 28300
    assert metrics.gross_revenue_cents == (30000 + 2300) == 32300


@pytest.mark.asyncio
async def test_BIL_117_mrr_metrics(async_session: AsyncSession):
    reporter = FinancialMetricsReporter(async_session)

    now = datetime.now(timezone.utc)
    # 3 active subscriptions, 1 canceled
    s1 = SubscriptionRecordV2(
        subscription_id="sub-mrr-1",
        tenant_id="tenant-mrr",
        customer_id="cust-1",
        plan_id="starter",
        status=SubscriptionStatus.ACTIVE.value,
        current_period_start=now,
        current_period_end=now
    )
    s2 = SubscriptionRecordV2(
        subscription_id="sub-mrr-2",
        tenant_id="tenant-mrr",
        customer_id="cust-2",
        plan_id="pro",
        status=SubscriptionStatus.ACTIVE.value,
        current_period_start=now,
        current_period_end=now
    )
    s3 = SubscriptionRecordV2(
        subscription_id="sub-mrr-3",
        tenant_id="tenant-mrr",
        customer_id="cust-3",
        plan_id="enterprise",
        status=SubscriptionStatus.ACTIVE.value,
        current_period_start=now,
        current_period_end=now
    )
    s4_canceled = SubscriptionRecordV2(
        subscription_id="sub-mrr-4",
        tenant_id="tenant-mrr",
        customer_id="cust-4",
        plan_id="enterprise",
        status=SubscriptionStatus.CANCELED.value,
        current_period_start=now,
        current_period_end=now
    )
    async_session.add_all([s1, s2, s3, s4_canceled])
    await async_session.commit()

    rates = {
        "starter": 2900,     # $29/mo
        "pro": 9900,         # $99/mo
        "enterprise": 29900  # $299/mo
    }
    mrr = await reporter.compute_mrr_metrics("tenant-mrr", plan_monthly_rates_cents=rates)
    assert mrr.active_subscriptions_count == 3
    expected_mrr = 2900 + 9900 + 29900  # 42700 cents ($427.00)
    assert mrr.total_mrr_cents == expected_mrr
    assert mrr.arr_cents == expected_mrr * 12
    assert mrr.arpu_cents == expected_mrr // 3
