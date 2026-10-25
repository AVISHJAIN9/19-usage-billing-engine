"""
Time-Range Partitioning and Pruning Engine (BIL-010).
Partitions usage events by time window (monthly partitions) with check constraints
and enforces partition pruning so queries only scan relevant date ranges.
"""

from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone
import calendar
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from models.events import UsageEventSchema

class PartitionManager:
    """
    Manages range-based partition tables for high-volume metered usage events.
    Verifies that queries outside a partition's time boundary prune the partition.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    def get_partition_table_name(self, year: int, month: int) -> str:
        return f"usage_events_p_{year}_{month:02d}"

    async def ensure_monthly_partition(self, year: int, month: int) -> str:
        """
        Creates a monthly partition table with time-range CHECK constraint.
        """
        table_name = self.get_partition_table_name(year, month)
        _, last_day = calendar.monthrange(year, month)
        start_ts = f"{year:04d}-{month:02d}-01 00:00:00"
        # Next month start
        if month == 12:
            next_start_ts = f"{year+1:04d}-01-01 00:00:00"
        else:
            next_start_ts = f"{year:04d}-{month+1:02d}-01 00:00:00"

        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            event_id VARCHAR(64) PRIMARY KEY,
            tenant_id VARCHAR(64) NOT NULL,
            customer_id VARCHAR(64) NOT NULL,
            event_type VARCHAR(64) NOT NULL,
            quantity BIGINT NOT NULL,
            dimensions_json VARCHAR(1024) NOT NULL,
            idempotency_key VARCHAR(128) NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            received_at TIMESTAMP NOT NULL,
            CONSTRAINT chk_time_range CHECK (timestamp >= '{start_ts}' AND timestamp < '{next_start_ts}'),
            CONSTRAINT chk_qty_nonneg CHECK (quantity >= 0)
        );
        """
        await self.session.execute(text(create_sql))
        # Create indexes on partition
        idx_sql = f"""
        CREATE INDEX IF NOT EXISTS ix_{table_name}_tenant_time ON {table_name} (tenant_id, timestamp);
        """
        await self.session.execute(text(idx_sql))
        await self.session.commit()
        return table_name

    async def insert_partitioned_event(self, event: UsageEventSchema) -> str:
        """
        Routes and inserts a metered usage event directly into its respective monthly partition.
        """
        ts = event.timestamp
        table_name = await self.ensure_monthly_partition(ts.year, ts.month)

        dims_str = "{}"
        if event.dimensions:
            import json
            dims_str = json.dumps(event.dimensions)

        insert_sql = f"""
        INSERT INTO {table_name} (
            event_id, tenant_id, customer_id, event_type, quantity, dimensions_json, idempotency_key, timestamp, received_at
        ) VALUES (
            :event_id, :tenant_id, :customer_id, :event_type, :quantity, :dimensions_json, :idempotency_key, :timestamp, :received_at
        )
        """
        now_ts = datetime.now(timezone.utc)
        await self.session.execute(
            text(insert_sql),
            {
                "event_id": event.event_id,
                "tenant_id": event.tenant_id,
                "customer_id": event.customer_id,
                "event_type": event.event_type,
                "quantity": event.quantity,
                "dimensions_json": dims_str,
                "idempotency_key": event.idempotency_key,
                "timestamp": ts,
                "received_at": now_ts
            }
        )
        await self.session.commit()
        return table_name

    def get_overlapping_partitions(self, start_time: datetime, end_time: datetime) -> List[Tuple[int, int]]:
        """
        Calculates distinct (year, month) buckets required for the given date range.
        Prunes all other existing partitions!
        """
        partitions = []
        cur_year = start_time.year
        cur_month = start_time.month

        while (cur_year < end_time.year) or (cur_year == end_time.year and cur_month <= end_time.month):
            partitions.append((cur_year, cur_month))
            if cur_month == 12:
                cur_year += 1
                cur_month = 1
            else:
                cur_month += 1
        return partitions

    async def query_with_pruning(
        self,
        tenant_id: str,
        start_time: datetime,
        end_time: datetime,
        all_created_partitions: List[str]
    ) -> Dict[str, Any]:
        """
        Executes query restricted strictly to pruned partition tables.
        Returns queried events, active partition tables, and pruned partition tables.
        """
        required_buckets = self.get_overlapping_partitions(start_time, end_time)
        required_tables = [self.get_partition_table_name(y, m) for y, m in required_buckets]

        active_tables = [t for t in required_tables if t in all_created_partitions]
        pruned_tables = [t for t in all_created_partitions if t not in active_tables]

        if not active_tables:
            return {
                "events": [],
                "scanned_partitions": [],
                "pruned_partitions": pruned_tables,
                "explain_plans": []
            }

        # Query only the active partitions
        events = []
        explain_plans = []
        for t in active_tables:
            # Run EXPLAIN QUERY PLAN to prove index/scan on active partition
            plan_sql = f"EXPLAIN QUERY PLAN SELECT * FROM {t} WHERE tenant_id = :tenant_id AND timestamp BETWEEN :start_ts AND :end_ts"
            plan_res = await self.session.execute(
                text(plan_sql),
                {"tenant_id": tenant_id, "start_ts": start_time, "end_ts": end_time}
            )
            rows = plan_res.fetchall()
            explain_plans.append({"table": t, "plan": [str(r) for r in rows]})

            select_sql = f"SELECT event_id, tenant_id, customer_id, event_type, quantity, timestamp FROM {t} WHERE tenant_id = :tenant_id AND timestamp BETWEEN :start_ts AND :end_ts"
            res = await self.session.execute(
                text(select_sql),
                {"tenant_id": tenant_id, "start_ts": start_time, "end_ts": end_time}
            )
            for r in res.fetchall():
                events.append({
                    "event_id": r[0],
                    "tenant_id": r[1],
                    "customer_id": r[2],
                    "event_type": r[3],
                    "quantity": r[4],
                    "timestamp": r[5]
                })

        return {
            "events": events,
            "scanned_partitions": active_tables,
            "pruned_partitions": pruned_tables,
            "explain_plans": explain_plans
        }
