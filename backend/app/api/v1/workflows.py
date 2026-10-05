from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import current_membership, current_user, write_membership
from app.db.session import get_db
from app.approvals import decide_invoice
from app.deliveries import queue_invoice
from app.models.entities import AuditLog, EmailDelivery, Invoice, InvoiceDecision

router = APIRouter()


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(pending_approval|approved|rejected)$")
    reason: str | None = Field(default=None, max_length=2000)


async def require_invoice(db, organization_id, invoice_id):
    if not await db.scalar(select(Invoice.id).where(Invoice.id == invoice_id, Invoice.organization_id == organization_id)):
        raise HTTPException(404, "Invoice not found")


@router.post("/invoices/{invoice_id}/approval")
async def approval(invoice_id: UUID, payload: DecisionIn, user=Depends(current_user), m=Depends(current_membership), db: AsyncSession=Depends(get_db)):
    invoice = await decide_invoice(db, m, invoice_id, user.id, payload.decision, payload.reason)
    return {"status": invoice.status}


@router.get("/invoices/{invoice_id}/decisions")
async def decisions(invoice_id: UUID, m=Depends(current_membership), db: AsyncSession=Depends(get_db)):
    await require_invoice(db, m.organization_id, invoice_id)
    rows = await db.execute(select(InvoiceDecision).where(InvoiceDecision.invoice_id == invoice_id, InvoiceDecision.organization_id == m.organization_id).order_by(InvoiceDecision.created_at))
    return [{"id": str(row.id), "decision": row.decision, "reason": row.reason, "user_id": str(row.user_id), "created_at": row.created_at} for row in rows.scalars().all()]


@router.post("/invoices/{invoice_id}/reminders", status_code=202)
async def reminder(invoice_id: UUID, user=Depends(current_user), m=Depends(write_membership), db: AsyncSession=Depends(get_db), idempotency_key: str = Header(default="initial", max_length=80)):
    return await queue_invoice(db, m.organization_id, invoice_id, user.id, idempotency_key, reminder=True)


@router.get("/invoices/{invoice_id}/deliveries")
async def deliveries(invoice_id: UUID, m=Depends(current_membership), db: AsyncSession=Depends(get_db)):
    await require_invoice(db, m.organization_id, invoice_id)
    rows = await db.execute(select(EmailDelivery).where(EmailDelivery.invoice_id == invoice_id, EmailDelivery.organization_id == m.organization_id).order_by(EmailDelivery.created_at.desc()).limit(100))
    return [{"id": str(row.id), "kind": row.kind, "status": row.status, "recipient": row.recipient, "failed_attempts": row.failed_attempts, "error_message": row.error_message, "created_at": row.created_at, "sent_at": row.sent_at} for row in rows.scalars().all()]


@router.post("/invoices/{invoice_id}/deliveries/{delivery_id}/retry", status_code=202)
async def retry_delivery(invoice_id: UUID, delivery_id: UUID, user=Depends(current_user), m=Depends(write_membership), db: AsyncSession=Depends(get_db)):
    row = await db.scalar(select(EmailDelivery).where(EmailDelivery.id == delivery_id, EmailDelivery.invoice_id == invoice_id, EmailDelivery.organization_id == m.organization_id).with_for_update())
    if not row:
        raise HTTPException(404, "Delivery not found")
    if row.status not in {"failed", "uncertain"} or not row.encrypted_payload:
        raise HTTPException(409, "This delivery cannot be retried")
    row.status = "queued"
    row.failed_attempts = 0
    row.next_attempt_at = datetime.now(timezone.utc)
    row.error_message = None
    db.add(AuditLog(organization_id=m.organization_id, user_id=user.id, action="email.retry_requested", entity_type="email_delivery", entity_id=row.id))
    await db.commit()
    return {"status": row.status}
