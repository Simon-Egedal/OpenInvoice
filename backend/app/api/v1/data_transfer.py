from typing import Literal
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import current_membership, current_user, write_membership
from app.db.session import get_db
from app.models.entities import Invoice, InvoicePayment, InvoiceTransactionMatch, BankTransaction
from app.providers.accounting import CSVAccountingProvider
from app.data_transfer import import_records

router = APIRouter()


@router.get("/exports/{kind}.csv")
async def export_csv(kind: Literal["invoices", "payments"], m=Depends(current_membership), db: AsyncSession=Depends(get_db)):
    provider = CSVAccountingProvider()
    columns = ["invoice_number", "invoice_type", "status", "issue_date", "due_date", "currency", "subtotal", "tax_amount", "total", "paid_amount", "due_amount"] if kind == "invoices" else ["invoice_number", "currency", "amount", "payment_date", "payment_method", "reference", "notes"]
    if kind == "invoices":
        result = await db.execute(select(Invoice).where(Invoice.organization_id == m.organization_id).order_by(Invoice.created_at))
        rows = [{name: (getattr(invoice, name).value if hasattr(getattr(invoice, name), "value") else getattr(invoice, name)) for name in columns} for invoice in result.scalars().all()]
    else:
        result = await db.execute(select(InvoicePayment, Invoice).join(Invoice, Invoice.id == InvoicePayment.invoice_id).where(InvoicePayment.organization_id == m.organization_id, Invoice.organization_id == m.organization_id).order_by(InvoicePayment.payment_date))
        rows = [{"invoice_number": invoice.invoice_number, "currency": invoice.currency, **{name: getattr(payment, name) for name in columns[2:]}} for payment, invoice in result.all()]
        allocations = await db.execute(select(InvoiceTransactionMatch, Invoice, BankTransaction).join(Invoice, Invoice.id == InvoiceTransactionMatch.invoice_id).join(BankTransaction, BankTransaction.id == InvoiceTransactionMatch.transaction_id).where(InvoiceTransactionMatch.organization_id == m.organization_id, Invoice.organization_id == m.organization_id, BankTransaction.organization_id == m.organization_id, InvoiceTransactionMatch.confirmed == True).order_by(BankTransaction.booked_at))
        rows += [{"invoice_number": invoice.invoice_number, "currency": invoice.currency, "amount": match.amount, "payment_date": transaction.booked_at.date(), "payment_method": "bank", "reference": transaction.reference or str(transaction.id), "notes": transaction.description} for match, invoice, transaction in allocations.all()]
    return Response(await provider.export_rows(rows, columns), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{kind}.csv"'})


@router.get("/imports/{kind}/template.csv")
async def import_template(kind: Literal["customers", "products"], m=Depends(write_membership)):
    columns = ["name", "email", "phone", "address", "postal_code", "city", "country", "vat_number", "payment_information", "notes"] if kind == "customers" else ["name", "unit_price"]
    return Response(await CSVAccountingProvider().export_rows([], columns), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{kind}-template.csv"'})


@router.post("/imports/{kind}", status_code=201)
async def import_csv(kind: Literal["customers", "products"], document: UploadFile=File(), user=Depends(current_user), m=Depends(write_membership), db: AsyncSession=Depends(get_db)):
    content = await document.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(413, "CSV must be 2 MB or smaller")
    return await import_records(db, m.organization_id, user.id, kind, content)
