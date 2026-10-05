from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from app.models.entities import AuditLog, Invoice, InvoiceDocument, InvoiceLine, InvoiceStatus, InvoiceType, Organization, Supplier
from app.providers.storage import storage_provider
from app.services import money, reserve_invoice_number


async def receive_supplier_invoice(db, organization_id, user_id, *, invoice_number, supplier_id, issue_date, due_date, description, net_amount, tax_rate, currency, document):
    if not await db.scalar(select(Supplier.id).where(Supplier.id == supplier_id, Supplier.organization_id == organization_id)):
        raise HTTPException(422, "Choose a supplier from this organization")
    org = await db.scalar(select(Organization).where(Organization.id == organization_id).with_for_update(key_share=True))
    invoice_number = await reserve_invoice_number(db, org, InvoiceType.incoming, supplier_id, invoice_number)
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        raise HTTPException(422, "Currency must be a three-letter code")
    if document.content_type != "application/pdf":
        raise HTTPException(415, "Only PDF invoices are accepted")
    content = await document.read(20 * 1024 * 1024 + 1)
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(413, "Invoice PDF must be 20 MB or smaller")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(415, "Uploaded file is not a PDF")
    if due_date < issue_date:
        raise HTTPException(422, "Due date must not be before issue date")
    amount = money(net_amount)
    tax = money(amount * tax_rate / Decimal("100"))
    if amount + tax >= Decimal("1000000000000"):
        raise HTTPException(422, "Invoice total exceeds supported amount")
    filename = (document.filename or "invoice.pdf").replace("\\", "/").split("/")[-1][:255] or "invoice.pdf"
    provider = storage_provider()
    key = None
    try:
        invoice = Invoice(organization_id=organization_id, created_by=user_id, invoice_number=invoice_number, invoice_type=InvoiceType.incoming, status=InvoiceStatus.received, supplier_id=supplier_id, issue_date=issue_date, due_date=due_date, currency=currency.upper(), subtotal=amount, tax_amount=tax, total=money(amount + tax))
        db.add(invoice); await db.flush()
        key = await provider.put(content, filename, "application/pdf")
        db.add(InvoiceLine(organization_id=organization_id, invoice_id=invoice.id, description=description, quantity=Decimal("1"), unit_price=amount, tax_rate=tax_rate, line_total=amount))
        db.add(InvoiceDocument(organization_id=organization_id, invoice_id=invoice.id, storage_key=key, original_filename=filename, content_type="application/pdf", size_bytes=len(content)))
        db.add(AuditLog(organization_id=organization_id, user_id=user_id, action="invoice.received", entity_type="invoice", entity_id=invoice.id, new_values={"invoice_number": invoice_number, "document_name": filename}))
        await db.commit()
    except Exception:
        await db.rollback()
        if key:
            try:
                await provider.delete(key)
            except Exception:
                import logging
                logging.getLogger(__name__).warning("Unable to clean up uncommitted document object")
        raise
    await db.refresh(invoice)
    return invoice
