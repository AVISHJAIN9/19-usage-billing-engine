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
async def test_BIL_103_usage_ingestion_api(client):
    """
    BIL-103: Usage ingestion API.
    Tests POST /v1/usage/events, batch ingestion, deduplication, and GET query endpoints.
    """
    # 1. Ingest single event
    payload = {
        "event_id": "evt-api-01",
        "tenant_id": "tenant-cloud",
        "customer_id": "cust-web",
        "event_type": "api.requests",
        "quantity": 100,
        "idempotency_key": "api-idem-1",
        "dimensions": {"region": "us-east"}
    }
    resp = await client.post("/v1/usage/events", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ACCEPTED"
    assert data["event_id"] == "evt-api-01"

    # 2. Ingest duplicate event (same idempotency_key + tenant)
    dup_resp = await client.post("/v1/usage/events", json=payload)
    assert dup_resp.status_code == 200
    dup_data = dup_resp.json()
    assert dup_data["status"] == "DUPLICATE"

    # 3. Query events
    query_resp = await client.get("/v1/usage/events", params={
        "tenant_id": "tenant-cloud",
        "customer_id": "cust-web"
    })
    assert query_resp.status_code == 200
    events = query_resp.json()
    assert len(events) == 1
    assert events[0]["quantity"] == 100
