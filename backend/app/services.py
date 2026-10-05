from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID
import secrets
import logging
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, select
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import hash_password, verify_password
from app.providers.email import EmailProvider
from app.core.runtime_config import settings_are_applied
from app.models.entities import (
    AuditLog,
    BankAccount,
    BankTransaction,
    Invoice,
    InvoiceLine,
    InvoicePayment,
    InvoiceStatus,
    InvoiceTransactionMatch,
    InvoiceType,
    MemberRole,
    Organization,
    OrganizationMember,
    User,
)
from app.providers.storage import storage_provider

CENT=Decimal("0.01")

async def create_member_account(db: AsyncSession, payload, membership, actor: User, provider: EmailProvider):
    email = str(payload.email).lower()
    if await db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(409, "An account with this email already exists")
    organization = await db.scalar(select(Organization).where(Organization.id == membership.organization_id))
    if not organization:
        raise HTTPException(404, "Organization not found")
    password = secrets.token_urlsafe(24)
    user = User(email=email, full_name=email.split("@", 1)[0][:200], password_hash=hash_password(password))
    try:
        db.add(user)
        await db.flush()
        db.add(OrganizationMember(organization_id=membership.organization_id, user_id=user.id, role=payload.role))
        db.add(AuditLog(organization_id=membership.organization_id, user_id=actor.id,
                        action="account.created", entity_type="user", entity_id=user.id,
                        new_values={"email": email, "role": payload.role}))
        await db.flush()
        await provider.send_account_credentials(email, password, payload.role, organization.name)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "An account with this email already exists") from None
    except Exception:
        await db.rollback()
        logging.getLogger(__name__).warning("Account creation or credentials email delivery failed")
        raise HTTPException(502, "Unable to create account and send credentials. Check SMTP configuration and try again.") from None
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": payload.role}

async def update_user_profile(db: AsyncSession, user: User, full_name: str):
    user.full_name = full_name
    await db.commit()
    await db.refresh(user)
    return user

async def change_user_password(db: AsyncSession, user: User, current_password: str, new_password: str):
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(new_password)
    await db.commit()

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


async def recalculate_invoice_payment(db: AsyncSession, invoice_id: UUID) -> Invoice:
    invoice = await db.scalar(select(Invoice).where(Invoice.id == invoice_id))
    if not invoice:
        raise ValueError("Invoice not found")

    manual_sum_val = await db.scalar(
        select(func.coalesce(func.sum(InvoicePayment.amount), 0)).where(InvoicePayment.invoice_id == invoice_id)
    )
    manual_sum = Decimal(str(manual_sum_val or 0))

    matched_sum_val = await db.scalar(
        select(func.coalesce(func.sum(InvoiceTransactionMatch.amount), 0)).where(
            InvoiceTransactionMatch.invoice_id == invoice_id,
            InvoiceTransactionMatch.confirmed == True,
        )
    )
    matched_sum = Decimal(str(matched_sum_val or 0))

    total_paid = money(manual_sum + matched_sum)
    invoice.paid_amount = total_paid

    if total_paid >= invoice.total and invoice.total > Decimal("0.00"):
        invoice.status = InvoiceStatus.paid
    elif total_paid > Decimal("0.00"):
        invoice.status = InvoiceStatus.partially_paid
    elif total_paid == Decimal("0.00"):
        if invoice.status in (InvoiceStatus.paid, InvoiceStatus.partially_paid):
            invoice.status = InvoiceStatus.sent if invoice.invoice_type == InvoiceType.outgoing else InvoiceStatus.received

    await db.flush()
    return invoice


async def record_manual_payment(
    db: AsyncSession,
    organization_id: UUID,
    user_id: UUID,
    invoice_id: UUID,
    amount: Decimal | None = None,
    payment_date: date | None = None,
    payment_method: str = "manual",
    reference: str | None = None,
    notes: str | None = None,
) -> InvoicePayment:
    invoice = await db.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.organization_id == organization_id)
    )
    if not invoice:
        raise ValueError("Invoice not found")

    remaining_due = invoice.due_amount
    if amount is None:
        amount_to_pay = remaining_due
    else:
        amount_to_pay = money(Decimal(str(amount)))

    if amount_to_pay <= Decimal("0.00"):
        raise ValueError("Payment amount must be greater than zero")

    effective_date = payment_date or datetime.now(timezone.utc).date()

    payment = InvoicePayment(
        organization_id=organization_id,
        invoice_id=invoice_id,
        amount=amount_to_pay,
        payment_date=effective_date,
        payment_method=payment_method.strip() or "manual",
        reference=reference.strip() if reference else None,
        notes=notes.strip() if notes else None,
    )
    db.add(payment)
    await db.flush()

    await recalculate_invoice_payment(db, invoice.id)

    db.add(
        AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="invoice.payment_recorded",
            entity_type="invoice_payment",
            entity_id=payment.id,
            new_values={
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "amount": str(payment.amount),
                "payment_method": payment.payment_method,
            },
        )
    )
    await db.commit()
    await db.refresh(payment)
    return payment


async def delete_manual_payment(
    db: AsyncSession,
    organization_id: UUID,
    user_id: UUID,
    payment_id: UUID,
) -> Invoice:
    payment = await db.scalar(
        select(InvoicePayment).where(
            InvoicePayment.id == payment_id,
            InvoicePayment.organization_id == organization_id,
        )
    )
    if not payment:
        raise ValueError("Payment not found")

    invoice_id = payment.invoice_id
    deleted_amount = str(payment.amount)
    await db.delete(payment)
    await db.flush()

    invoice = await recalculate_invoice_payment(db, invoice_id)

    db.add(
        AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="invoice.payment_deleted",
            entity_type="invoice_payment",
            entity_id=payment_id,
            new_values={"invoice_id": str(invoice_id), "amount": deleted_amount},
        )
    )
    await db.commit()
    await db.refresh(invoice)
    return invoice


async def link_invoice_to_transaction(
    db: AsyncSession,
    organization_id: UUID,
    user_id: UUID,
    invoice_id: UUID,
    transaction_id: UUID,
    amount: Decimal | None = None,
) -> InvoiceTransactionMatch:
    invoice = await db.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.organization_id == organization_id)
    )
    if not invoice:
        raise ValueError("Invoice not found")

    transaction = await db.scalar(
        select(BankTransaction).where(
            BankTransaction.id == transaction_id,
            BankTransaction.organization_id == organization_id,
        )
    )
    if not transaction:
        raise ValueError("Bank transaction not found")

    expected_invoice_type = InvoiceType.outgoing if transaction.direction == "credit" else InvoiceType.incoming
    if invoice.invoice_type != expected_invoice_type:
        direction_label = "credit" if transaction.direction == "credit" else "debit"
        invoice_label = "outgoing" if transaction.direction == "credit" else "incoming"
        raise ValueError(f"A {direction_label} transaction can only be matched to an {invoice_label} invoice")

    tx_magnitude = abs(Decimal(str(transaction.amount)))

    existing_match = await db.scalar(
        select(InvoiceTransactionMatch).where(
            InvoiceTransactionMatch.invoice_id == invoice_id,
            InvoiceTransactionMatch.transaction_id == transaction_id,
            InvoiceTransactionMatch.organization_id == organization_id,
        )
    )

    other_matched_val = await db.scalar(
        select(func.coalesce(func.sum(InvoiceTransactionMatch.amount), 0)).where(
            InvoiceTransactionMatch.transaction_id == transaction_id,
            InvoiceTransactionMatch.invoice_id != invoice_id,
            InvoiceTransactionMatch.confirmed == True,
        )
    )
    other_matched = Decimal(str(other_matched_val or 0))
    available_on_tx = max(Decimal("0.00"), tx_magnitude - other_matched)

    if available_on_tx <= Decimal("0.00"):
        raise ValueError("This bank transaction is already fully allocated to other invoices")

    current_match_amount = existing_match.amount if existing_match else Decimal("0.00")
    effective_due = invoice.due_amount + current_match_amount

    if amount is None:
        allocated = min(available_on_tx, effective_due)
    else:
        allocated = money(Decimal(str(amount)))
        if allocated <= Decimal("0.00"):
            raise ValueError("Allocated amount must be greater than zero")
        if allocated > available_on_tx:
            raise ValueError(
                f"Specified amount ({allocated}) exceeds available unallocated transaction amount ({available_on_tx})"
            )

    if allocated <= Decimal("0.00"):
        raise ValueError("No remaining balance on the invoice to link")

    if existing_match:
        existing_match.amount = allocated
        existing_match.confirmed = True
        existing_match.confidence = Decimal("1.00")
        match_obj = existing_match
    else:
        match_obj = InvoiceTransactionMatch(
            organization_id=organization_id,
            invoice_id=invoice_id,
            transaction_id=transaction_id,
            amount=allocated,
            confidence=Decimal("1.00"),
            confirmed=True,
        )
        db.add(match_obj)

    await db.flush()
    await recalculate_invoice_payment(db, invoice.id)

    db.add(
        AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="invoice.transaction_linked",
            entity_type="invoice_transaction_match",
            entity_id=match_obj.id,
            new_values={
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "transaction_id": str(transaction.id),
                "amount": str(match_obj.amount),
            },
        )
    )
    await db.commit()
    await db.refresh(match_obj)
    return match_obj


async def unlink_invoice_transaction(
    db: AsyncSession,
    organization_id: UUID,
    user_id: UUID,
    match_id: UUID,
) -> Invoice:
    match_obj = await db.scalar(
        select(InvoiceTransactionMatch).where(
            InvoiceTransactionMatch.id == match_id,
            InvoiceTransactionMatch.organization_id == organization_id,
        )
    )
    if not match_obj:
        raise ValueError("Transaction match not found")

    invoice_id = match_obj.invoice_id
    tx_id = match_obj.transaction_id
    unlinked_amount = str(match_obj.amount)

    await db.delete(match_obj)
    await db.flush()

    invoice = await recalculate_invoice_payment(db, invoice_id)

    db.add(
        AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="invoice.transaction_unlinked",
            entity_type="invoice_transaction_match",
            entity_id=match_id,
            new_values={
                "invoice_id": str(invoice_id),
                "transaction_id": str(tx_id),
                "amount": unlinked_amount,
            },
        )
    )
    await db.commit()
    await db.refresh(invoice)
    return invoice


