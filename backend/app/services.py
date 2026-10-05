from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import hash_password
from app.models.entities import AuditLog, Invoice, InvoiceLine, MemberRole, Organization, OrganizationMember, User
from app.providers.storage import storage_provider

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

async def create_initial_organization(
    db: AsyncSession,
    name: str,
    country: str = "DK",
    currency: str = "DKK",
    logo_bytes: bytes | None = None,
    logo_filename: str | None = None,
    content_type: str | None = None,
) -> Organization:
    existing_user = await db.scalar(select(User).limit(1))
    if existing_user:
        raise ValueError("Setup has already been completed")

    logo_key = None
    if logo_bytes:
        safe_name = (logo_filename or "logo.png").replace("\\", "/").split("/")[-1][:255] or "logo.png"
        logo_key = await storage_provider().put(logo_bytes, safe_name, content_type or "image/png")

    existing_org = await db.scalar(select(Organization).order_by(Organization.created_at.asc()))
    if existing_org:
        existing_org.name = name.strip()
        existing_org.country = country.upper().strip()
        existing_org.currency = currency.upper().strip()
        if logo_key:
            existing_org.logo_key = logo_key
        await db.commit()
        await db.refresh(existing_org)
        return existing_org

    org = Organization(
        name=name.strip(),
        country=country.upper().strip(),
        currency=currency.upper().strip(),
        logo_key=logo_key,
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org

async def create_initial_admin(
    db: AsyncSession,
    full_name: str,
    email: str,
    password: str,
    organization_id: UUID | None = None,
) -> tuple[User, Organization]:
    existing_user = await db.scalar(select(User).limit(1))
    if existing_user:
        raise ValueError("An administrator account already exists")

    if organization_id:
        org = await db.scalar(select(Organization).where(Organization.id == organization_id))
    else:
        org = await db.scalar(select(Organization).order_by(Organization.created_at.asc()))

    if not org:
        raise ValueError("Please set up an organization before creating an admin account")

    normalized_email = email.strip().lower()
    existing_email = await db.scalar(select(User).where(User.email == normalized_email))
    if existing_email:
        raise ValueError("Email already registered")

    user = User(
        email=normalized_email,
        password_hash=hash_password(password),
        full_name=full_name.strip(),
    )
    db.add(user)
    await db.flush()
    db.add(OrganizationMember(user_id=user.id, organization_id=org.id, role=MemberRole.owner))
    db.add(AuditLog(
        organization_id=org.id,
        user_id=user.id,
        action="admin.created",
        entity_type="user",
        entity_id=user.id,
        new_values={"email": user.email, "role": "owner"}
    ))
    await db.commit()
    await db.refresh(user)
    return user, org


