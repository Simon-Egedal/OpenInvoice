from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO
from uuid import UUID
import asyncio
import smtplib
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import delete, select, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import current_membership, current_user, hash_password, verify_password, write_membership
from app.core.config import settings
from app.core.runtime_config import config_path, read_saved_settings, save_settings, settings_are_applied
from app.db.session import get_db
from app.models.entities import AuditLog, BankAccount, Customer, EmailDelivery, Invoice, InvoiceDocument, InvoiceLine, InvoiceStatus, InvoiceType, Organization, OrganizationMember, Supplier, User
from app.providers.banking import EnableBankingProvider, MockBankingProvider
from app.providers.email import email_provider
from app.providers.storage import storage_provider
from app.schemas import CustomerIn, CustomerOut, InvoiceIn, InvoiceLineOut, InvoiceOut, LoginIn, OrganizationOut, RegisterIn, SetupIn, SupplierIn, SupplierOut, UserOut
from app.services import create_invoice, money

router=APIRouter()
setup_lock=asyncio.Lock()

@router.get("/setup/status")
async def setup_status():
    saved=read_saved_settings()
    configured=bool(saved and saved.get("setup_completed"))
    applied=settings_are_applied(settings,saved)
    return {"complete":configured,"applied":applied,"database_mode":saved.get("database_mode") if saved else None}

async def verify_database(url: str) -> None:
    engine=create_async_engine(url,connect_args={"timeout":8})
    try:
        async with engine.connect() as connection: await connection.execute(text("SELECT 1"))
    finally:
        await engine.dispose()

def verify_smtp(values: SetupIn) -> None:
    if not values.smtp_host or not values.smtp_from:
        raise ValueError("SMTP host and from address are required")
    with smtplib.SMTP(values.smtp_host,values.smtp_port,timeout=8) as server:
        if values.smtp_use_tls: server.starttls()
        if values.smtp_username: server.login(values.smtp_username,values.smtp_password)

def verify_s3(values: SetupIn) -> None:
    if not all((values.s3_bucket,values.s3_access_key_id,values.s3_secret_access_key)):
        raise ValueError("S3 bucket, access key, and secret key are required")
    import boto3
    client=boto3.client("s3",endpoint_url=values.s3_endpoint_url or None,aws_access_key_id=values.s3_access_key_id,aws_secret_access_key=values.s3_secret_access_key,region_name=values.s3_region)
    client.head_bucket(Bucket=values.s3_bucket)

@router.post("/setup/configure",status_code=200)
async def configure_installation(payload:SetupIn):
    async with setup_lock:
        if config_path().exists(): raise HTTPException(409,"OpenInvoice is already configured")
        if payload.database_mode=="external":
            database_url=URL.create("postgresql+asyncpg",username=payload.database_username,password=payload.database_password,host=payload.database_host,port=payload.database_port,database=payload.database_name)
            if payload.database_ssl: database_url=database_url.update_query_dict({"ssl":"require"})
            url=database_url.render_as_string(hide_password=False)
        else:
            url=settings.database_url
        try: await verify_database(url)
        except Exception as exc: raise HTTPException(422,"Could not connect to PostgreSQL. Check the host, database, credentials, and network access.") from exc
        if payload.email_provider=="smtp":
            try: await asyncio.to_thread(verify_smtp,payload)
            except Exception as exc: raise HTTPException(422,"Could not connect to SMTP. Check the server, TLS setting, and credentials.") from exc
        if payload.storage_provider=="s3":
            try: await asyncio.to_thread(verify_s3,payload)
            except Exception as exc: raise HTTPException(422,"Could not access the S3 bucket. Check its endpoint, region, name, and credentials.") from exc
        values=payload.model_dump(exclude={"database_host","database_port","database_name","database_username","database_password","database_ssl"})
        values.update({"database_url":url,"setup_completed":True,"local_storage_path":settings.local_storage_path})
        if payload.storage_provider=="local":
            from pathlib import Path
            import tempfile
            try:
                Path(settings.local_storage_path).mkdir(parents=True,exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=settings.local_storage_path): pass
            except OSError as exc: raise HTTPException(422,"The local storage directory is not writable") from exc
        save_settings(values)
        return {"status":"saved","restart_required":True,"message":"Configuration saved securely. Restart the API so it can run migrations with these settings."}

@router.post("/auth/register",response_model=UserOut,status_code=201)
async def register(payload:RegisterIn,request:Request,db:AsyncSession=Depends(get_db)):
    saved=read_saved_settings()
    if not saved or not saved.get("setup_completed"): raise HTTPException(409,"Complete installation setup before creating an account")
    if not settings_are_applied(settings,saved): raise HTTPException(409,"Restart the API to apply configuration before creating an account")
    if await db.scalar(select(User).where(User.email==payload.email.lower())): raise HTTPException(409,"Email already registered")
    user=User(email=payload.email.lower(),password_hash=hash_password(payload.password),full_name=payload.full_name)
    org=Organization(name=payload.organization_name)
    db.add_all([user,org]); await db.flush(); db.add(OrganizationMember(user_id=user.id,organization_id=org.id,role="owner")); await db.commit(); await db.refresh(user); request.session["user_id"]=str(user.id)
    return user
@router.post("/auth/login",response_model=UserOut)
async def login(payload:LoginIn,request:Request,db:AsyncSession=Depends(get_db)):
    user=await db.scalar(select(User).where(User.email==payload.email.lower()))
    if not user or not verify_password(payload.password,user.password_hash): raise HTTPException(401,"Invalid email or password")
    request.session["user_id"]=str(user.id); return user
@router.post("/auth/logout",status_code=204)
async def logout(request:Request): request.session.clear(); return Response(status_code=204)
@router.get("/auth/me",response_model=UserOut)
async def me(user:User=Depends(current_user)): return user
@router.get("/organizations",response_model=list[OrganizationOut])
async def organizations(user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    rows=await db.execute(select(Organization).join(OrganizationMember).where(OrganizationMember.user_id==user.id)); return rows.scalars().all()
@router.post("/organizations",response_model=OrganizationOut,status_code=201)
async def create_organization(payload:dict, user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
    name=str(payload.get("name","")).strip()
    if not name: raise HTTPException(422,"Organization name is required")
    org=Organization(name=name,country=payload.get("country","DK"),currency=payload.get("currency","DKK")); db.add(org); await db.flush(); db.add(OrganizationMember(user_id=user.id,organization_id=org.id,role="owner")); await db.commit(); await db.refresh(org); return org

async def entity_list(model, db, org_id):
    result=await db.execute(select(model).where(model.organization_id==org_id).order_by(model.name)); return result.scalars().all()
@router.get("/customers",response_model=list[CustomerOut])
async def customers(m=Depends(current_membership),db:AsyncSession=Depends(get_db)): return await entity_list(Customer,db,m.organization_id)
@router.post("/customers",response_model=CustomerOut,status_code=201)
async def add_customer(payload:CustomerIn,user=Depends(current_user),m=Depends(write_membership),db:AsyncSession=Depends(get_db)):
    item=Customer(**payload.model_dump(),organization_id=m.organization_id); db.add(item); await db.flush(); db.add(AuditLog(organization_id=m.organization_id,user_id=user.id,action="customer.created",entity_type="customer",entity_id=item.id,new_values={"name":item.name})); await db.commit(); await db.refresh(item); return item
@router.get("/customers/{item_id}",response_model=CustomerOut)
async def get_customer(item_id:UUID,m=Depends(current_membership),db:AsyncSession=Depends(get_db)):
    item=await db.scalar(select(Customer).where(Customer.id==item_id,Customer.organization_id==m.organization_id));
    if not item: raise HTTPException(404,"Customer not found")
    return item
@router.patch("/customers/{item_id}",response_model=CustomerOut)
async def update_customer(item_id:UUID,payload:CustomerIn,m=Depends(write_membership),db:AsyncSession=Depends(get_db)):
    item=await db.scalar(select(Customer).where(Customer.id==item_id,Customer.organization_id==m.organization_id));
    if not item: raise HTTPException(404,"Customer not found")
    for key,value in payload.model_dump().items(): setattr(item,key,value)
    await db.commit(); await db.refresh(item); return item
@router.get("/suppliers",response_model=list[SupplierOut])
async def suppliers(m=Depends(current_membership),db:AsyncSession=Depends(get_db)): return await entity_list(Supplier,db,m.organization_id)
@router.post("/suppliers",response_model=SupplierOut,status_code=201)
async def add_supplier(payload:SupplierIn,user=Depends(current_user),m=Depends(write_membership),db:AsyncSession=Depends(get_db)):
    item=Supplier(**payload.model_dump(),organization_id=m.organization_id); db.add(item); await db.flush(); db.add(AuditLog(organization_id=m.organization_id,user_id=user.id,action="supplier.created",entity_type="supplier",entity_id=item.id,new_values={"name":item.name})); await db.commit(); await db.refresh(item); return item
@router.get("/suppliers/{item_id}",response_model=SupplierOut)
async def get_supplier(item_id:UUID,m=Depends(current_membership),db:AsyncSession=Depends(get_db)):
    item=await db.scalar(select(Supplier).where(Supplier.id==item_id,Supplier.organization_id==m.organization_id));
    if not item: raise HTTPException(404,"Supplier not found")
    return item
@router.patch("/suppliers/{item_id}",response_model=SupplierOut)
async def update_supplier(item_id:UUID,payload:SupplierIn,m=Depends(write_membership),db:AsyncSession=Depends(get_db)):
    item=await db.scalar(select(Supplier).where(Supplier.id==item_id,Supplier.organization_id==m.organization_id));
    if not item: raise HTTPException(404,"Supplier not found")
    for key,value in payload.model_dump().items(): setattr(item,key,value)
    await db.commit(); await db.refresh(item); return item

@router.get("/invoices",response_model=list[InvoiceOut])
async def invoices(m=Depends(current_membership),db:AsyncSession=Depends(get_db)):
    result=await db.execute(select(Invoice).where(Invoice.organization_id==m.organization_id).order_by(Invoice.created_at.desc())); return result.scalars().all()
@router.post("/invoices",response_model=InvoiceOut,status_code=201)
async def add_invoice(payload:InvoiceIn,user=Depends(current_user),m=Depends(write_membership),db:AsyncSession=Depends(get_db)):
    if payload.invoice_type.value=="outgoing":
        if not payload.customer_id or not await db.scalar(select(Customer.id).where(Customer.id==payload.customer_id,Customer.organization_id==m.organization_id)): raise HTTPException(422,"Choose a customer from this organization")
    if payload.invoice_type.value=="incoming":
        if not payload.supplier_id or not await db.scalar(select(Supplier.id).where(Supplier.id==payload.supplier_id,Supplier.organization_id==m.organization_id)): raise HTTPException(422,"Choose a supplier from this organization")
    return await create_invoice(db,payload,m.organization_id,user.id)
@router.post("/invoices/receive",response_model=InvoiceOut,status_code=201)
async def receive_invoice(user=Depends(current_user),m=Depends(write_membership),db:AsyncSession=Depends(get_db),invoice_number:str=Form(min_length=1,max_length=100),supplier_id:UUID=Form(),issue_date:date=Form(),due_date:date=Form(),description:str=Form(min_length=1,max_length=500),net_amount:Decimal=Form(gt=0),tax_rate:Decimal=Form(ge=0,le=100),currency:str=Form(default="DKK"),document:UploadFile=File()):
    if not await db.scalar(select(Supplier.id).where(Supplier.id==supplier_id,Supplier.organization_id==m.organization_id)): raise HTTPException(422,"Choose a supplier from this organization")
    if document.content_type!="application/pdf": raise HTTPException(415,"Only PDF invoices are accepted")
    content=await document.read(20*1024*1024+1)
    if len(content)>20*1024*1024: raise HTTPException(413,"Invoice PDF must be 20 MB or smaller")
    if not content.startswith(b"%PDF-"): raise HTTPException(415,"Uploaded file is not a valid PDF")
    if due_date<issue_date: raise HTTPException(422,"Due date must not be before issue date")
    safe_name=(document.filename or "invoice.pdf").replace("\\","/").split("/")[-1][:255] or "invoice.pdf"
    key=await storage_provider().put(content,safe_name,"application/pdf")
    amount=money(net_amount); tax=money(amount*tax_rate/Decimal("100"))
    invoice=Invoice(organization_id=m.organization_id,created_by=user.id,invoice_number=invoice_number,invoice_type=InvoiceType.incoming,status=InvoiceStatus.received,supplier_id=supplier_id,issue_date=issue_date,due_date=due_date,currency=currency.upper(),subtotal=amount,tax_amount=tax,total=money(amount+tax))
    db.add(invoice); await db.flush(); db.add(InvoiceLine(invoice_id=invoice.id,description=description,quantity=Decimal("1"),unit_price=amount,tax_rate=tax_rate,line_total=amount)); db.add(InvoiceDocument(organization_id=m.organization_id,invoice_id=invoice.id,storage_key=key,original_filename=safe_name,content_type="application/pdf",size_bytes=len(content))); db.add(AuditLog(organization_id=m.organization_id,user_id=user.id,action="invoice.received",entity_type="invoice",entity_id=invoice.id,new_values={"invoice_number":invoice_number,"document_name":safe_name})); await db.commit(); await db.refresh(invoice); return invoice
@router.patch("/invoices/{invoice_id}",response_model=InvoiceOut)
async def update_draft_invoice(invoice_id:UUID,payload:InvoiceIn,user=Depends(current_user),m=Depends(write_membership),db:AsyncSession=Depends(get_db)):
    invoice=await db.scalar(select(Invoice).where(Invoice.id==invoice_id,Invoice.organization_id==m.organization_id))
    if not invoice: raise HTTPException(404,"Invoice not found")
    if invoice.status!=InvoiceStatus.draft: raise HTTPException(409,"Only draft invoices can be edited")
    if payload.invoice_type.value=="outgoing":
        if not payload.customer_id or not await db.scalar(select(Customer.id).where(Customer.id==payload.customer_id,Customer.organization_id==m.organization_id)): raise HTTPException(422,"Choose a customer from this organization")
    if payload.invoice_type.value=="incoming":
        if not payload.supplier_id or not await db.scalar(select(Supplier.id).where(Supplier.id==payload.supplier_id,Supplier.organization_id==m.organization_id)): raise HTTPException(422,"Choose a supplier from this organization")
    subtotal=Decimal("0"); tax=Decimal("0"); prepared=[]
    for line in payload.lines:
        amount=money(line.quantity*line.unit_price); subtotal+=amount; tax+=money(amount*line.tax_rate/Decimal("100")); prepared.append((line,amount))
    for key in ("invoice_number","invoice_type","customer_id","supplier_id","issue_date","due_date","currency","notes"): setattr(invoice,key,getattr(payload,key))
    invoice.currency=invoice.currency.upper(); invoice.subtotal=money(subtotal); invoice.tax_amount=money(tax); invoice.total=money(subtotal+tax)
    await db.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id==invoice.id))
    for line,amount in prepared: db.add(InvoiceLine(invoice_id=invoice.id,description=line.description,quantity=line.quantity,unit_price=line.unit_price,tax_rate=line.tax_rate,line_total=amount))
    db.add(AuditLog(organization_id=m.organization_id,user_id=user.id,action="invoice.updated",entity_type="invoice",entity_id=invoice.id,new_values={"invoice_number":invoice.invoice_number,"total":str(invoice.total)}))
    await db.commit(); await db.refresh(invoice); return invoice
@router.get("/invoices/{invoice_id}",response_model=InvoiceOut)
async def get_invoice(invoice_id:UUID,m=Depends(current_membership),db:AsyncSession=Depends(get_db)):
    invoice=await db.scalar(select(Invoice).where(Invoice.id==invoice_id,Invoice.organization_id==m.organization_id));
    if not invoice: raise HTTPException(404,"Invoice not found")
    return invoice
@router.get("/invoices/{invoice_id}/lines",response_model=list[InvoiceLineOut])
async def invoice_lines(invoice_id:UUID,m=Depends(current_membership),db:AsyncSession=Depends(get_db)):
    if not await db.scalar(select(Invoice.id).where(Invoice.id==invoice_id,Invoice.organization_id==m.organization_id)): raise HTTPException(404,"Invoice not found")
    result=await db.execute(select(InvoiceLine).where(InvoiceLine.invoice_id==invoice_id)); return result.scalars().all()
def make_pdf(invoice,lines):
    out=BytesIO(); doc=canvas.Canvas(out,pagesize=A4); width,height=A4; y=height-60
    doc.setFillColorRGB(.1,.12,.14); doc.setFont("Helvetica-Bold",22); doc.drawString(48,y,"INVOICE"); y-=35
    doc.setFont("Helvetica-Bold",13); doc.drawString(48,y,invoice.invoice_number); y-=24
    doc.setFont("Helvetica",10); doc.drawString(48,y,f"Issue date  {invoice.issue_date}     Due date  {invoice.due_date}"); y-=42
    doc.setFont("Helvetica-Bold",10); doc.drawString(48,y,"DESCRIPTION"); doc.drawRightString(width-160,y,"QTY"); doc.drawRightString(width-90,y,"PRICE"); doc.drawRightString(width-48,y,"TOTAL"); y-=10; doc.line(48,y,width-48,y); y-=20
    doc.setFont("Helvetica",10)
    for line in lines:
        doc.drawString(48,y,line.description[:70]); doc.drawRightString(width-160,y,str(line.quantity)); doc.drawRightString(width-90,y,f"{line.unit_price:.2f}"); doc.drawRightString(width-48,y,f"{line.line_total:.2f}"); y-=22
    y-=10; doc.line(width-220,y,width-48,y); y-=22
    for label,value in (("Subtotal",invoice.subtotal),("VAT",invoice.tax_amount),("Total",invoice.total)):
        doc.setFont("Helvetica-Bold" if label=="Total" else "Helvetica",11 if label=="Total" else 10); doc.drawString(width-220,y,label); doc.drawRightString(width-48,y,f"{invoice.currency} {value:.2f}"); y-=22
    if invoice.notes: y-=15; doc.setFont("Helvetica",9); doc.drawString(48,y,"Notes: "+invoice.notes[:100])
    doc.save(); return out.getvalue()
@router.get("/invoices/{invoice_id}/pdf")
async def invoice_pdf(invoice_id:UUID,m=Depends(current_membership),db:AsyncSession=Depends(get_db)):
    invoice=await db.scalar(select(Invoice).where(Invoice.id==invoice_id,Invoice.organization_id==m.organization_id));
    if not invoice: raise HTTPException(404,"Invoice not found")
    result=await db.execute(select(InvoiceLine).where(InvoiceLine.invoice_id==invoice_id)); return StreamingResponse(BytesIO(make_pdf(invoice,result.scalars().all())),media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="{invoice.invoice_number}.pdf"'})
@router.post("/invoices/{invoice_id}/send",status_code=202)
async def send_invoice(invoice_id:UUID,user=Depends(current_user),m=Depends(current_membership),db:AsyncSession=Depends(get_db)):
    invoice=await db.scalar(select(Invoice).where(Invoice.id==invoice_id,Invoice.organization_id==m.organization_id))
    if not invoice: raise HTTPException(404,"Invoice not found")
    if not invoice.customer_id: raise HTTPException(422,"Invoice has no customer")
    customer=await db.scalar(select(Customer).where(Customer.id==invoice.customer_id,Customer.organization_id==m.organization_id))
    if not customer or not customer.email: raise HTTPException(422,"Customer has no email address")
    rows=await db.execute(select(InvoiceLine).where(InvoiceLine.invoice_id==invoice.id)); pdf=make_pdf(invoice,rows.scalars().all())
    delivery=EmailDelivery(organization_id=m.organization_id,invoice_id=invoice.id,recipient=customer.email,status="sending"); db.add(delivery); await db.flush()
    try:
        delivery.provider_message_id=await email_provider().send_invoice(customer.email,f"Invoice {invoice.invoice_number}",f"Please find invoice {invoice.invoice_number} attached.",pdf,f"{invoice.invoice_number}.pdf"); delivery.status="sent"; delivery.sent_at=datetime.now(timezone.utc); invoice.status=InvoiceStatus.sent
        db.add(AuditLog(organization_id=m.organization_id,user_id=user.id,action="invoice.sent",entity_type="invoice",entity_id=invoice.id,new_values={"recipient":customer.email}))
    except Exception as exc:
        delivery.status="failed"; delivery.failed_attempts+=1; delivery.error_message=str(exc)[:500]
        await db.commit(); raise HTTPException(502,"Email delivery failed") from exc
    await db.commit(); return {"status":delivery.status,"recipient":delivery.recipient}

@router.get("/banking/accounts")
async def bank_accounts(m=Depends(current_membership),db:AsyncSession=Depends(get_db)):
    result=await db.execute(select(BankAccount).where(BankAccount.organization_id==m.organization_id)); saved=result.scalars().all()
    if saved: return saved
    if settings.banking_provider=="enable_banking": return []
    provider=MockBankingProvider(); account=(await provider.get_accounts("demo"))[0]; balance=(await provider.get_balances(account["id"]))[0]
    return [{**account,"balance":balance["amount"],"last_synced_at":datetime.now(timezone.utc)}]
@router.get("/banking/transactions")
async def bank_transactions(m=Depends(current_membership)):
    if settings.banking_provider=="enable_banking": return []
    return await MockBankingProvider().get_transactions("mock-account-1")
@router.post("/banking/connections/authorize")
async def bank_authorize(m=Depends(current_membership)):
    provider=EnableBankingProvider() if settings.banking_provider=="enable_banking" else MockBankingProvider()
    try: return {"authorization_url":await provider.create_authorization(settings.frontend_url+"/banking/callback")}
    except NotImplementedError as exc: raise HTTPException(501,str(exc)) from exc
@router.get("/audit")
async def audit(m=Depends(current_membership),db:AsyncSession=Depends(get_db)):
    result=await db.execute(select(AuditLog).where(AuditLog.organization_id==m.organization_id).order_by(AuditLog.created_at.desc()).limit(100)); return result.scalars().all()
