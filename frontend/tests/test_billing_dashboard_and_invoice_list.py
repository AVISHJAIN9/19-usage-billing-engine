"""
Tests for Billing Dashboard & Invoice List (BIL-139, BIL-145).
"""

import os
import pytest
import pytest_asyncio
import httpx
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from db.database import Base, get_db
from api.app import app
from invoicing.manager import InvoiceManager, InvoiceRecord, InvoiceStatus
from models.accounts import SubscriptionRecordV2, SubscriptionStatus


def test_BIL_139_and_145_frontend_assets():
    """
    Asset verification for Billing Dashboard and Invoice List.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_path = os.path.join(base_dir, "src", "index.html")
    js_path = os.path.join(base_dir, "src", "app.js")

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # BIL-139 Dashboard elements
    assert 'id="section-dashboard"' in html
    assert 'id="kpi-gross-revenue"' in html
    assert 'id="kpi-mrr"' in html
    assert 'id="kpi-active-subs"' in html
    assert 'id="kpi-unpaid-invoices"' in html

    # BIL-145 Invoice List elements
    assert 'id="section-invoice-list"' in html
    assert 'id="invoice-list-table"' in html
    assert 'id="invoice-list-tbody"' in html
    assert 'id="filter-status"' in html

    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "fetchDashboard" in js
    assert "fetchInvoiceList" in js


@pytest_asyncio.fixture
async def test_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        # Create invoices: 1 PAID, 1 FINALIZED (unpaid), 1 DRAFT
        inv_paid = InvoiceRecord(
            id="inv-t1-paid",
            tenant_id="tenant-demo",
            customer_id="cust-1",
            status=InvoiceStatus.PAID.value,
            subtotal_cents=15000,
            discount_cents=1000,
            tax_cents=500,
            total_cents=14500,
            due_date=now
        )
        inv_unpaid = InvoiceRecord(
            id="inv-t1-unpaid",
            tenant_id="tenant-demo",
            customer_id="cust-2",
            status=InvoiceStatus.FINALIZED.value,
            subtotal_cents=8000,
            discount_cents=0,
            tax_cents=0,
            total_cents=8000,
            due_date=now
        )
        inv_draft = InvoiceRecord(
            id="inv-t1-draft",
            tenant_id="tenant-demo",
            customer_id="cust-3",
            status=InvoiceStatus.DRAFT.value,
            subtotal_cents=5000,
            discount_cents=0,
            tax_cents=0,
            total_cents=5000,
            due_date=now
        )
        session.add_all([inv_paid, inv_unpaid, inv_draft])

        # Active subscriptions for MRR
        sub = SubscriptionRecordV2(
            subscription_id="sub-demo-1",
            tenant_id="tenant-demo",
            customer_id="cust-1",
            plan_id="pro",
            status=SubscriptionStatus.ACTIVE.value,
            current_period_start=now,
            current_period_end=now
        )
        session.add(sub)
        await session.commit()

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_BIL_139_dashboard_api(test_client):
    res = await test_client.get("/v1/dashboard/summary?tenant_id=tenant-demo")
    assert res.status_code == 200
    data = res.json()
    assert data["tenant_id"] == "tenant-demo"
    assert data["net_revenue_cents"] == 14500
    assert data["active_subscriptions"] == 1
    assert data["unpaid_invoices_count"] == 1
    assert data["unpaid_amount_cents"] == 8000


@pytest.mark.asyncio
async def test_BIL_145_invoice_list_api_and_filtering(test_client):
    # 1. Fetch all invoices
    res = await test_client.get("/v1/invoices?tenant_id=tenant-demo")
    assert res.status_code == 200
    invoices = res.json()
    assert len(invoices) == 3

    # 2. Filter by status: PAID
    res_paid = await test_client.get("/v1/invoices?tenant_id=tenant-demo&status=PAID")
    assert res_paid.status_code == 200
    paid_invoices = res_paid.json()
    assert len(paid_invoices) == 1
    assert paid_invoices[0]["id"] == "inv-t1-paid"

    # 3. Filter by status: FINALIZED
    res_final = await test_client.get("/v1/invoices?tenant_id=tenant-demo&status=FINALIZED")
    assert res_final.status_code == 200
    final_invoices = res_final.json()
    assert len(final_invoices) == 1
    assert final_invoices[0]["id"] == "inv-t1-unpaid"
