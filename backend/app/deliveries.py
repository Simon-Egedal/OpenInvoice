"""Durable encrypted outbox. SMTP acceptance is recorded separately from invoice payment state."""
import base64
import json
import os
import smtplib
from datetime import datetime, timedelta, timezone
from uuid import UUID
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException
from sqlalchemy import select
from app.core.runtime_config import get_or_create_secret
from app.models.entities import AccountToken, AuditLog, Customer, EmailDelivery, Invoice, InvoiceStatus, Organization, User
from app.invoice_documents import issue_invoice
from app.providers.email import email_provider
from app.providers.storage import storage_provider

MAX_ATTEMPTS = 5


def encrypt_message(payload):
    nonce = os.urandom(12)
    key = base64.urlsafe_b64decode(get_or_create_secret())
    return base64.urlsafe_b64encode(nonce + AESGCM(key).encrypt(nonce, json.dumps(payload).encode(), b"openinvoice-outbox")).decode()


def decrypt_message(payload):
    raw = base64.urlsafe_b64decode(payload)
    key = base64.urlsafe_b64decode(get_or_create_secret())
    return json.loads(AESGCM(key).decrypt(raw[:12], raw[12:], b"openinvoice-outbox"))


async def enqueue_message(db, organization_id, recipient, kind, idempotency_key, payload, invoice_id=None):
    existing = await db.scalar(select(EmailDelivery).where(EmailDelivery.organization_id == organization_id, EmailDelivery.idempotency_key == idempotency_key))
    if existing:
        return existing
    delivery = EmailDelivery(organization_id=organization_id, invoice_id=invoice_id, recipient=recipient, kind=kind, idempotency_key=idempotency_key, encrypted_payload=encrypt_message(payload), status="queued", failed_attempts=0, next_attempt_at=datetime.now(timezone.utc))
    db.add(delivery)
    await db.flush()
    return delivery


async def queue_invoice(db, organization_id, invoice_id, user_id, key="initial", reminder=False):
    await db.scalar(select(Organization.id).where(Organization.id == organization_id).with_for_update(key_share=True))
    invoice = await db.scalar(select(Invoice).where(Invoice.id == invoice_id, Invoice.organization_id == organization_id).with_for_update())
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if reminder and not invoice.is_overdue:
        raise HTTPException(409, "Only overdue invoices with an unpaid balance can receive reminders")
    invoice = await issue_invoice(db, organization_id, invoice_id, user_id)
    recipient = invoice.issued_snapshot["recipient"].get("email")
    if not recipient:
        raise HTTPException(422, "Customer has no email address")
    kind = "reminder" if reminder else "invoice"
    payload = {"subject": f"{'Payment reminder: ' if reminder else ''}Invoice {invoice.invoice_number}", "body": f"Please find invoice {invoice.invoice_number} attached." if not reminder else f"Invoice {invoice.invoice_number} was due on {invoice.due_date}. Remaining balance: {invoice.currency} {invoice.due_amount:.2f}.", "pdf_key": invoice.issued_pdf_key, "filename": "invoice.pdf"}
    delivery = await enqueue_message(db, organization_id, recipient, kind, f"{kind}:{invoice_id}:{key}", payload, invoice_id)
    db.add(AuditLog(organization_id=organization_id, user_id=user_id, action=f"{kind}.queued", entity_type="email_delivery", entity_id=delivery.id))
    await db.commit()
    return {"id": str(delivery.id), "status": delivery.status, "recipient": delivery.recipient}


async def process_one(session_factory, provider=None, organization_id=None):
    """Persist the claim before network IO. Interrupted claims require manual review."""
    now = datetime.now(timezone.utc)
    async with session_factory() as db:
        stale = await db.execute(select(EmailDelivery).where(EmailDelivery.status == "sending", EmailDelivery.started_at < now - timedelta(minutes=5)).with_for_update(skip_locked=True))
        for delivery in stale.scalars().all():
            delivery.status = "uncertain"
            delivery.error_message = "Delivery interrupted; verify receipt before retrying"
        query = select(EmailDelivery).where(EmailDelivery.status.in_(["queued", "failed"]), EmailDelivery.next_attempt_at <= now, EmailDelivery.failed_attempts < MAX_ATTEMPTS)
        if organization_id:
            query = query.where(EmailDelivery.organization_id == organization_id)
        row = await db.scalar(query.order_by(EmailDelivery.created_at).limit(1).with_for_update(skip_locked=True))
        if row is None:
            await db.commit()
            return False
        row.status = "sending"
        row.started_at = now
        delivery_id = row.id
        await db.commit()
    status, error, message_id = "sent", None, None
    try:
        payload = decrypt_message(row.encrypted_payload)
        if row.kind in {"invitation", "reset"}:
            async with session_factory() as db:
                token = await db.scalar(select(AccountToken).where(AccountToken.id == UUID(payload["token_id"]), AccountToken.organization_id == row.organization_id))
                user = await db.get(User, token.user_id) if token else None
                if not token or not user or token.consumed_at or token.expires_at <= now or token.session_version != user.session_version:
                    status = "cancelled"
        # Reminders queued earlier must not chase invoices paid in the meantime.
        if row.kind == "reminder":
            async with session_factory() as db:
                invoice = await db.scalar(select(Invoice).where(Invoice.id == row.invoice_id, Invoice.organization_id == row.organization_id))
                if not invoice or not invoice.is_overdue:
                    status = "cancelled"
                else:
                    payload["body"] = f"Invoice {invoice.invoice_number} was due on {invoice.due_date}. Remaining balance: {invoice.currency} {invoice.due_amount:.2f}."
        if status != "cancelled":
            provider = provider or email_provider()
            if payload.get("pdf_key"):
                pdf = await storage_provider().get(payload["pdf_key"])
                message_id = await provider.send_invoice(row.recipient, payload["subject"], payload["body"], pdf, payload["filename"])
            else:
                message_id = await provider.send_message(row.recipient, payload["subject"], payload["body"])
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPAuthenticationError, smtplib.SMTPConnectError, ConnectionRefusedError, FileNotFoundError) as exc:
        status, error = "failed", type(exc).__name__
    except Exception as exc:
        # Acceptance may have happened before an IO failure; never blindly resend.
        status, error = "uncertain", type(exc).__name__
    async with session_factory() as db:
        await db.scalar(select(Organization.id).where(Organization.id == row.organization_id).with_for_update(key_share=True))
        delivery = await db.scalar(select(EmailDelivery).where(EmailDelivery.id == delivery_id).with_for_update())
        if delivery.status != "sending":
            return True
        delivery.status = status
        delivery.error_message = error
        delivery.provider_message_id = message_id
        if status in {"failed", "uncertain"}:
            delivery.failed_attempts += 1
            delivery.next_attempt_at = now + timedelta(seconds=30 * 2 ** delivery.failed_attempts)
        if status == "sent":
            delivery.sent_at = datetime.now(timezone.utc)
            delivery.encrypted_payload = encrypt_message({**payload, "body": "Delivered account message"}) if row.kind in {"invitation", "reset"} else delivery.encrypted_payload
            if delivery.kind == "invoice":
                invoice = await db.scalar(select(Invoice).where(Invoice.id == delivery.invoice_id, Invoice.organization_id == delivery.organization_id).with_for_update())
                if invoice and invoice.status == InvoiceStatus.issued:
                    invoice.status = InvoiceStatus.sent
        db.add(AuditLog(organization_id=delivery.organization_id, action=f"email.{status}", entity_type="email_delivery", entity_id=delivery.id, new_values={"kind": delivery.kind, "recipient": delivery.recipient}))
        await db.commit()
    return True
