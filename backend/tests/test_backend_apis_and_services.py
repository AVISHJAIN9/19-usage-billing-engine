"""
Tests for Backend APIs & Services:
- BIL-104: Meter API
- BIL-106: Rating API
- BIL-107: Usage query API
- BIL-109: Payment API
- BIL-110: Subscription API
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from db.database import Base, get_db
from api.app import app
from models.events import UsageEventRecord


@pytest_asyncio.fixture
async def test_app_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, session_maker

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_BIL_104_meter_api(test_app_client):
    client, _ = test_app_client

    # 1. Create meter
    create_res = await client.post(
        "/v1/meters",
        json={
            "meter_id": "m-api-01",
            "tenant_id": "tenant-test",
            "name": "API Request Meter",
            "event_type": "api_requests",
            "aggregation_type": "SUM",
            "unit": "requests"
        }
    )
    assert create_res.status_code == 200
    data = create_res.json()
    assert data["meter_id"] == "m-api-01"
    assert data["event_type"] == "api_requests"

    # 2. Get meter
    get_res = await client.get("/v1/meters/m-api-01?tenant_id=tenant-test")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "API Request Meter"

    # 3. List meters
    list_res = await client.get("/v1/meters?tenant_id=tenant-test")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1


@pytest.mark.asyncio
async def test_BIL_106_rating_api(test_app_client):
    client, _ = test_app_client

    # 1. Register price book entry
    pbe_payload = {
        "id": "pbe-api-01",
        "tenant_id": "tenant-test",
        "plan_id": "pro-tier",
        "event_type": "compute_hours",
        "pricing_type": "TIERED_VOLUME",
        "flat_fee_cents": 1000,
        "free_units": 10,
        "unit_price_cents": 50,
        "min_charge_cents": 2000,
        "max_charge_cents": 50000,
        "included_units": 0,
        "overage_unit_price_cents": 0,
        "tiers": [
            {"up_to": 100, "unit_price_cents": 50, "flat_fee_cents": 0},
            {"up_to": None, "unit_price_cents": 30, "flat_fee_cents": 0}
        ]
    }
    pbe_res = await client.post("/v1/rating/price-books", json=pbe_payload)
    assert pbe_res.status_code == 200

    # 2. Query price book entries
    get_res = await client.get("/v1/rating/price-books?tenant_id=tenant-test&plan_id=pro-tier")
    assert get_res.status_code == 200
    entries = get_res.json()
    assert len(entries) >= 1
    assert entries[0]["id"] == "pbe-api-01"

    # 3. Calculate on-the-fly rating
    calc_res = await client.post(
        "/v1/rating/calculate",
        json={
            "entry": entries[0],
            "quantity": 60  # 10 free, 50 billable @ 50c = 2500 + 1000 flat = 3500c
        }
    )
    assert calc_res.status_code == 200
    r = calc_res.json()
    assert r["total_cents"] == 3500
    assert r["free_units_applied"] == 10
    assert r["billable_quantity"] == 50


@pytest.mark.asyncio
async def test_BIL_107_usage_query_api(test_app_client):
    client, session_maker = test_app_client

    start = datetime(2026, 10, 24, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 25, 0, 0, 0, tzinfo=timezone.utc)

    # Insert raw events into DB
    async with session_maker() as session:
        events = [
            UsageEventRecord(
                event_id="e-uq-1", tenant_id="t-uq", customer_id="c-uq",
                event_type="bandwidth_gb", quantity=150, idempotency_key="idemp-uq-1",
                timestamp=start + timedelta(hours=2)
            ),
            UsageEventRecord(
                event_id="e-uq-2", tenant_id="t-uq", customer_id="c-uq",
                event_type="bandwidth_gb", quantity=350, idempotency_key="idemp-uq-2",
                timestamp=start + timedelta(hours=8)
            )
        ]
        session.add_all(events)
        await session.commit()

    # Query usage via API
    res = await client.get(
        f"/v1/usage/query?tenant_id=t-uq&customer_id=c-uq&event_type=bandwidth_gb"
        f"&start_date={start.isoformat()}&end_date={end.isoformat()}"
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_quantity"] == 500


@pytest.mark.asyncio
async def test_BIL_109_payment_api(test_app_client):
    client, _ = test_app_client

    # 1. Authorize payment
    auth_res = await client.post(
        "/v1/payments/authorize",
        json={
            "payment_id": "pay-api-100",
            "tenant_id": "tenant-pay",
            "customer_id": "cust-pay",
            "invoice_id": "inv-pay-01",
            "amount_cents": 8500,
            "idempotency_key": "idemp-pay-100"
        }
    )
    assert auth_res.status_code == 200
    auth_data = auth_res.json()
    assert auth_data["status"] == "AUTHORIZED"
    assert auth_data["amount_cents"] == 8500

    # 2. Capture payment
    cap_res = await client.post(
        "/v1/payments/pay-api-100/capture",
        json={"amount_cents": 8500}
    )
    assert cap_res.status_code == 200
    cap_data = cap_res.json()
    assert cap_data["status"] == "CAPTURED"
    assert cap_data["amount_cents"] == 8500


@pytest.mark.asyncio
async def test_BIL_110_subscription_api(test_app_client):
    client, _ = test_app_client

    start = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 1, 0, 0, 0, tzinfo=timezone.utc)
    upgrade_date = datetime(2026, 10, 16, 0, 0, 0, tzinfo=timezone.utc)

    # 1. Create subscription
    sub_res = await client.post(
        "/v1/subscriptions",
        json={
            "subscription_id": "sub-api-100",
            "tenant_id": "tenant-sub",
            "customer_id": "cust-sub",
            "plan_id": "starter-plan",
            "current_period_start": start.isoformat(),
            "current_period_end": end.isoformat()
        }
    )
    assert sub_res.status_code == 200
    assert sub_res.json()["subscription_id"] == "sub-api-100"

    # 2. Upgrade subscription
    upg_res = await client.post(
        "/v1/subscriptions/sub-api-100/upgrade",
        json={
            "new_plan_id": "pro-plan",
            "new_plan_rate_cents": 6000,
            "old_plan_rate_cents": 3000,
            "as_of": upgrade_date.isoformat()
        }
    )
    assert upg_res.status_code == 200
    upg_data = upg_res.json()
    assert upg_data["subscription"]["plan_id"] == "pro-plan"
    assert upg_data["proration"]["net_proration_cents"] > 0
