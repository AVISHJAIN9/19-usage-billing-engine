"""
Real-Time Usage Counters and Database Reconciliation (BIL-063).
Provides low-latency Redis-backed counters with periodic or on-demand reconciliation against
the Postgres raw events store (which remains the authoritative source of truth).
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from models.events import UsageEventRecord


class RealtimeUsageCounter:
    """
    Manages real-time usage counters with hot Redis-like fast cache and
    reconciliation against the Postgres immutable event store.
    """
    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._local_redis_store: Dict[str, int] = {}

    def _make_key(self, tenant_id: str, customer_id: str, event_type: str) -> str:
        return f"counter:{tenant_id}:{customer_id}:{event_type}"

    async def increment(self, tenant_id: str, customer_id: str, event_type: str, amount: int = 1) -> int:
        """
        Increments the fast real-time counter.
        """
        key = self._make_key(tenant_id, customer_id, event_type)
        if self._redis:
            try:
                return await self._redis.incrby(key, amount)
            except Exception:
                pass
        current = self._local_redis_store.get(key, 0) + amount
        self._local_redis_store[key] = current
        return current

    async def get_count(self, tenant_id: str, customer_id: str, event_type: str) -> int:
        key = self._make_key(tenant_id, customer_id, event_type)
        if self._redis:
            try:
                val = await self._redis.get(key)
                if val is not None:
                    return int(val)
            except Exception:
                pass
        return self._local_redis_store.get(key, 0)

    async def reconcile_with_db(
        self,
        session: AsyncSession,
        tenant_id: str,
        customer_id: str,
        event_type: str,
        max_allowed_drift: int = 100
    ) -> Dict[str, Any]:
        """
        Reconciles the real-time cache against Postgres (authoritative source of truth).
        Detects drift, verifies if drift is within documented bounds, and updates
        the cache to match Postgres exactly.
        """
        key = self._make_key(tenant_id, customer_id, event_type)
        cache_before = await self.get_count(tenant_id, customer_id, event_type)

        stmt = (
            select(func.coalesce(func.sum(UsageEventRecord.quantity), 0))
            .where(
                UsageEventRecord.tenant_id == tenant_id,
                UsageEventRecord.customer_id == customer_id,
                UsageEventRecord.event_type == event_type
            )
        )
        res = await session.execute(stmt)
        db_source_of_truth = int(res.scalar_one())

        drift = abs(cache_before - db_source_of_truth)
        drift_within_bounds = (drift <= max_allowed_drift)

        # Update cache to match authoritative Postgres DB state
        if self._redis:
            try:
                await self._redis.set(key, db_source_of_truth)
            except Exception:
                pass
        self._local_redis_store[key] = db_source_of_truth

        return {
            "tenant_id": tenant_id,
            "customer_id": customer_id,
            "event_type": event_type,
            "cache_before": cache_before,
            "db_source_of_truth": db_source_of_truth,
            "drift": drift,
            "drift_within_bounds": drift_within_bounds,
            "reconciled": True
        }
