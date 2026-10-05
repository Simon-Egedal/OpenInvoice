"""Preserve issuer and recipient details when an invoice is issued."""
from datetime import datetime, timezone
from sqlalchemy import select
from fastapi import HTTPException
from app.models.entities import AuditLog, Customer, Supplier, Invoice, InvoiceLine, InvoiceStatus, InvoiceType, Organization
from app.invoice_pdf import make_pdf
from app.providers.storage import storage_provider


PARTY_FIELDS = ("name", "address", "postal_code", "city", "country", "vat_number", "email", "phone", "payment_information")


async def invoice_content(db, invoice):
    rows = await db.execute(select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id, InvoiceLine.organization_id == invoice.organization_id).order_by(InvoiceLine.position, InvoiceLine.id))
    lines = rows.scalars().all()
    if invoice.issued_snapshot:
        org = invoice.issued_snapshot["organization"]
        recipient = invoice.issued_snapshot["recipient"]
    else:
        org = await db.scalar(select(Organization).where(Organization.id == invoice.organization_id))
        model = Customer if invoice.invoice_type == InvoiceType.outgoing else Supplier
        recipient_id = invoice.customer_id if invoice.invoice_type == InvoiceType.outgoing else invoice.supplier_id
        recipient = await db.scalar(select(model).where(model.id == recipient_id, model.organization_id == invoice.organization_id))
    logo_key = org.get("logo_key") if isinstance(org, dict) else getattr(org, "logo_key", None)
    logo_bytes = await storage_provider().get(logo_key) if logo_key else None
    return make_pdf(invoice, lines, org=org, recipient=recipient, logo_bytes=logo_bytes)


async def issue_invoice(db, organization_id, invoice_id, user_id):
    await db.scalar(select(Organization.id).where(Organization.id == organization_id).with_for_update(key_share=True))
    invoice = await db.scalar(select(Invoice).where(Invoice.id == invoice_id, Invoice.organization_id == organization_id).with_for_update())
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if invoice.invoice_type != InvoiceType.outgoing or invoice.status in {InvoiceStatus.cancelled, InvoiceStatus.rejected, InvoiceStatus.pending_approval}:
        raise HTTPException(409, "This invoice cannot be issued")
    if invoice.issued_pdf_key:
        return invoice
    org = await db.scalar(select(Organization).where(Organization.id == organization_id))
    customer = await db.scalar(select(Customer).where(Customer.id == invoice.customer_id, Customer.organization_id == organization_id))
    if not org or not customer:
        raise HTTPException(422, "Invoice requires an organization and customer")
    invoice.issued_snapshot = {
        "organization": {name: getattr(org, name, None) for name in (*PARTY_FIELDS, "payment_terms", "logo_key")},
        "recipient": {name: getattr(customer, name, None) for name in PARTY_FIELDS},
    }
    content = await invoice_content(db, invoice)
    invoice.issued_pdf_key = await storage_provider().put(content, f"{invoice.invoice_number}.pdf", "application/pdf")
    invoice.issued_at = datetime.now(timezone.utc)
    if invoice.status == InvoiceStatus.draft:
        invoice.status = InvoiceStatus.issued
    db.add(AuditLog(organization_id=organization_id, user_id=user_id, action="invoice.issued", entity_type="invoice", entity_id=invoice.id, new_values={"invoice_number": invoice.invoice_number}))
    await db.flush()
    return invoice
