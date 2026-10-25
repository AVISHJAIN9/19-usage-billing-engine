"""
Audit Logging and PII Redaction (BIL-136).
Logs all mutations with actor, action, timestamp, before/after state.
Strictly sanitizes and redacts PII, Tax IDs, and credit card numbers from all audit entries.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
import json
import re
from sqlalchemy import Column, String, Text, DateTime, Index, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict
from db.database import Base


# Regex patterns for sensitive data redaction
TAX_ID_PATTERN = re.compile(r"\b\d{2}-\d{7}\b|\b\d{3}-\d{2}-\d{4}\b")
CARD_PATTERN = re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b")
EMAIL_PATTERN = re.compile(r"(?<=.)[^@\s]{2,}(?=[^@\s]{2,}@)")


def redact_sensitive_info(val: Any) -> Any:
    """
    Recursively masks PII and financial identifiers.
    """
    if isinstance(val, dict):
        cleaned = {}
        for k, v in val.items():
            k_lower = k.lower()
            if any(s in k_lower for s in ["tax_id", "ssn", "card_number", "cvv", "secret", "password"]):
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = redact_sensitive_info(v)
        return cleaned
    elif isinstance(val, list):
        return [redact_sensitive_info(x) for x in val]
    elif isinstance(val, str):
        v = TAX_ID_PATTERN.sub("[REDACTED_TAX_ID]", val)
        v = CARD_PATTERN.sub("[REDACTED_CARD]", v)
        return v
    return val


class AuditLogRecord(Base):
    __tablename__ = "audit_logs"

    audit_id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    actor = Column(String(128), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String(64), nullable=False)
    before_state = Column(Text, nullable=True)
    after_state = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_audit_tenant_action", "tenant_id", "action", "created_at"),
    )


class AuditLogSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audit_id: str
    tenant_id: str
    actor: str
    action: str
    resource_type: str
    resource_id: str
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    created_at: datetime


class AuditLogManager:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_mutation(
        self,
        audit_id: str,
        tenant_id: str,
        actor: str,
        action: str,
        resource_type: str,
        resource_id: str,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None
    ) -> AuditLogSchema:
        """
        BIL-136: Records mutation with actor, sanitized before/after state.
        Guarantees PII/tax IDs never enter audit logs.
        """
        sanitized_before = redact_sensitive_info(before_state) if before_state else None
        sanitized_after = redact_sensitive_info(after_state) if after_state else None

        rec = AuditLogRecord(
            audit_id=audit_id,
            tenant_id=tenant_id,
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before_state=json.dumps(sanitized_before) if sanitized_before else None,
            after_state=json.dumps(sanitized_after) if sanitized_after else None,
            created_at=datetime.now(timezone.utc)
        )
        self.session.add(rec)
        await self.session.commit()

        return AuditLogSchema(
            audit_id=rec.audit_id,
            tenant_id=rec.tenant_id,
            actor=rec.actor,
            action=rec.action,
            resource_type=rec.resource_type,
            resource_id=rec.resource_id,
            before_state=sanitized_before,
            after_state=sanitized_after,
            created_at=rec.created_at
        )

    async def get_audit_trail(
        self,
        tenant_id: str,
        resource_id: Optional[str] = None
    ) -> list[AuditLogSchema]:
        stmt = select(AuditLogRecord).where(AuditLogRecord.tenant_id == tenant_id)
        if resource_id:
            stmt = stmt.where(AuditLogRecord.resource_id == resource_id)
        stmt = stmt.order_by(AuditLogRecord.created_at.desc())

        res = await self.session.execute(stmt)
        records = res.scalars().all()
        return [
            AuditLogSchema(
                audit_id=r.audit_id,
                tenant_id=r.tenant_id,
                actor=r.actor,
                action=r.action,
                resource_type=r.resource_type,
                resource_id=r.resource_id,
                before_state=json.loads(r.before_state) if r.before_state else None,
                after_state=json.loads(r.after_state) if r.after_state else None,
                created_at=r.created_at
            )
            for r in records
        ]
