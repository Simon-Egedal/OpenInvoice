from fastapi import HTTPException
from sqlalchemy import select
from app.models.entities import AuditLog, Invoice, InvoiceDecision, InvoiceStatus, InvoiceType, Organization


async def decide_invoice(db, membership, invoice_id, user_id, decision, reason=None):
    roles = {"owner", "admin", "approver"} if decision in {"approved", "rejected"} else {"owner", "admin", "accountant", "member"}
    if membership.role not in roles:
        raise HTTPException(403, "Your role cannot perform this approval action")
    await db.scalar(select(Organization.id).where(Organization.id == membership.organization_id).with_for_update(key_share=True))
    invoice = await db.scalar(select(Invoice).where(Invoice.id == invoice_id, Invoice.organization_id == membership.organization_id).with_for_update())
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if invoice.invoice_type != InvoiceType.incoming:
        raise HTTPException(409, "Approval applies to incoming invoices")
    allowed = {InvoiceStatus.received, InvoiceStatus.rejected} if decision == "pending_approval" else {InvoiceStatus.pending_approval}
    if invoice.status not in allowed:
        raise HTTPException(409, "Invoice is not in the expected approval state")
    if decision == "rejected" and not (reason and reason.strip()):
        raise HTTPException(422, "A rejection reason is required")
    invoice.status = InvoiceStatus(decision)
    db.add(InvoiceDecision(organization_id=membership.organization_id, invoice_id=invoice.id, user_id=user_id, decision=decision, reason=reason.strip() if reason else None))
    db.add(AuditLog(organization_id=membership.organization_id, user_id=user_id, action=f"invoice.{decision}", entity_type="invoice", entity_id=invoice.id, new_values={"reason": reason}))
    await db.commit()
    return invoice
