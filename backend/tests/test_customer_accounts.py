import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.database import Base
from models.accounts import AccountManager, CustomerStatus

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
async def test_BIL_013_customer_accounts(async_session):
    """
    BIL-013: Customer accounts.
    Tests creation, metadata enrichment, status transitions (ACTIVE, SUSPENDED, CLOSED),
    and retrieving customer details.
    """
    mgr = AccountManager(async_session)

    # 1. Create customer
    cust = await mgr.create_customer(
        customer_id="cust-enterprise-42",
        tenant_id="tenant-cloud",
        name="Global Corp",
        email="finance@globalcorp.example",
        currency="USD_CENTS",
        metadata={"tier": "vip", "region": "us-east"}
    )
    assert cust.customer_id == "cust-enterprise-42"
    assert cust.tenant_id == "tenant-cloud"
    assert cust.status == CustomerStatus.ACTIVE.value
    assert cust.metadata["tier"] == "vip"

    # 2. Retrieve customer
    fetched = await mgr.get_customer("cust-enterprise-42")
    assert fetched is not None
    assert fetched.name == "Global Corp"
    assert fetched.metadata["region"] == "us-east"

    # 3. Update customer details
    updated = await mgr.update_customer(
        customer_id="cust-enterprise-42",
        name="Global Corp International",
        metadata={"tier": "vip", "region": "eu-central"}
    )
    assert updated.name == "Global Corp International"
    assert updated.metadata["region"] == "eu-central"

    # 4. Suspend customer
    suspended = await mgr.suspend_customer("cust-enterprise-42")
    assert suspended.status == CustomerStatus.SUSPENDED.value

    # 5. Close customer
    closed = await mgr.close_customer("cust-enterprise-42")
    assert closed.status == CustomerStatus.CLOSED.value
