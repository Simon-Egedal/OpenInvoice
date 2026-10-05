from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import hash_password
from app.core.runtime_config import settings_are_applied
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

def get_infrastructure_config(saved: dict | None, runtime_settings: Any) -> dict:
    saved = saved or {}
    db_mode = saved.get("database_mode", "bundled")
    restart_required = not settings_are_applied(runtime_settings, saved) if saved.get("setup_completed") else False

    return {
        "can_manage": True,
        "database_mode": db_mode,
        "database_host": saved.get("database_host", runtime_settings.postgres_host or "localhost"),
        "database_port": int(saved.get("database_port", 5432)),
        "database_name": saved.get("database_name", runtime_settings.postgres_db or "openinvoice"),
        "database_username": saved.get("database_username", runtime_settings.postgres_user or "openinvoice"),
        "database_ssl": bool(saved.get("database_ssl", False)),
        "has_database_password": bool(saved.get("database_password") or runtime_settings.postgres_password),
        "email_provider": saved.get("email_provider", runtime_settings.email_provider or "console"),
        "smtp_host": saved.get("smtp_host", runtime_settings.smtp_host or ""),
        "smtp_port": int(saved.get("smtp_port", runtime_settings.smtp_port or 587)),
        "smtp_username": saved.get("smtp_username", runtime_settings.smtp_username or ""),
        "smtp_from": saved.get("smtp_from", runtime_settings.smtp_from or "OpenInvoice <invoices@example.com>"),
        "smtp_use_tls": bool(saved.get("smtp_use_tls", runtime_settings.smtp_use_tls)),
        "has_smtp_password": bool(saved.get("smtp_password") or runtime_settings.smtp_password),
        "storage_provider": saved.get("storage_provider", runtime_settings.storage_provider or "local"),
        "s3_endpoint_url": saved.get("s3_endpoint_url", runtime_settings.s3_endpoint_url or ""),
        "s3_bucket": saved.get("s3_bucket", runtime_settings.s3_bucket or ""),
        "s3_access_key_id": saved.get("s3_access_key_id", runtime_settings.s3_access_key_id or ""),
        "s3_region": saved.get("s3_region", runtime_settings.s3_region or "eu-central-1"),
        "has_s3_secret": bool(saved.get("s3_secret_access_key") or runtime_settings.s3_secret_access_key),
        "banking_provider": saved.get("banking_provider", runtime_settings.banking_provider or "mock"),
        "enable_banking_app_id": saved.get("enable_banking_app_id", runtime_settings.enable_banking_app_id or ""),
        "enable_banking_private_key_path": saved.get("enable_banking_private_key_path", runtime_settings.enable_banking_private_key_path or ""),
        "session_cookie_secure": bool(saved.get("session_cookie_secure", runtime_settings.session_cookie_secure)),
        "restart_required": restart_required,
    }

def prepare_infrastructure_update(
    payload: Any,
    saved: dict | None,
    runtime_settings: Any,
) -> tuple[dict, str]:
    saved = saved or {}
    db_password = payload.database_password or saved.get("database_password") or runtime_settings.postgres_password or ""
    smtp_password = payload.smtp_password or saved.get("smtp_password") or runtime_settings.smtp_password or ""
    s3_secret = payload.s3_secret_access_key or saved.get("s3_secret_access_key") or runtime_settings.s3_secret_access_key or ""

    if payload.database_mode == "external":
        database_url = URL.create(
            "postgresql+asyncpg",
            username=payload.database_username,
            password=db_password,
            host=payload.database_host,
            port=payload.database_port,
            database=payload.database_name,
        )
        if payload.database_ssl:
            database_url = database_url.update_query_dict({"ssl": "require"})
        url = database_url.render_as_string(hide_password=False)
    else:
        url = runtime_settings.database_url

    values = {
        "setup_completed": True,
        "database_mode": payload.database_mode,
        "database_host": payload.database_host,
        "database_port": payload.database_port,
        "database_name": payload.database_name,
        "database_username": payload.database_username,
        "database_password": db_password,
        "database_ssl": payload.database_ssl,
        "database_url": url,
        "email_provider": payload.email_provider,
        "smtp_host": payload.smtp_host,
        "smtp_port": payload.smtp_port,
        "smtp_username": payload.smtp_username,
        "smtp_password": smtp_password,
        "smtp_from": payload.smtp_from,
        "smtp_use_tls": payload.smtp_use_tls,
        "storage_provider": payload.storage_provider,
        "s3_endpoint_url": payload.s3_endpoint_url,
        "s3_bucket": payload.s3_bucket,
        "s3_access_key_id": payload.s3_access_key_id,
        "s3_secret_access_key": s3_secret,
        "s3_region": payload.s3_region,
        "banking_provider": payload.banking_provider,
        "enable_banking_app_id": payload.enable_banking_app_id,
        "enable_banking_private_key_path": payload.enable_banking_private_key_path,
        "session_cookie_secure": payload.session_cookie_secure,
        "local_storage_path": runtime_settings.local_storage_path,
    }
    return values, url



