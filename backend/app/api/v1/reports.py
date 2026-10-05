from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import current_membership
from app.db.session import get_db
from app.models.entities import Invoice, InvoiceStatus

router = APIRouter()


@router.get("/reports/aging")
async def aging_report(m=Depends(current_membership), db: AsyncSession=Depends(get_db)):
    rows = await db.execute(select(Invoice).where(Invoice.organization_id == m.organization_id, Invoice.status.notin_([InvoiceStatus.draft, InvoiceStatus.cancelled, InvoiceStatus.rejected, InvoiceStatus.pending_approval])))
    groups = {}
    today = datetime.now(timezone.utc).date()
    for invoice in rows.scalars().all():
        key = (invoice.invoice_type.value if hasattr(invoice.invoice_type, "value") else invoice.invoice_type, invoice.currency)
        group = groups.setdefault(key, {"invoice_type": key[0], "currency": key[1], **{name: Decimal("0.00") for name in ("outstanding", "overdue", "paid", "current", "days_1_30", "days_31_60", "days_61_90", "days_91_plus")}})
        group["paid"] += invoice.paid_amount or Decimal("0.00")
        due = invoice.due_amount
        group["outstanding"] += due
        days = (today - invoice.due_date).days
        bucket = "current" if days <= 0 else "days_1_30" if days <= 30 else "days_31_60" if days <= 60 else "days_61_90" if days <= 90 else "days_91_plus"
        group[bucket] += due
        if days > 0:
            group["overdue"] += due
    return [{name: str(value) if isinstance(value, Decimal) else value for name, value in group.items()} for _, group in sorted(groups.items())]
