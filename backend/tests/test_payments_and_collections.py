"""
Tests for Payments & Collections:
- BIL-092: Payment authorization
- BIL-093: Payment capture
- BIL-097: Payment retries
- BIL-098: Failed payment handling
- BIL-099: Dunning schedule (manual clock)
- BIL-100: Grace period (manual clock)
- BIL-101: Automatic collection (idempotent)
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from db.database import Base
from payments.manager import PaymentRecord, PaymentStatus
from payments.collections import (
    PaymentCollectionsManager,
    DunningStage,
    AccountStanding
)
from invoicing.manager import InvoiceRecord, InvoiceStatus


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
async def test_BIL_092_and_093_payment_authorization_and_capture(async_session: AsyncSession):
    manager = PaymentCollectionsManager(async_session)

    # Setup invoice
    inv = InvoiceRecord(
        id="inv-pay-01",
        tenant_id="tenant-1",
        customer_id="cust-1",
        status=InvoiceStatus.FINALIZED.value,
        total_cents=10000,
        due_date=datetime.now(timezone.utc)
    )
    async_session.add(inv)
    await async_session.commit()

    # BIL-092: Authorize payment
    pay = await manager.authorize_payment(
        payment_id="pay-auth-1",
        tenant_id="tenant-1",
        customer_id="cust-1",
        invoice_id="inv-pay-01",
        amount_cents=10000,
        idempotency_key="idemp-auth-01"
    )
    assert pay.status == PaymentStatus.AUTHORIZED.value

    # Idempotent re-authorization returns same record
    pay_idemp = await manager.authorize_payment(
        payment_id="pay-auth-diff",
        tenant_id="tenant-1",
        customer_id="cust-1",
        invoice_id="inv-pay-01",
        amount_cents=10000,
        idempotency_key="idemp-auth-01"
    )
    assert pay_idemp.id == "pay-auth-1"

    # BIL-093: Capture cannot exceed authorized amount
    with pytest.raises(ValueError, match="exceeds authorized amount"):
        await manager.capture_payment("pay-auth-1", capture_amount_cents=15000)

    # Valid capture transitions to CAPTURED and marks invoice PAID
    captured = await manager.capture_payment("pay-auth-1", capture_amount_cents=10000)
    assert captured.status == PaymentStatus.CAPTURED.value
    assert captured.amount_cents == 10000

    # Invoice is now marked PAID
    await async_session.refresh(inv)
    assert inv.status == InvoiceStatus.PAID.value


@pytest.mark.asyncio
async def test_BIL_097_and_098_payment_retries_and_failure_handling(async_session: AsyncSession):
    manager = PaymentCollectionsManager(async_session)

    # Create payment record
    pay = await manager.authorize_payment(
        payment_id="pay-fail-1",
        tenant_id="tenant-1",
        customer_id="cust-2",
        invoice_id="inv-fail-01",
        amount_cents=5000
    )

    # BIL-098: Failure handling
    failed = await manager.handle_payment_failure(
        payment_id="pay-fail-1",
        error_code="insufficient_funds",
        error_message="Card has insufficient funds"
    )
    assert failed.status == PaymentStatus.FAILED.value
    assert failed.error_code == "insufficient_funds"

    # BIL-097: Idempotent payment retries
    att1 = await manager.retry_payment(
        payment_id="pay-fail-1",
        attempt_number=1,
        idempotency_key="idemp-retry-01"
    )
    assert att1.attempt_number == 1
    assert att1.status == "SUCCESS"

    # Repeated call with same idempotency key returns same attempt
    att1_repeat = await manager.retry_payment(
        payment_id="pay-fail-1",
        attempt_number=1,
        idempotency_key="idemp-retry-01"
    )
    assert att1_repeat.attempt_id == att1.attempt_id


@pytest.mark.asyncio
async def test_BIL_099_and_100_dunning_and_grace_period_manual_clock(async_session: AsyncSession):
    manager = PaymentCollectionsManager(async_session)

    due_date = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    # Grace period = 7 days -> grace_period_until is 2026-10-08
    dunning = await manager.initiate_dunning(
        tenant_id="tenant-1",
        customer_id="cust-dunning",
        invoice_id="inv-dun-1",
        due_date=due_date,
        grace_days=7
    )

    # Day 0: ATTEMPT_1, PAST_DUE
    d_day0 = await manager.evaluate_dunning(dunning.dunning_id, current_time=due_date)
    assert d_day0.stage == DunningStage.ATTEMPT_1.value
    assert d_day0.standing == AccountStanding.PAST_DUE.value

    # Day 3: ATTEMPT_2, still within grace period (PAST_DUE)
    d_day3 = await manager.evaluate_dunning(dunning.dunning_id, current_time=due_date + timedelta(days=3))
    assert d_day3.stage == DunningStage.ATTEMPT_2.value
    assert d_day3.standing == AccountStanding.PAST_DUE.value

    # Day 7: ATTEMPT_3, at the boundary of grace period (PAST_DUE)
    d_day7 = await manager.evaluate_dunning(dunning.dunning_id, current_time=due_date + timedelta(days=7))
    assert d_day7.stage == DunningStage.ATTEMPT_3.value
    assert d_day7.standing == AccountStanding.PAST_DUE.value

    # Day 8: Grace period expired! Transition to SUSPENDED
    d_day8 = await manager.evaluate_dunning(dunning.dunning_id, current_time=due_date + timedelta(days=8))
    assert d_day8.stage == DunningStage.ATTEMPT_3.value
    assert d_day8.standing == AccountStanding.SUSPENDED.value

    # Day 14+: FINAL_ESCALATION and SUSPENDED
    d_day14 = await manager.evaluate_dunning(dunning.dunning_id, current_time=due_date + timedelta(days=15))
    assert d_day14.stage == DunningStage.FINAL_ESCALATION.value
    assert d_day14.standing == AccountStanding.SUSPENDED.value


@pytest.mark.asyncio
async def test_BIL_101_automatic_collection_idempotent(async_session: AsyncSession):
    manager = PaymentCollectionsManager(async_session)

    as_of = datetime(2026, 10, 24, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Past-due finalized invoice
    inv_due = InvoiceRecord(
        id="inv-auto-1",
        tenant_id="tenant-acme",
        customer_id="cust-1",
        status=InvoiceStatus.FINALIZED.value,
        total_cents=7500,
        due_date=as_of - timedelta(days=1)
    )
    # 2. Future invoice (not due yet)
    inv_future = InvoiceRecord(
        id="inv-auto-2",
        tenant_id="tenant-acme",
        customer_id="cust-2",
        status=InvoiceStatus.FINALIZED.value,
        total_cents=12000,
        due_date=as_of + timedelta(days=5)
    )
    async_session.add_all([inv_due, inv_future])
    await async_session.commit()

    # Run automatic collection
    results = await manager.execute_automatic_collection(tenant_id="tenant-acme", as_of=as_of)
    assert len(results) == 1
    assert results[0]["invoice_id"] == "inv-auto-1"
    assert results[0]["status"] == "COLLECTED"
    assert results[0]["amount_cents"] == 7500

    # Invoice is marked PAID
    await async_session.refresh(inv_due)
    assert inv_due.status == InvoiceStatus.PAID.value

    # Running collection again is idempotent and does not double charge
    results_repeat = await manager.execute_automatic_collection(tenant_id="tenant-acme", as_of=as_of)
    assert len(results_repeat) == 0  # inv_due is now PAID, so not returned in due query
