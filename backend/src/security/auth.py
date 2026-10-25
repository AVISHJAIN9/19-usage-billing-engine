"""
Security, Authentication & Deny-by-Default RBAC (BIL-127, BIL-128, BIL-129).
Roles:
- OWNER: Full administrative access.
- FINANCE: Invoicing, payments, and subscription management.
- VIEWER: Read-only access to usage, invoices, and metrics.
- SERVICE: High-throughput ingestion and webhook submission.
Deny-by-default on all unrecognized operations and cross-tenant requests.
"""

from typing import Dict, Any, Optional, Set
from datetime import datetime, timezone
from enum import Enum
import hashlib
import secrets
from sqlalchemy import Column, String, Boolean, DateTime, Index, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict
from db.database import Base


class Role(str, Enum):
    OWNER = "OWNER"
    FINANCE = "FINANCE"
    VIEWER = "VIEWER"
    SERVICE = "SERVICE"


ROLE_PERMISSIONS: Dict[Role, Set[str]] = {
    Role.OWNER: {
        "usage:ingest", "usage:read", "invoices:read", "invoices:write",
        "payments:write", "payments:read", "subscriptions:write", "subscriptions:read",
        "plans:write", "plans:read", "admin:all"
    },
    Role.FINANCE: {
        "usage:read", "invoices:read", "invoices:write", "payments:write",
        "payments:read", "subscriptions:write", "subscriptions:read", "plans:read"
    },
    Role.VIEWER: {
        "usage:read", "invoices:read", "payments:read", "subscriptions:read", "plans:read"
    },
    Role.SERVICE: {
        "usage:ingest", "webhooks:process"
    }
}


class ApiKeyRecord(Base):
    __tablename__ = "api_keys"

    key_id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    key_hash = Column(String(64), nullable=False, unique=True, index=True)
    role = Column(String(32), default=Role.VIEWER.value, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_api_key_lookup", "tenant_id", "key_hash"),
    )


class AuthContext(BaseModel):
    tenant_id: str
    role: Role
    key_id: str


class AuthManager:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _hash_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode()).hexdigest()

    async def create_api_key(
        self,
        tenant_id: str,
        role: Role = Role.VIEWER
    ) -> tuple[str, ApiKeyRecord]:
        """
        Generates secure random API key, hashes and persists in DB.
        Raw key is returned only once.
        """
        raw_key = f"bil_{role.value.lower()}_{secrets.token_urlsafe(32)}"
        key_hash = self._hash_key(raw_key)
        key_id = f"key_{secrets.token_hex(8)}"

        rec = ApiKeyRecord(
            key_id=key_id,
            tenant_id=tenant_id,
            key_hash=key_hash,
            role=role.value,
            is_revoked=False,
            created_at=datetime.now(timezone.utc)
        )
        self.session.add(rec)
        await self.session.commit()
        return raw_key, rec

    async def authenticate(self, raw_key: str) -> Optional[AuthContext]:
        """
        BIL-127: Validates raw API key against hashed store.
        """
        if not raw_key:
            return None
        key_hash = self._hash_key(raw_key)

        stmt = select(ApiKeyRecord).where(
            ApiKeyRecord.key_hash == key_hash,
            ApiKeyRecord.is_revoked == False
        )
        res = await self.session.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            return None

        return AuthContext(
            tenant_id=rec.tenant_id,
            role=Role(rec.role),
            key_id=rec.key_id
        )

    @staticmethod
    def authorize_permission(context: AuthContext, permission: str) -> bool:
        """
        BIL-128: Deny-by-default RBAC check.
        """
        allowed_perms = ROLE_PERMISSIONS.get(context.role, set())
        return permission in allowed_perms

    @staticmethod
    def assert_tenant_isolation(context: AuthContext, requested_tenant_id: str):
        """
        BIL-129: Guarantees a tenant cannot access or mutate another tenant's resources.
        """
        if context.tenant_id != requested_tenant_id:
            raise PermissionError(
                f"Cross-tenant access violation: Caller tenant '{context.tenant_id}' "
                f"attempted to access tenant '{requested_tenant_id}'"
            )
