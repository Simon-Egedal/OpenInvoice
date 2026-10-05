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
from app.auth import admin_membership, current_membership, current_user, hash_password, verify_password, write_membership
from app.core.config import settings
from app.core.runtime_config import config_path, read_saved_settings, save_settings, settings_are_applied
from app.db.session import get_db
from app.models.entities import AuditLog, BankAccount, BankConnection, BankTransaction, Customer, EmailDelivery, Invoice, InvoiceDocument, InvoiceLine, InvoiceStatus, InvoiceType, Organization, OrganizationMember, Supplier, User
from app.providers.banking import EnableBankingProvider, MockBankingProvider
from app.providers.email import email_provider
from app.providers.storage import storage_provider
from app.schemas import BankAuthorizeIn, BankCallbackIn, CustomerIn, CustomerOut, InfrastructureSettingsIn, InfrastructureSettingsOut, InvoiceIn, InvoiceLineOut, InvoiceOut, LoginIn, OrganizationOut, RegisterIn, SetupAdminIn, SetupIn, SetupOrgOut, SupplierIn, SupplierOut, UserOut
from app.services import create_initial_admin, create_initial_organization, create_invoice, get_infrastructure_config, money, prepare_infrastructure_update

router=APIRouter()
setup_lock=asyncio.Lock()

@router.get("/setup/status")
async def setup_status():
    saved=read_saved_settings()
    configured=bool(saved and saved.get("setup_completed"))
    applied=settings_are_applied(settings,saved)
    has_organization = False
    has_admin = False
    org_id = None
    org_name = None
    if applied:
        try:
            from app.db.session import SessionLocal
            async with SessionLocal() as db:
                org = await db.scalar(select(Organization).order_by(Organization.created_at.asc()))
                if org:
                    has_organization = True
                    org_id = str(org.id)
                    org_name = org.name
                user = await db.scalar(select(User).limit(1))
                if user:
                    has_admin = True
        except Exception:
            pass
    return {
        "complete": configured,
        "applied": applied,
        "database_mode": saved.get("database_mode") if saved else None,
        "has_organization": has_organization,
        "has_admin": has_admin,
        "organization_id": org_id,
        "organization_name": org_name,
    }

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
        values=payload.model_dump()
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

@router.post("/setup/organization")
async def setup_organization(
    name: str = Form(min_length=1, max_length=200),
    country: str = Form(default="DK"),
    currency: str = Form(default="DKK"),
    logo: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    saved = read_saved_settings()
    if not saved or not saved.get("setup_completed"):
        raise HTTPException(409, "Complete installation setup first")
    if not settings_are_applied(settings, saved):
        raise HTTPException(409, "Restart the API to apply configuration before setting up an organization")

    logo_bytes = None
    logo_filename = None
    content_type = None
    if logo and logo.filename:
        logo_bytes = await logo.read(5 * 1024 * 1024 + 1)
        if len(logo_bytes) > 5 * 1024 * 1024:
            raise HTTPException(413, "Logo image must be 5 MB or smaller")
        content_type = logo.content_type or "image/png"
        if not (content_type.startswith("image/") or logo.filename.lower().endswith((".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif"))):
            raise HTTPException(415, "Only image files (PNG, JPG, SVG, WebP) are accepted for the organization logo")
        logo_filename = logo.filename

    try:
        org = await create_initial_organization(
            db=db,
            name=name,
            country=country,
            currency=currency,
            logo_bytes=logo_bytes,
            logo_filename=logo_filename,
            content_type=content_type,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

    return {
        "id": str(org.id),
        "name": org.name,
        "country": org.country,
        "currency": org.currency,
        "logo_key": org.logo_key,
        "logo_url": f"/organizations/{org.id}/logo" if org.logo_key else None,
    }

@router.get("/setup/organization")
async def get_setup_organization(db: AsyncSession = Depends(get_db)):
    org = await db.scalar(select(Organization).order_by(Organization.created_at.asc()))
    if not org:
        raise HTTPException(404, "No organization has been set up yet")
    return {
        "id": str(org.id),
        "name": org.name,
        "country": org.country,
        "currency": org.currency,
        "logo_key": org.logo_key,
        "logo_url": f"/organizations/{org.id}/logo" if org.logo_key else None,
    }

@router.post("/setup/admin", response_model=UserOut, status_code=201)
async def setup_admin(
    payload: SetupAdminIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    saved = read_saved_settings()
    if not saved or not saved.get("setup_completed"):
        raise HTTPException(409, "Complete installation setup first")
    if not settings_are_applied(settings, saved):
        raise HTTPException(409, "Restart the API to apply configuration before creating an admin account")

    try:
        user, org = await create_initial_admin(
            db=db,
            full_name=payload.full_name,
            email=payload.email,
            password=payload.password,
            organization_id=payload.organization_id,
        )
    except ValueError as exc:
        msg = str(exc)
        if "already exists" in msg or "already registered" in msg:
            raise HTTPException(409, msg) from exc
        raise HTTPException(422, msg) from exc

    request.session["user_id"] = str(user.id)
    return user

@router.get("/organizations/{org_id}/logo")
async def organization_logo(org_id: UUID, db: AsyncSession = Depends(get_db)):
    org = await db.scalar(select(Organization).where(Organization.id == org_id))
    if not org or not org.logo_key:
        raise HTTPException(404, "Logo not found")
    try:
        content = await storage_provider().get(org.logo_key)
    except Exception as exc:
        raise HTTPException(404, "Logo not found") from exc

    media_type = "image/png"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        media_type = "image/png"
    elif content.startswith(b"\xff\xd8\xff"):
        media_type = "image/jpeg"
    elif content.startswith(b"<svg") or b"<svg" in content[:200]:
        media_type = "image/svg+xml"
    elif content.startswith(b"RIFF") and b"WEBP" in content[:12]:
        media_type = "image/webp"
    elif content.startswith(b"GIF87a") or content.startswith(b"GIF89a"):
        media_type = "image/gif"
    return Response(content=content, media_type=media_type)

@router.post("/auth/register",response_model=UserOut,status_code=201)
async def register(payload:RegisterIn,request:Request,db:AsyncSession=Depends(get_db)):
    existing_user = await db.scalar(select(User).limit(1))
    if existing_user:
        raise HTTPException(403, "Public registration is disabled. Please contact your organization administrator.")
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
@router.get("/banking/aspsps")
async def get_banking_aspsps(
    country: str | None = None,
    m: OrganizationMember = Depends(current_membership),
    db: AsyncSession = Depends(get_db),
):
    provider = EnableBankingProvider() if settings.banking_provider == "enable_banking" else MockBankingProvider()
    if not country:
        org = await db.scalar(select(Organization).where(Organization.id == m.organization_id))
        country = org.country if org and org.country else "DK"
    try:
        banks = await provider.get_aspsps(country)
        return {"country": country, "banks": banks}
    except Exception as exc:
        raise HTTPException(502, f"Failed to retrieve banks from provider: {exc}") from exc

@router.get("/banking/accounts")
async def bank_accounts(m: OrganizationMember = Depends(current_membership), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BankAccount)
        .where(BankAccount.organization_id == m.organization_id)
        .order_by(BankAccount.created_at.asc())
    )
    saved = result.scalars().all()
    if saved:
        return [
            {
                "id": str(a.id),
                "name": a.name,
                "bank": a.bank_name,
                "masked_number": a.masked_number,
                "currency": a.currency,
                "balance": str(a.balance),
                "last_synced_at": a.last_synced_at.isoformat() if a.last_synced_at else None,
            }
            for a in saved
        ]
    if settings.banking_provider == "enable_banking":
        return []
    provider = MockBankingProvider()
    account = (await provider.get_accounts("demo"))[0]
    balance = (await provider.get_balances(account["id"]))[0]
    return [{**account, "balance": str(balance["amount"]), "last_synced_at": datetime.now(timezone.utc).isoformat()}]

@router.get("/banking/transactions")
async def bank_transactions(m: OrganizationMember = Depends(current_membership), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BankTransaction)
        .where(BankTransaction.organization_id == m.organization_id)
        .order_by(BankTransaction.booked_at.desc())
        .limit(100)
    )
    saved = result.scalars().all()
    if saved:
        return [
            {
                "id": str(t.id),
                "booked_at": t.booked_at.isoformat(),
                "description": t.description,
                "counterparty": t.counterparty or "",
                "amount": str(t.amount),
                "currency": t.currency,
                "reference": t.reference,
            }
            for t in saved
        ]
    if settings.banking_provider == "enable_banking":
        return []
    return await MockBankingProvider().get_transactions("mock-account-1")

@router.post("/banking/connections/authorize")
async def bank_authorize(
    payload: BankAuthorizeIn | None = None,
    m: OrganizationMember = Depends(current_membership),
    db: AsyncSession = Depends(get_db),
):
    provider = EnableBankingProvider() if settings.banking_provider == "enable_banking" else MockBankingProvider()
    aspsp_name = payload.aspsp_name if payload else None
    aspsp_country = payload.aspsp_country if payload else None
    if not aspsp_country:
        org = await db.scalar(select(Organization).where(Organization.id == m.organization_id))
        aspsp_country = org.country if org and org.country else "DK"
    try:
        url = await provider.create_authorization(
            callback_url=settings.frontend_url + "/banking/callback",
            aspsp_name=aspsp_name,
            aspsp_country=aspsp_country,
        )
        return {"authorization_url": url}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Failed to initiate bank authorization: {exc}") from exc

@router.post("/banking/connections/callback")
async def bank_callback(
    payload: BankCallbackIn,
    user: User = Depends(current_user),
    m: OrganizationMember = Depends(current_membership),
    db: AsyncSession = Depends(get_db),
):
    provider = EnableBankingProvider() if settings.banking_provider == "enable_banking" else MockBankingProvider()
    try:
        session_data = await provider.handle_callback(payload.code)
    except Exception as exc:
        raise HTTPException(422, f"Failed to authorize bank session: {exc}") from exc

    session_id = session_data.get("session_id") or payload.code
    aspsp_info = session_data.get("aspsp") or {}
    bank_name = aspsp_info.get("name") or "Connected Bank"

    conn = BankConnection(
        organization_id=m.organization_id,
        provider=settings.banking_provider,
        provider_reference=session_id,
        status="connected",
        last_synced_at=datetime.now(timezone.utc),
    )
    db.add(conn)
    await db.flush()

    raw_accounts = session_data.get("accounts", [])
    if not raw_accounts:
        try:
            raw_accounts = await provider.get_accounts(session_id)
        except Exception:
            raw_accounts = []

    connected_accounts = []
    for acc in raw_accounts:
        uid = str(acc.get("uid") or acc.get("id") or uuid4())
        acc_dict = acc.get("account_id") or {}
        iban = acc_dict.get("iban") or acc.get("masked_number") or ""
        masked = f"•••• {iban[-4:]}" if len(iban) >= 4 else (acc.get("masked_number") or "•••• 0000")
        name = acc.get("name") or acc.get("details") or "Business Account"

        try:
            balances = await provider.get_balances(uid)
            balance = balances[0]["amount"] if balances else Decimal("0.00")
            curr = balances[0]["currency"] if balances else (acc.get("currency") or "DKK")
        except Exception:
            balance = Decimal("0.00")
            curr = acc.get("currency") or "DKK"

        bank_acc = BankAccount(
            organization_id=m.organization_id,
            connection_id=conn.id,
            provider_account_id=uid,
            name=name[:150],
            bank_name=bank_name[:150],
            masked_number=masked[:40],
            currency=curr[:3].upper(),
            balance=balance,
            last_synced_at=datetime.now(timezone.utc),
        )
        db.add(bank_acc)
        await db.flush()
        connected_accounts.append(bank_acc)

        try:
            txs = await provider.get_transactions(uid)
            for t in txs:
                db.add(BankTransaction(
                    organization_id=m.organization_id,
                    account_id=bank_acc.id,
                    provider_transaction_id=str(t["id"])[:200],
                    booked_at=t["booked_at"],
                    description=str(t["description"])[:300],
                    counterparty=str(t["counterparty"])[:200] if t.get("counterparty") else None,
                    amount=t["amount"],
                    currency=str(t["currency"])[:3].upper(),
                    reference=str(t["reference"])[:200] if t.get("reference") else None,
                ))
        except Exception:
            pass

    db.add(AuditLog(
        organization_id=m.organization_id,
        user_id=user.id,
        action="bank.connected",
        entity_type="bank_connection",
        entity_id=conn.id,
        new_values={"provider": settings.banking_provider, "accounts_count": len(connected_accounts)},
    ))
    await db.commit()

    return {
        "status": "connected",
        "accounts_count": len(connected_accounts),
        "accounts": [
            {
                "id": str(a.id),
                "name": a.name,
                "bank": a.bank_name,
                "masked_number": a.masked_number,
                "currency": a.currency,
                "balance": str(a.balance),
            }
            for a in connected_accounts
        ],
    }

@router.post("/banking/sync")
async def bank_sync(m: OrganizationMember = Depends(current_membership), db: AsyncSession = Depends(get_db)):
    provider = EnableBankingProvider() if settings.banking_provider == "enable_banking" else MockBankingProvider()
    result = await db.execute(select(BankAccount).where(BankAccount.organization_id == m.organization_id))
    accounts = result.scalars().all()
    now = datetime.now(timezone.utc)
    synced_tx_count = 0
    for a in accounts:
        try:
            balances = await provider.get_balances(a.provider_account_id)
            if balances:
                a.balance = balances[0]["amount"]
            a.last_synced_at = now
            txs = await provider.get_transactions(a.provider_account_id)
            for t in txs:
                exists = await db.scalar(
                    select(BankTransaction)
                    .where(BankTransaction.account_id == a.id)
                    .where(BankTransaction.provider_transaction_id == str(t["id"]))
                )
                if not exists:
                    db.add(BankTransaction(
                        organization_id=m.organization_id,
                        account_id=a.id,
                        provider_transaction_id=str(t["id"])[:200],
                        booked_at=t["booked_at"],
                        description=str(t["description"])[:300],
                        counterparty=str(t["counterparty"])[:200] if t.get("counterparty") else None,
                        amount=t["amount"],
                        currency=str(t["currency"])[:3].upper(),
                        reference=str(t["reference"])[:200] if t.get("reference") else None,
                    ))
                    synced_tx_count += 1
        except Exception:
            pass
    await db.commit()
    return {"status": "synced", "new_transactions": synced_tx_count}

@router.get("/audit")
async def audit(m=Depends(current_membership),db:AsyncSession=Depends(get_db)):
    result=await db.execute(select(AuditLog).where(AuditLog.organization_id==m.organization_id).order_by(AuditLog.created_at.desc()).limit(100)); return result.scalars().all()

@router.get("/settings/infrastructure", response_model=InfrastructureSettingsOut)
async def get_settings_infrastructure(
    m: OrganizationMember = Depends(admin_membership),
):
    saved = read_saved_settings()
    return get_infrastructure_config(saved, settings)

@router.put("/settings/infrastructure", response_model=InfrastructureSettingsOut)
async def update_settings_infrastructure(
    payload: InfrastructureSettingsIn,
    user: User = Depends(current_user),
    m: OrganizationMember = Depends(admin_membership),
    db: AsyncSession = Depends(get_db),
):
    saved = read_saved_settings()
    values, url = prepare_infrastructure_update(payload, saved, settings)

    try:
        await verify_database(url)
    except Exception as exc:
        raise HTTPException(422, "Could not connect to PostgreSQL. Check the host, database, credentials, and network access.") from exc

    if payload.email_provider == "smtp":
        try:
            temp_setup = SetupIn(**{**payload.model_dump(), "smtp_password": values["smtp_password"]})
            await asyncio.to_thread(verify_smtp, temp_setup)
        except Exception as exc:
            raise HTTPException(422, "Could not connect to SMTP. Check the server, TLS setting, and credentials.") from exc

    if payload.storage_provider == "s3":
        try:
            temp_setup = SetupIn(**{**payload.model_dump(), "s3_secret_access_key": values["s3_secret_access_key"]})
            await asyncio.to_thread(verify_s3, temp_setup)
        except Exception as exc:
            raise HTTPException(422, "Could not access the S3 bucket. Check its endpoint, region, name, and credentials.") from exc

    if payload.storage_provider == "local":
        from pathlib import Path
        import tempfile
        try:
            Path(settings.local_storage_path).mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=settings.local_storage_path):
                pass
        except OSError as exc:
            raise HTTPException(422, "The local storage directory is not writable") from exc

    save_settings(values)
    db.add(AuditLog(
        organization_id=m.organization_id,
        user_id=user.id,
        action="infrastructure.updated",
        entity_type="system",
        entity_id=m.organization_id,
        new_values={
            "database_mode": payload.database_mode,
            "banking_provider": payload.banking_provider,
            "email_provider": payload.email_provider,
            "storage_provider": payload.storage_provider,
        }
    ))
    await db.commit()

    return get_infrastructure_config(values, settings)

