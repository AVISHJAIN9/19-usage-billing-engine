"""
Reporting and Financial Metrics Engine (BIL-115, BIL-117).
Computes:
- Real-time Revenue metrics: Gross revenue, net revenue, discounts, taxes (BIL-115).
- Monthly Recurring Revenue (MRR) and Annual Recurring Revenue (ARR) (BIL-117).
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict

from invoicing.manager import InvoiceRecord, InvoiceStatus
from payments.manager import PaymentRecord, PaymentStatus
from models.accounts import SubscriptionRecordV2, SubscriptionStatus


class RevenueMetricsSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: str
    gross_revenue_cents: int
    net_revenue_cents: int
    total_discounts_cents: int
    total_tax_cents: int
    total_invoiced_cents: int
    paid_invoice_count: int
    currency: str = "USD"


class MRRMetricsSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: str
    total_mrr_cents: int
    arr_cents: int
    active_subscriptions_count: int
    arpu_cents: int  # Average Revenue Per User in cents


class FinancialMetricsReporter:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def compute_revenue_metrics(
        self,
        tenant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        currency: str = "USD"
    ) -> RevenueMetricsSchema:
        """
        BIL-115: Computes real-time gross/net revenue, discounts, taxes from settled invoices & payments.
        """
        stmt = (
            select(
                func.coalesce(func.sum(InvoiceRecord.subtotal_cents), 0),
                func.coalesce(func.sum(InvoiceRecord.discount_cents), 0),
                func.coalesce(func.sum(InvoiceRecord.tax_cents), 0),
                func.coalesce(func.sum(InvoiceRecord.total_cents), 0),
                func.count(InvoiceRecord.id)
            )
            .where(
                InvoiceRecord.tenant_id == tenant_id,
                InvoiceRecord.status == InvoiceStatus.PAID.value
            )
        )
        if start_date:
            stmt = stmt.where(InvoiceRecord.created_at >= start_date)
        if end_date:
            stmt = stmt.where(InvoiceRecord.created_at <= end_date)

        res = await self.session.execute(stmt)
        subtotal, discounts, tax, total, count = res.one()

        gross_rev = int(subtotal + tax)
        net_rev = int(total)

        return RevenueMetricsSchema(
            tenant_id=tenant_id,
            gross_revenue_cents=gross_rev,
            net_revenue_cents=net_rev,
            total_discounts_cents=int(discounts),
            total_tax_cents=int(tax),
            total_invoiced_cents=int(total),
            paid_invoice_count=int(count),
            currency=currency
        )

    async def compute_mrr_metrics(
        self,
        tenant_id: str,
        plan_monthly_rates_cents: Optional[Dict[str, int]] = None
    ) -> MRRMetricsSchema:
        """
        BIL-117: Calculates total MRR, ARR, and active subscription metrics.
        """
        rates = plan_monthly_rates_cents or {}
        default_rate = 5000  # $50.00 default if not in rates mapping

        stmt = (
            select(SubscriptionRecordV2)
            .where(
                SubscriptionRecordV2.tenant_id == tenant_id,
                SubscriptionRecordV2.status == SubscriptionStatus.ACTIVE.value
            )
        )
        res = await self.session.execute(stmt)
        active_subs = res.scalars().all()

        total_mrr = 0
        for sub in active_subs:
            monthly_price = rates.get(sub.plan_id, default_rate)
            total_mrr += monthly_price

        count = len(active_subs)
        arr = total_mrr * 12
        arpu = (total_mrr // count) if count > 0 else 0

        return MRRMetricsSchema(
            tenant_id=tenant_id,
            total_mrr_cents=total_mrr,
            arr_cents=arr,
            active_subscriptions_count=count,
            arpu_cents=arpu
        )
