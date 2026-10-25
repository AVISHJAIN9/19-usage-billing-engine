"""
FastAPI Application for Usage & Billing Engine (Project 19).
Exposes:
- Usage Ingestion API (BIL-103)
- Invoice API (BIL-108)
- Health check and CORS for Billing Console
"""

from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

from db.database import get_db, init_db, AsyncSessionLocal
from metering.ingestion import UsageIngestionPipeline, IngestEventPayload, IngestionResponse, IngestionStatus
from invoicing.manager import InvoiceManager, InvoiceSchema, InvoiceLineItemSchema, InvoiceStatus


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    await init_db()
    yield


app = FastAPI(
    title="Usage Billing Engine API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health(session: AsyncSession = Depends(get_db)):
    res = await session.execute(select(1))
    alive = (res.scalar() == 1)
    return {
        "status": "ok" if alive else "down",
        "service": "19-usage-billing-engine",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ============================================================================
# BIL-103: Usage Ingestion API
# ============================================================================

@app.post("/v1/usage/events", response_model=IngestionResponse)
async def ingest_single_event(
    payload: IngestEventPayload,
    session: AsyncSession = Depends(get_db)
):
    """
    Ingests a single metered usage event (BIL-103).
    """
    pipeline = UsageIngestionPipeline(session)
    res = await pipeline.ingest_event(payload)
    if res.status == IngestionStatus.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Event rejected: {res.error}"
        )
    return res


@app.post("/v1/usage/events/batch", response_model=List[IngestionResponse])
async def ingest_batch_events(
    events: List[IngestEventPayload],
    session: AsyncSession = Depends(get_db)
):
    """
    Ingests a batch of metered usage events (BIL-103).
    """
    pipeline = UsageIngestionPipeline(session)
    return await pipeline.ingest_batch(events)


@app.get("/v1/usage/events")
async def query_events(
    tenant_id: str = Query(...),
    customer_id: str = Query(...),
    event_type: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db)
):
    """
    Queries usage events for a customer (BIL-103).
    """
    pipeline = UsageIngestionPipeline(session)
    events = await pipeline.event_store.query_events(
        tenant_id=tenant_id,
        customer_id=customer_id,
        event_type=event_type
    )
    return [e.model_dump() for e in events]


# ============================================================================
# BIL-108: Invoice API
# ============================================================================

class CreateInvoiceRequest(BaseModel):
    invoice_id: str
    tenant_id: str
    customer_id: str
    period_id: Optional[str] = None
    due_days: int = 30


class AddLineItemRequest(BaseModel):
    description: str
    quantity: int
    unit_price_cents: int
    event_type: Optional[str] = None


@app.post("/v1/invoices", response_model=InvoiceSchema)
async def create_draft_invoice(
    req: CreateInvoiceRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Creates a new draft invoice (BIL-108).
    """
    mgr = InvoiceManager(session)
    return await mgr.create_draft_invoice(
        invoice_id=req.invoice_id,
        tenant_id=req.tenant_id,
        customer_id=req.customer_id,
        period_id=req.period_id,
        due_days=req.due_days
    )


@app.post("/v1/invoices/{invoice_id}/items", response_model=InvoiceLineItemSchema)
async def add_invoice_item(
    invoice_id: str,
    req: AddLineItemRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Adds a line item to a draft invoice (BIL-108).
    """
    mgr = InvoiceManager(session)
    try:
        return await mgr.add_line_item(
            invoice_id=invoice_id,
            description=req.description,
            quantity=req.quantity,
            unit_price_cents=req.unit_price_cents,
            event_type=req.event_type
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/v1/invoices/{invoice_id}/finalize", response_model=InvoiceSchema)
async def finalize_invoice(
    invoice_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Finalizes an invoice, locking line items and assigning sequential number (BIL-108).
    """
    mgr = InvoiceManager(session)
    try:
        return await mgr.finalize_invoice(invoice_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.get("/v1/invoices/{invoice_id}", response_model=InvoiceSchema)
async def get_invoice_details(
    invoice_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Retrieves full invoice details including line items and totals (BIL-108).
    """
    mgr = InvoiceManager(session)
    inv = await mgr.get_invoice(invoice_id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return inv


@app.get("/v1/invoices", response_model=List[InvoiceSchema])
async def list_invoices(
    tenant_id: str = Query(...),
    customer_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db)
):
    """
    Lists invoices for a tenant with optional filtering by customer and status (BIL-145).
    """
    from invoicing.manager import InvoiceRecord
    stmt = select(InvoiceRecord).where(InvoiceRecord.tenant_id == tenant_id)
    if customer_id:
        stmt = stmt.where(InvoiceRecord.customer_id == customer_id)
    if status:
        stmt = stmt.where(InvoiceRecord.status == status)
    stmt = stmt.order_by(InvoiceRecord.created_at.desc())

    res = await session.execute(stmt)
    mgr = InvoiceManager(session)
    records = res.scalars().all()
    invoices = []
    for r in records:
        full_inv = await mgr.get_invoice(r.id)
        if full_inv:
            invoices.append(full_inv)
    return invoices


@app.get("/v1/dashboard/summary")
async def get_dashboard_summary(
    tenant_id: str = Query(...),
    session: AsyncSession = Depends(get_db)
):
    """
    Returns aggregated KPI summary for the Billing Dashboard (BIL-139).
    """
    from reporting.metrics import FinancialMetricsReporter
    from invoicing.manager import InvoiceRecord, InvoiceStatus
    reporter = FinancialMetricsReporter(session)
    rev_metrics = await reporter.compute_revenue_metrics(tenant_id)
    mrr_metrics = await reporter.compute_mrr_metrics(tenant_id)

    # Unpaid invoices count and amount
    stmt = select(
        func.count(InvoiceRecord.id),
        func.coalesce(func.sum(InvoiceRecord.total_cents), 0)
    ).where(
        InvoiceRecord.tenant_id == tenant_id,
        InvoiceRecord.status == InvoiceStatus.FINALIZED.value
    )
    res = await session.execute(stmt)
    unpaid_count, unpaid_amount = res.one()

    return {
        "tenant_id": tenant_id,
        "gross_revenue_cents": rev_metrics.gross_revenue_cents,
        "net_revenue_cents": rev_metrics.net_revenue_cents,
        "mrr_cents": mrr_metrics.total_mrr_cents,
        "arr_cents": mrr_metrics.arr_cents,
        "active_subscriptions": mrr_metrics.active_subscriptions_count,
        "unpaid_invoices_count": int(unpaid_count),
        "unpaid_amount_cents": int(unpaid_amount)
    }


# ============================================================================
# BIL-104: Meter API
# ============================================================================

from models.meters import MeterManager, MeterSchema, MeterAggregationType

class CreateMeterRequest(BaseModel):
    meter_id: str
    tenant_id: str
    name: str
    event_type: str
    aggregation_type: MeterAggregationType = MeterAggregationType.SUM
    unit: str = "units"


@app.post("/v1/meters", response_model=MeterSchema)
async def create_meter(
    req: CreateMeterRequest,
    session: AsyncSession = Depends(get_db)
):
    mgr = MeterManager(session)
    return await mgr.create_meter(
        meter_id=req.meter_id,
        tenant_id=req.tenant_id,
        name=req.name,
        event_type=req.event_type,
        aggregation_type=req.aggregation_type,
        unit=req.unit
    )


@app.get("/v1/meters/{meter_id}", response_model=MeterSchema)
async def get_meter(
    meter_id: str,
    tenant_id: str = Query(...),
    session: AsyncSession = Depends(get_db)
):
    mgr = MeterManager(session)
    meter = await mgr.get_meter(tenant_id, meter_id)
    if not meter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meter not found")
    return meter


@app.get("/v1/meters", response_model=List[MeterSchema])
async def list_meters(
    tenant_id: str = Query(...),
    session: AsyncSession = Depends(get_db)
):
    mgr = MeterManager(session)
    return await mgr.list_meters(tenant_id)


# ============================================================================
# BIL-106: Rating API
# ============================================================================

from rating.engine import RatingEngine, PriceBookManager, PriceBookEntry, RatingLineItem, PricingType, PriceTier

class CalculateRateRequest(BaseModel):
    entry: PriceBookEntry
    quantity: int


@app.post("/v1/rating/calculate", response_model=RatingLineItem)
async def calculate_rate(req: CalculateRateRequest):
    try:
        return RatingEngine.rate_usage(req.entry, req.quantity)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/v1/rating/price-books", response_model=PriceBookEntry)
async def add_price_book_entry(
    entry: PriceBookEntry,
    session: AsyncSession = Depends(get_db)
):
    mgr = PriceBookManager(session)
    return await mgr.add_entry(
        entry_id=entry.id,
        tenant_id=entry.tenant_id,
        plan_id=entry.plan_id,
        event_type=entry.event_type,
        pricing_type=entry.pricing_type,
        flat_fee_cents=entry.flat_fee_cents,
        free_units=entry.free_units,
        unit_price_cents=entry.unit_price_cents,
        min_charge_cents=entry.min_charge_cents,
        max_charge_cents=entry.max_charge_cents,
        included_units=entry.included_units,
        overage_unit_price_cents=entry.overage_unit_price_cents,
        tiers=entry.tiers
    )


@app.get("/v1/rating/price-books", response_model=List[PriceBookEntry])
async def get_price_books(
    tenant_id: str = Query(...),
    plan_id: str = Query(...),
    session: AsyncSession = Depends(get_db)
):
    mgr = PriceBookManager(session)
    return await mgr.get_entries_for_plan(tenant_id, plan_id)


# ============================================================================
# BIL-107: Usage Query API
# ============================================================================

from aggregation.periods import UsageAggregator

@app.get("/v1/usage/query")
async def query_aggregated_usage(
    tenant_id: str = Query(...),
    customer_id: str = Query(...),
    event_type: str = Query(...),
    start_date: str = Query(...),
    end_date: str = Query(...),
    session: AsyncSession = Depends(get_db)
):
    aggregator = UsageAggregator(session)
    dt_start = datetime.fromisoformat(start_date.replace(" ", "+"))
    dt_end = datetime.fromisoformat(end_date.replace(" ", "+"))
    total_qty = await aggregator.recompute_from_scratch(
        tenant_id=tenant_id,
        customer_id=customer_id,
        event_type=event_type,
        start_date=dt_start,
        end_date=dt_end
    )
    return {
        "tenant_id": tenant_id,
        "customer_id": customer_id,
        "event_type": event_type,
        "start_date": dt_start.isoformat(),
        "end_date": dt_end.isoformat(),
        "total_quantity": total_qty
    }


# ============================================================================
# BIL-109: Payment API
# ============================================================================

from payments.collections import PaymentCollectionsManager

class AuthorizePaymentRequest(BaseModel):
    payment_id: str
    tenant_id: str
    customer_id: str
    invoice_id: str
    amount_cents: int
    idempotency_key: Optional[str] = None


class CapturePaymentRequest(BaseModel):
    amount_cents: Optional[int] = None


@app.post("/v1/payments/authorize")
async def authorize_payment_endpoint(
    req: AuthorizePaymentRequest,
    session: AsyncSession = Depends(get_db)
):
    mgr = PaymentCollectionsManager(session)
    try:
        rec = await mgr.authorize_payment(
            payment_id=req.payment_id,
            tenant_id=req.tenant_id,
            customer_id=req.customer_id,
            invoice_id=req.invoice_id,
            amount_cents=req.amount_cents,
            idempotency_key=req.idempotency_key
        )
        return {
            "payment_id": rec.id,
            "status": rec.status,
            "amount_cents": rec.amount_cents,
            "gateway_ref": rec.gateway_ref
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/v1/payments/{payment_id}/capture")
async def capture_payment_endpoint(
    payment_id: str,
    req: CapturePaymentRequest,
    session: AsyncSession = Depends(get_db)
):
    mgr = PaymentCollectionsManager(session)
    try:
        rec = await mgr.capture_payment(payment_id, req.amount_cents)
        return {
            "payment_id": rec.id,
            "status": rec.status,
            "amount_cents": rec.amount_cents
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================================================
# BIL-110: Subscription API
# ============================================================================

from models.accounts import SubscriptionLifecycleManager

class CreateSubscriptionRequest(BaseModel):
    subscription_id: str
    tenant_id: str
    customer_id: str
    plan_id: str
    current_period_start: datetime
    current_period_end: datetime


class UpgradeSubscriptionRequest(BaseModel):
    new_plan_id: str
    new_plan_rate_cents: int
    old_plan_rate_cents: int
    as_of: datetime


@app.post("/v1/subscriptions")
async def create_subscription(
    req: CreateSubscriptionRequest,
    session: AsyncSession = Depends(get_db)
):
    mgr = SubscriptionLifecycleManager(session)
    sub = await mgr.create_subscription(
        subscription_id=req.subscription_id,
        tenant_id=req.tenant_id,
        customer_id=req.customer_id,
        plan_id=req.plan_id,
        current_period_start=req.current_period_start,
        current_period_end=req.current_period_end
    )
    return sub.model_dump()


@app.get("/v1/subscriptions/{subscription_id}")
async def get_subscription(
    subscription_id: str,
    session: AsyncSession = Depends(get_db)
):
    mgr = SubscriptionLifecycleManager(session)
    sub = await mgr.get_subscription(subscription_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return sub.model_dump()


@app.post("/v1/subscriptions/{subscription_id}/upgrade")
async def upgrade_subscription(
    subscription_id: str,
    req: UpgradeSubscriptionRequest,
    session: AsyncSession = Depends(get_db)
):
    mgr = SubscriptionLifecycleManager(session)
    sub, proration = await mgr.upgrade_subscription(
        subscription_id=subscription_id,
        new_plan_id=req.new_plan_id,
        new_plan_price_cents=req.new_plan_rate_cents,
        old_plan_price_cents=req.old_plan_rate_cents,
        effective_time=req.as_of
    )
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return {
        "subscription": sub.model_dump(),
        "proration": proration.to_dict()
    }

