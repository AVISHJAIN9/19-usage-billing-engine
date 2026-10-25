import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base, get_db
from api.app import app

@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()

@pytest.mark.asyncio
async def test_BIL_108_invoice_api(client):
    """
    BIL-108: Invoice API.
    Tests POST /v1/invoices, adding line items, finalization, and retrieving invoice details.
    """
    # 1. Create draft invoice
    create_payload = {
        "invoice_id": "inv-rest-001",
        "tenant_id": "tenant-saas",
        "customer_id": "cust-api-test",
        "due_days": 15
    }
    create_resp = await client.post("/v1/invoices", json=create_payload)
    assert create_resp.status_code == 200
    inv = create_resp.json()
    assert inv["id"] == "inv-rest-001"
    assert inv["status"] == "DRAFT"

    # 2. Add line item
    item_payload = {
        "description": "Storage Terabytes",
        "quantity": 5,
        "unit_price_cents": 1200,
        "event_type": "storage.tb"
    }
    item_resp = await client.post("/v1/invoices/inv-rest-001/items", json=item_payload)
    assert item_resp.status_code == 200
    assert item_resp.json()["amount_cents"] == 6000

    # 3. Finalize invoice
    fin_resp = await client.post("/v1/invoices/inv-rest-001/finalize")
    assert fin_resp.status_code == 200
    fin_inv = fin_resp.json()
    assert fin_inv["status"] == "FINALIZED"
    assert fin_inv["invoice_number"] is not None
    assert fin_inv["total_cents"] == 6000

    # 4. Get invoice details
    get_resp = await client.get("/v1/invoices/inv-rest-001")
    assert get_resp.status_code == 200
    det = get_resp.json()
    assert det["id"] == "inv-rest-001"
    assert len(det["line_items"]) == 1
    assert det["line_items"][0]["description"] == "Storage Terabytes"
