import os
import pytest
import pytest_asyncio
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base, get_db
from api.app import app
from invoicing.manager import InvoiceManager

def test_BIL_146_console_assets_integrity():
    """
    BIL-146: Invoice detail console asset integrity.
    Verifies that the HTML, CSS, and JavaScript files exist and contain required
    interactive invoice detail components, line items table, and totals cards.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_path = os.path.join(base_dir, "src", "index.html")
    css_path = os.path.join(base_dir, "src", "index.css")
    js_path = os.path.join(base_dir, "src", "app.js")

    assert os.path.isfile(html_path), "index.html missing"
    assert os.path.isfile(css_path), "index.css missing"
    assert os.path.isfile(js_path), "app.js missing"

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Verify key invoice detail UI elements
    assert "Invoice Detail Console" in html
    assert 'id="inv-number"' in html
    assert 'id="inv-status-badge"' in html
    assert 'id="line-items-table"' in html
    assert 'id="line-items-tbody"' in html
    assert 'id="val-subtotal"' in html
    assert 'id="val-total"' in html
    assert 'id="btn-finalize"' in html
    assert 'id="btn-add-item"' in html
    assert 'id="ledger-preview"' in html or 'class="ledger-preview' in html

@pytest_asyncio.fixture
async def test_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_maker() as session:
        mgr = InvoiceManager(session)
        inv = await mgr.create_draft_invoice(
            invoice_id="inv-demo-100",
            tenant_id="tenant-saas",
            customer_id="cust-enterprise-42"
        )
        await mgr.add_line_item(
            invoice_id="inv-demo-100",
            description="Base Platform Subscription",
            quantity=1,
            unit_price_cents=9900
        )

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
async def test_BIL_146_console_api_integration(test_client):
    """
    BIL-146: Verify invoice detail console backend API contract.
    Ensures GET /v1/invoices/{invoice_id} returns the full invoice data structure
    ready for frontend rendering.
    """
    res = await test_client.get("/v1/invoices/inv-demo-100")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "inv-demo-100"
    assert data["customer_id"] == "cust-enterprise-42"
    assert data["status"] == "DRAFT"
    assert data["subtotal_cents"] == 9900
    assert len(data["line_items"]) == 1
    assert data["line_items"][0]["description"] == "Base Platform Subscription"
