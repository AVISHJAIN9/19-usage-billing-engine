"""
Tests for Security, RBAC, Tenant Isolation & Audit Logging:
- BIL-127: API authentication
- BIL-128: Deny-by-default RBAC
- BIL-129: Tenant isolation
- BIL-136: Audit logging & PII redaction
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from db.database import Base
from security.auth import AuthManager, Role, AuthContext
from security.audit import AuditLogManager, AuditLogRecord


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
async def test_BIL_127_api_authentication(async_session: AsyncSession):
    manager = AuthManager(async_session)

    # 1. Create API key for tenant
    raw_key, rec = await manager.create_api_key(tenant_id="tenant-alpha", role=Role.FINANCE)
    assert rec.key_hash != raw_key  # Must be hashed in DB

    # 2. Authenticate with valid key
    ctx = await manager.authenticate(raw_key)
    assert ctx is not None
    assert ctx.tenant_id == "tenant-alpha"
    assert ctx.role == Role.FINANCE

    # 3. Invalid key fails
    assert await manager.authenticate("bil_finance_invalid_fake_key") is None

    # 4. Revoked key fails
    rec.is_revoked = True
    await async_session.commit()
    assert await manager.authenticate(raw_key) is None


@pytest.mark.asyncio
async def test_BIL_128_deny_by_default_rbac(async_session: AsyncSession):
    # Test roles permissions
    owner_ctx = AuthContext(tenant_id="t1", role=Role.OWNER, key_id="k1")
    finance_ctx = AuthContext(tenant_id="t1", role=Role.FINANCE, key_id="k2")
    viewer_ctx = AuthContext(tenant_id="t1", role=Role.VIEWER, key_id="k3")
    service_ctx = AuthContext(tenant_id="t1", role=Role.SERVICE, key_id="k4")

    # OWNER has admin & write
    assert AuthManager.authorize_permission(owner_ctx, "invoices:write") is True
    assert AuthManager.authorize_permission(owner_ctx, "admin:all") is True

    # FINANCE has invoice write, but NOT admin:all
    assert AuthManager.authorize_permission(finance_ctx, "invoices:write") is True
    assert AuthManager.authorize_permission(finance_ctx, "admin:all") is False

    # VIEWER has read only, write operations denied by default
    assert AuthManager.authorize_permission(viewer_ctx, "invoices:read") is True
    assert AuthManager.authorize_permission(viewer_ctx, "invoices:write") is False
    assert AuthManager.authorize_permission(viewer_ctx, "payments:write") is False

    # SERVICE has ingest only
    assert AuthManager.authorize_permission(service_ctx, "usage:ingest") is True
    assert AuthManager.authorize_permission(service_ctx, "invoices:write") is False

    # Unrecognized permission denied by default for all roles
    assert AuthManager.authorize_permission(owner_ctx, "random:unknown:perm") is False


@pytest.mark.asyncio
async def test_BIL_129_tenant_isolation(async_session: AsyncSession):
    ctx_tenant_a = AuthContext(tenant_id="tenant-A", role=Role.OWNER, key_id="kA")

    # Same tenant passes
    AuthManager.assert_tenant_isolation(ctx_tenant_a, "tenant-A")

    # Cross tenant access is strictly blocked
    with pytest.raises(PermissionError, match="Cross-tenant access violation"):
        AuthManager.assert_tenant_isolation(ctx_tenant_a, "tenant-B")


@pytest.mark.asyncio
async def test_BIL_136_audit_logging_and_pii_redaction(async_session: AsyncSession):
    audit_mgr = AuditLogManager(async_session)

    # Mutation payload containing sensitive PII and Tax ID
    before = {
        "plan_id": "starter",
        "tax_id": "12-3456789",
        "card_number": "4111-2222-3333-4444"
    }
    after = {
        "plan_id": "pro",
        "tax_id": "12-3456789",
        "card_number": "4111-2222-3333-4444",
        "notes": "Upgraded with SSN 123-45-6789"
    }

    entry = await audit_mgr.log_mutation(
        audit_id="audit-001",
        tenant_id="tenant-audit",
        actor="admin@example.com",
        action="subscription.upgrade",
        resource_type="subscription",
        resource_id="sub-100",
        before_state=before,
        after_state=after
    )

    assert entry.action == "subscription.upgrade"
    assert entry.before_state["tax_id"] == "[REDACTED]"
    assert entry.before_state["card_number"] == "[REDACTED]"
    assert "[REDACTED_TAX_ID]" in entry.after_state["notes"]

    # Grep test: raw database record must NEVER contain raw Tax ID or Credit Card
    from sqlalchemy import select
    res = await async_session.execute(select(AuditLogRecord).where(AuditLogRecord.audit_id == "audit-001"))
    raw_record = res.scalar_one()

    assert "12-3456789" not in (raw_record.before_state or "")
    assert "12-3456789" not in (raw_record.after_state or "")
    assert "4111-2222-3333-4444" not in (raw_record.before_state or "")
    assert "4111-2222-3333-4444" not in (raw_record.after_state or "")
    assert "123-45-6789" not in (raw_record.after_state or "")
