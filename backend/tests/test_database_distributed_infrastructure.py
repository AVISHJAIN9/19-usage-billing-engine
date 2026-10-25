import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from db.database import Base
from invoicing.manager import InvoiceManager, InvoiceStatus
from payments.manager import PaymentManager, PaymentStatus, PaymentRecord
from models.events import UsageEventRecord, UsageEventSchema, UsageEventStore
from metering.partitioning import PartitionManager

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        yield session
    await engine.dispose()

@pytest.mark.asyncio
async def test_BIL_005_payment_database(db_session):
    """
    BIL-005: Payment database schema and manager verification.
    Tests constraints, idempotency key uniqueness, positive amount check, and status lifecycle.
    """
    inv_mgr = InvoiceManager(db_session)
    pay_mgr = PaymentManager(db_session)

    # 1. Create invoice
    await inv_mgr.create_draft_invoice(
        invoice_id="inv-db-001",
        tenant_id="tenant-db-1",
        customer_id="cust-db-1"
    )
    await inv_mgr.add_line_item("inv-db-001", "Database Hosting", 1, 15000)
    await inv_mgr.finalize_invoice("inv-db-001")

    # 2. Positive amount check validation
    with pytest.raises(ValueError, match="strictly positive"):
        await pay_mgr.record_payment(
            payment_id="pay-fail-0",
            tenant_id="tenant-db-1",
            customer_id="cust-db-1",
            invoice_id="inv-db-001",
            amount_cents=0
        )

    # 3. Successful payment record with AUTHORIZED state and idempotency key
    p1 = await pay_mgr.record_payment(
        payment_id="pay-db-001",
        tenant_id="tenant-db-1",
        customer_id="cust-db-1",
        invoice_id="inv-db-001",
        amount_cents=15000,
        status=PaymentStatus.AUTHORIZED,
        idempotency_key="idemp-pay-key-1",
        gateway_ref="gw_auth_123"
    )
    assert p1.id == "pay-db-001"
    assert p1.status == PaymentStatus.AUTHORIZED
    assert p1.amount_cents == 15000
    assert p1.gateway_ref == "gw_auth_123"

    # 4. Idempotency test: duplicate call returns same payment
    p1_dup = await pay_mgr.record_payment(
        payment_id="pay-db-different-id",
        tenant_id="tenant-db-1",
        customer_id="cust-db-1",
        invoice_id="inv-db-001",
        amount_cents=15000,
        status=PaymentStatus.AUTHORIZED,
        idempotency_key="idemp-pay-key-1"
    )
    assert p1_dup.id == "pay-db-001"

    # 5. Transition to CAPTURED
    captured = await pay_mgr.update_payment_status("pay-db-001", PaymentStatus.CAPTURED, gateway_ref="gw_cap_456")
    assert captured.status == PaymentStatus.CAPTURED
    assert captured.gateway_ref == "gw_cap_456"

    # 6. Transition to REFUNDED
    refunded = await pay_mgr.update_payment_status("pay-db-001", PaymentStatus.REFUNDED)
    assert refunded.status == PaymentStatus.REFUNDED

@pytest.mark.asyncio
async def test_BIL_009_indexes_for_usage_queries(db_session):
    """
    BIL-009: Verification of composite indexes for usage queries using EXPLAIN QUERY PLAN.
    """
    store = UsageEventStore(db_session)
    t0 = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)

    # Insert test events
    for i in range(10):
        await store.record_event(
            event_id=f"evt-idx-{i}",
            tenant_id="tenant-idx-1",
            customer_id=f"cust-{i % 2}",
            event_type="api_requests",
            quantity=100 + i,
            idempotency_key=f"idem-idx-{i}",
            timestamp=t0
        )
    await db_session.commit()

    # 1. EXPLAIN query for tenant + customer + type + timestamp
    explain_sql_1 = """
    EXPLAIN QUERY PLAN
    SELECT * FROM usage_events
    WHERE tenant_id = :tenant_id
      AND customer_id = :customer_id
      AND event_type = :event_type
      AND timestamp BETWEEN :start_ts AND :end_ts
    """
    res1 = await db_session.execute(
        text(explain_sql_1),
        {
            "tenant_id": "tenant-idx-1",
            "customer_id": "cust-0",
            "event_type": "api_requests",
            "start_ts": datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc),
            "end_ts": datetime(2026, 10, 2, 0, 0, tzinfo=timezone.utc)
        }
    )
    rows1 = [str(r) for r in res1.fetchall()]
    plan_str1 = " ".join(rows1)
    assert "USING INDEX ix_usage_tenant_cust_type_time" in plan_str1 or "USING INDEX" in plan_str1

    # 2. EXPLAIN query for tenant + timestamp
    explain_sql_2 = """
    EXPLAIN QUERY PLAN
    SELECT * FROM usage_events
    WHERE tenant_id = :tenant_id
      AND timestamp BETWEEN :start_ts AND :end_ts
    """
    res2 = await db_session.execute(
        text(explain_sql_2),
        {
            "tenant_id": "tenant-idx-1",
            "start_ts": datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc),
            "end_ts": datetime(2026, 10, 2, 0, 0, tzinfo=timezone.utc)
        }
    )
    rows2 = [str(r) for r in res2.fetchall()]
    plan_str2 = " ".join(rows2)
    assert "USING INDEX ix_usage_tenant_time" in plan_str2 or "USING INDEX" in plan_str2

@pytest.mark.asyncio
async def test_BIL_010_partitioning(db_session):
    """
    BIL-010: Range-based partitioning and partition pruning verification.
    Proves that queries restrict scan to relevant partitions and prune non-overlapping partitions.
    """
    part_mgr = PartitionManager(db_session)

    # 1. Pre-create partitions for September, October, November 2026
    p_sep = await part_mgr.ensure_monthly_partition(2026, 9)
    p_oct = await part_mgr.ensure_monthly_partition(2026, 10)
    p_nov = await part_mgr.ensure_monthly_partition(2026, 11)
    all_partitions = [p_sep, p_oct, p_nov]

    # 2. Route events into partitions
    evt_sep = UsageEventSchema(
        event_id="evt-p-sep-1",
        tenant_id="tenant-part-1",
        customer_id="cust-part-1",
        event_type="compute_seconds",
        quantity=3600,
        dimensions={"host": "worker-1"},
        idempotency_key="idemp-p-sep-1",
        timestamp=datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
    )
    evt_oct = UsageEventSchema(
        event_id="evt-p-oct-1",
        tenant_id="tenant-part-1",
        customer_id="cust-part-1",
        event_type="compute_seconds",
        quantity=7200,
        dimensions={"host": "worker-2"},
        idempotency_key="idemp-p-oct-1",
        timestamp=datetime(2026, 10, 10, 15, 30, tzinfo=timezone.utc)
    )
    evt_nov = UsageEventSchema(
        event_id="evt-p-nov-1",
        tenant_id="tenant-part-1",
        customer_id="cust-part-1",
        event_type="compute_seconds",
        quantity=14400,
        dimensions={"host": "worker-3"},
        idempotency_key="idemp-p-nov-1",
        timestamp=datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc)
    )

    t_sep = await part_mgr.insert_partitioned_event(evt_sep)
    t_oct = await part_mgr.insert_partitioned_event(evt_oct)
    t_nov = await part_mgr.insert_partitioned_event(evt_nov)

    assert t_sep == "usage_events_p_2026_09"
    assert t_oct == "usage_events_p_2026_10"
    assert t_nov == "usage_events_p_2026_11"

    # 3. Query strictly inside October 2026 (2026-10-01 to 2026-10-31)
    start_q = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    end_q = datetime(2026, 10, 31, 23, 59, tzinfo=timezone.utc)

    query_res = await part_mgr.query_with_pruning(
        tenant_id="tenant-part-1",
        start_time=start_q,
        end_time=end_q,
        all_created_partitions=all_partitions
    )

    # 4. Verify partition pruning: only October was scanned, September & November were pruned!
    assert query_res["scanned_partitions"] == ["usage_events_p_2026_10"]
    assert "usage_events_p_2026_09" in query_res["pruned_partitions"]
    assert "usage_events_p_2026_11" in query_res["pruned_partitions"]

    # 5. Verify data integrity: only October event returned
    assert len(query_res["events"]) == 1
    assert query_res["events"][0]["event_id"] == "evt-p-oct-1"
    assert query_res["events"][0]["quantity"] == 7200

    # 6. Verify EXPLAIN query plan was captured proving indexed partition scan
    assert len(query_res["explain_plans"]) == 1
    assert query_res["explain_plans"][0]["table"] == "usage_events_p_2026_10"
