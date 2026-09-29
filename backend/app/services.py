from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import AuditLog, Invoice, InvoiceLine

CENT=Decimal("0.01")
def money(value: Decimal)->Decimal: return value.quantize(CENT,rounding=ROUND_HALF_UP)

async def create_invoice(db: AsyncSession, data, organization_id, user_id)->Invoice:
    subtotal=Decimal("0"); tax=Decimal("0"); prepared=[]
    for line in data.lines:
        amount=money(line.quantity*line.unit_price)
        line_tax=money(amount*line.tax_rate/Decimal("100"))
        subtotal+=amount; tax+=line_tax; prepared.append((line,amount))
    invoice=Invoice(organization_id=organization_id,created_by=user_id,invoice_number=data.invoice_number,invoice_type=data.invoice_type,status="draft",customer_id=data.customer_id,supplier_id=data.supplier_id,issue_date=data.issue_date,due_date=data.due_date,currency=data.currency.upper(),subtotal=money(subtotal),tax_amount=money(tax),total=money(subtotal+tax),notes=data.notes)
    db.add(invoice); await db.flush()
    for line,amount in prepared: db.add(InvoiceLine(invoice_id=invoice.id,description=line.description,quantity=line.quantity,unit_price=line.unit_price,tax_rate=line.tax_rate,line_total=amount))
    db.add(AuditLog(organization_id=organization_id,user_id=user_id,action="invoice.created",entity_type="invoice",entity_id=invoice.id,new_values={"invoice_number":invoice.invoice_number,"total":str(invoice.total)}))
    await db.commit(); await db.refresh(invoice)
    return invoice

