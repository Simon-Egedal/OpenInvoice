"""Real database tests. TEST_DATABASE_URL must point at a dedicated migrated test database."""
import asyncio
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.entities import User, Organization, OrganizationMember, Customer, Supplier, Product, BankAccount, BankTransaction, Invoice, InvoiceType, InvoiceStatus, InvoiceTransactionMatch, EmailDelivery
from app.services import create_invoice, link_invoice_to_transaction, record_manual_payment
from app.schemas import InvoiceIn
from app.invoice_documents import issue_invoice
from app.deliveries import queue_invoice, process_one, decrypt_message
from app.approvals import decide_invoice

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="Set TEST_DATABASE_URL to an isolated PostgreSQL database")


async def seed(factory):
    async with factory() as db:
        from app.auth import hash_password
        user = User(email=f"{uuid4()}@example.com", full_name="Owner", password_hash=hash_password("Integration password 123"))
        org = Organization(name="Original seller", country="DK", currency="DKK", address="Original street", payment_information="Bank 123")
        db.add_all([user, org]); await db.flush()
        db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
        customer = Customer(organization_id=org.id, name="Original customer", email="customer@example.com", country="DK")
        account = BankAccount(organization_id=org.id, name="Test account", bank_name="Test bank", masked_number="1234", provider_account_id=str(uuid4()), currency="DKK", balance=Decimal("100"))
        db.add_all([customer, account]); await db.flush()
        tx = BankTransaction(organization_id=org.id, account_id=account.id, provider_transaction_id=str(uuid4()), booked_at=datetime.now(timezone.utc), description="Receipt", amount=Decimal("100"), direction="credit", currency="DKK")
        db.add(tx); await db.commit()
        return user.id, org.id, customer.id, tx.id


def invoice_payload(customer_id, number=""):
    return InvoiceIn(invoice_number=number, customer_id=customer_id, issue_date=date.today(), due_date=date.today(), lines=[{"description": "Service", "quantity": "1", "unit_price": "100", "tax_rate": "0"}])


def run_scenario(scenario):
    async def run():
        engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            await scenario(factory)
        finally:
            await engine.dispose()
    asyncio.run(run())


def test_concurrent_numbering_and_allocations():
    async def scenario(factory):
        user_id, org_id, customer_id, tx_id = await seed(factory)
        async def create():
            async with factory() as db:
                invoice = await create_invoice(db, invoice_payload(customer_id), org_id, user_id)
                await issue_invoice(db, org_id, invoice.id, user_id); await db.commit()
                return invoice.id, invoice.invoice_number
        first, second = await asyncio.gather(create(), create())
        assert first[1] != second[1]
        async def allocate(invoice_id):
            async with factory() as db:
                try:
                    return await link_invoice_to_transaction(db, org_id, user_id, invoice_id, tx_id, Decimal("75"))
                except ValueError as exc:
                    return exc
        results = await asyncio.gather(allocate(first[0]), allocate(second[0]))
        assert sum(isinstance(result, InvoiceTransactionMatch) for result in results) == 1
        async with factory() as db:
            rows = await db.execute(select(InvoiceTransactionMatch).where(InvoiceTransactionMatch.organization_id == org_id))
            assert sum(row.amount for row in rows.scalars().all()) == Decimal("75")
    run_scenario(scenario)


def test_invitation_tokens_expire_are_single_use_and_revoke_sessions(monkeypatch):
    from app.core.config import settings
    from app.accounts import invite_account, consume_token, create_token, update_member
    from app.models.entities import AccountToken
    from app.schemas import AccountCreateIn
    from app.auth import verify_password
    from fastapi import HTTPException
    monkeypatch.setattr(settings, "email_provider", "smtp")
    async def scenario(factory):
        actor_id, org_id, _, _ = await seed(factory)
        membership = SimpleNamespace(organization_id=org_id, role="owner")
        async with factory() as db:
            actor = await db.get(User, actor_id)
            result = await invite_account(db, AccountCreateIn(email=f"{uuid4()}@example.com", role="viewer"), membership, actor)
            user_id = result["id"]
            delivery = await db.scalar(select(EmailDelivery).where(EmailDelivery.recipient == result["email"]))
            raw = decrypt_message(delivery.encrypted_payload)["body"].split("#", 1)[1].split()[0]
            stored = await db.scalar(select(AccountToken).where(AccountToken.user_id == user_id))
            assert raw not in stored.token_hash and raw not in delivery.encrypted_payload
            assert not result["is_active"]
            await consume_token(db, raw, "Chosen password 123")
            with pytest.raises(HTTPException):
                await consume_token(db, raw, "Other password 123")
            await db.rollback()
            user = await db.get(User, user_id)
            assert user.is_active and verify_password("Chosen password 123", user.password_hash)
            old_version = user.session_version
            await update_member(db, membership, SimpleNamespace(id=actor_id), user_id, revoke=True)
            assert user.session_version == old_version + 1
            token = await create_token(db, user, org_id, "reset")
            token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            await db.commit()
            delivery = await db.scalar(select(EmailDelivery).where(EmailDelivery.idempotency_key == f"reset:{token.id}"))
            raw = decrypt_message(delivery.encrypted_payload)["body"].split("#", 1)[1].split()[0]
            with pytest.raises(HTTPException) as error:
                await consume_token(db, raw, "Another password 123")
            assert error.value.status_code == 400
    run_scenario(scenario)


def test_http_permissions_isolation_original_documents_and_pagination(monkeypatch, tmp_path):
    import httpx
    from app.main import app
    from app.db.session import get_db
    from app.core.config import settings
    monkeypatch.setattr(settings, "local_storage_path", str(tmp_path))
    async def scenario(factory):
        actor_id, org_id, customer_id, _ = await seed(factory)
        _, other_org_id, other_customer_id, _ = await seed(factory)
        async def database():
            async with factory() as db: yield db
        app.dependency_overrides[get_db] = database
        try:
            async with factory() as db:
                actor = await db.get(User, actor_id)
                email = actor.email
                other_invoice = await create_invoice(db, invoice_payload(other_customer_id), other_org_id, actor_id)
                other_invoice_id = str(other_invoice.id)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                assert (await client.post("/api/v1/auth/login", json={"email": email, "password": "Integration password 123"})).status_code == 200
                foreign = await client.get(f"/api/v1/invoices/{other_invoice_id}")
                assert foreign.status_code == 404
                foreign_create = await client.post("/api/v1/invoices", json=invoice_payload(other_customer_id).model_dump(mode="json"))
                assert foreign_create.status_code == 422
                supplier_response = await client.post("/api/v1/suppliers", json={"name": "Supplier", "country": "DK"})
                supplier_id = supplier_response.json()["id"]
                original = b"%PDF-1.4\noriginal supplier content"
                received = await client.post("/api/v1/invoices/receive", data={"invoice_number": "SUP-1", "supplier_id": supplier_id, "issue_date": "2026-10-01", "due_date": "2026-10-15", "description": "Purchase", "net_amount": "100", "tax_rate": "25", "currency": "DKK"}, files={"document": ("original.pdf", original, "application/pdf")})
                assert received.status_code == 201, received.text
                invoice_id = received.json()["id"]
                docs = await client.get(f"/api/v1/invoices/{invoice_id}/documents")
                document_id = docs.json()[0]["id"]
                download = await client.get(f"/api/v1/invoices/{invoice_id}/documents/{document_id}")
                assert download.content == original
                wrong_parent = await client.get(f"/api/v1/invoices/{other_invoice_id}/documents/{document_id}")
                assert wrong_parent.status_code == 404
                first = await client.get("/api/v1/invoices?limit=1&offset=0")
                second = await client.get("/api/v1/invoices?limit=1&offset=1")
                assert len(first.json()) == 1 and second.json() == []
                assert (await client.get("/api/v1/invoices?limit=0")).status_code == 422
                async with factory() as db:
                    member = await db.scalar(select(OrganizationMember).where(OrganizationMember.user_id == actor_id))
                    member.role = "viewer"; await db.commit()
                assert (await client.post("/api/v1/banking/sync")).status_code == 403
                assert (await client.post(f"/api/v1/invoices/{invoice_id}/send")).status_code == 403
                async with factory() as db:
                    actor = await db.get(User, actor_id)
                    actor.session_version += 1; await db.commit()
                assert (await client.get("/api/v1/auth/me")).status_code == 401
        finally:
            app.dependency_overrides.clear()
    run_scenario(scenario)


def test_csv_import_is_atomic_and_exports_escape_formulas():
    from app.data_transfer import import_records
    from app.providers.accounting import CSVAccountingProvider
    from fastapi import HTTPException
    async def scenario(factory):
        actor_id, org_id, _, _ = await seed(factory)
        async with factory() as db:
            with pytest.raises(HTTPException) as error:
                await import_records(db, org_id, actor_id, "products", b"name,unit_price\nValid,10.00\nInvalid,1.001\n")
            assert error.value.status_code == 422
            assert not (await db.execute(select(Product).where(Product.organization_id == org_id))).scalars().all()
            imported = await import_records(db, org_id, actor_id, "products", b"name,unit_price\nFirst,10.00\nSecond,20.25\n")
            assert imported["imported"] == 2
            with pytest.raises(HTTPException) as error:
                await import_records(db, org_id, actor_id, "products", b"name,unit_price\nFirst,1.00\nThird,5.00\n")
            assert error.value.status_code == 409
        csv = await CSVAccountingProvider().export_rows([{"invoice_number": "=HYPERLINK(\"bad\")", "amount": Decimal("10.00")}], ["invoice_number", "amount"])
        assert b"'=HYPERLINK" in csv and b"10.00" in csv
    run_scenario(scenario)


def test_outbox_retries_definite_failure_and_cancels_paid_reminders(monkeypatch, tmp_path):
    import smtplib
    from app.core.config import settings
    monkeypatch.setattr(settings, "local_storage_path", str(tmp_path))
    async def scenario(factory):
        actor_id, org_id, customer_id, _ = await seed(factory)
        async with factory() as db:
            payload = invoice_payload(customer_id)
            payload.issue_date = date.today() - timedelta(days=10)
            payload.due_date = date.today() - timedelta(days=1)
            invoice = await create_invoice(db, payload, org_id, actor_id)
            invoice_id = invoice.id
            response = await queue_invoice(db, org_id, invoice_id, actor_id)
            delivery_id = response["id"]
        class Provider:
            calls = 0
            async def send_invoice(self, *args):
                self.calls += 1
                if self.calls == 1:
                    raise smtplib.SMTPConnectError(421, b"Temporarily unavailable")
                return "accepted"
        provider = Provider()
        await process_one(factory, provider, organization_id=org_id)
        async with factory() as db:
            from uuid import UUID
            delivery = await db.get(EmailDelivery, UUID(delivery_id))
            assert delivery.status == "failed" and delivery.failed_attempts == 1
            delivery.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            await db.commit()
        await process_one(factory, provider, organization_id=org_id)
        async with factory() as db:
            delivery = await db.get(EmailDelivery, UUID(delivery_id))
            invoice = await db.get(Invoice, invoice_id)
            assert delivery.status == "sent" and invoice.status == InvoiceStatus.sent
            reminder = await queue_invoice(db, org_id, invoice_id, actor_id, "reminder-one", reminder=True)
            await record_manual_payment(db, org_id, actor_id, invoice_id)
        await process_one(factory, provider, organization_id=org_id)
        async with factory() as db:
            cancelled = await db.get(EmailDelivery, UUID(reminder["id"]))
            assert cancelled.status == "cancelled"
            assert provider.calls == 2
    run_scenario(scenario)


def test_uncertain_delivery_does_not_automatically_resend(monkeypatch, tmp_path):
    from app.core.config import settings
    monkeypatch.setattr(settings, "local_storage_path", str(tmp_path))
    async def scenario(factory):
        actor_id, org_id, customer_id, _ = await seed(factory)
        async with factory() as db:
            invoice = await create_invoice(db, invoice_payload(customer_id), org_id, actor_id)
            response = await queue_invoice(db, org_id, invoice.id, actor_id)
        class Provider:
            calls = 0
            async def send_invoice(self, *args):
                self.calls += 1
                raise TimeoutError("Connection lost after potential acceptance")
        provider = Provider()
        await process_one(factory, provider, organization_id=org_id)
        assert not await process_one(factory, provider, organization_id=org_id)
        assert provider.calls == 1
        async with factory() as db:
            from uuid import UUID
            row = await db.get(EmailDelivery, UUID(response["id"]))
            assert row.status == "uncertain" and row.error_message == "TimeoutError"
    run_scenario(scenario)


def test_issue_snapshot_queue_deduplication_and_paid_resend(monkeypatch, tmp_path):
    from app.core.config import settings
    monkeypatch.setattr(settings, "local_storage_path", str(tmp_path))
    async def scenario(factory):
        user_id, org_id, customer_id, _ = await seed(factory)
        async with factory() as db:
            invoice = await create_invoice(db, invoice_payload(customer_id), org_id, user_id)
            invoice_id = invoice.id
            first = await queue_invoice(db, org_id, invoice_id, user_id, "same-request")
            second = await queue_invoice(db, org_id, invoice_id, user_id, "same-request")
            assert first["id"] == second["id"]
            customer = await db.get(Customer, customer_id)
            customer.name = "Changed customer"
            org = await db.get(Organization, org_id)
            org.name = "Changed seller"
            await db.commit()
            await record_manual_payment(db, org_id, user_id, invoice_id)
            await queue_invoice(db, org_id, invoice_id, user_id, "resend")
            await db.refresh(invoice)
            assert invoice.status == InvoiceStatus.paid
            assert invoice.issued_snapshot["recipient"]["name"] == "Original customer"
            assert invoice.issued_snapshot["organization"]["name"] == "Original seller"
        class Provider:
            def __init__(self): self.messages = []
            async def send_invoice(self, *args): self.messages.append(args); return "test-message"
        provider = Provider()
        await process_one(factory, provider, organization_id=org_id)
        await process_one(factory, provider, organization_id=org_id)
        assert len(provider.messages) == 2
        assert b"Original customer" in provider.messages[0][3]
        assert b"Changed customer" not in provider.messages[0][3]
    run_scenario(scenario)


def test_approval_records_actor_and_requires_reason():
    async def scenario(factory):
        user_id, org_id, _, _ = await seed(factory)
        async with factory() as db:
            supplier = Supplier(organization_id=org_id, name="Supplier", country="DK")
            db.add(supplier); await db.flush()
            invoice = Invoice(organization_id=org_id, created_by=user_id, supplier_id=supplier.id, invoice_number=str(uuid4()), invoice_type=InvoiceType.incoming, status=InvoiceStatus.received, issue_date=date.today(), due_date=date.today(), currency="DKK", total=Decimal("100"))
            db.add(invoice); await db.commit()
            member = SimpleNamespace(organization_id=org_id, role="member")
            approver = SimpleNamespace(organization_id=org_id, role="approver")
            invoice_id = invoice.id
            await decide_invoice(db, member, invoice_id, user_id, "pending_approval")
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as error:
                await decide_invoice(db, approver, invoice_id, user_id, "rejected", "")
            assert error.value.status_code == 422
            await db.rollback()
            rejected = await decide_invoice(db, approver, invoice_id, user_id, "rejected", "Wrong total")
            assert rejected.status == InvoiceStatus.rejected
            await decide_invoice(db, member, invoice_id, user_id, "pending_approval")
            approved = await decide_invoice(db, approver, invoice_id, user_id, "approved", "Checked receipt")
            assert approved.status == InvoiceStatus.approved
            from app.models.entities import InvoiceDecision
            decisions = await db.execute(select(InvoiceDecision).where(InvoiceDecision.invoice_id == invoice_id).order_by(InvoiceDecision.created_at))
            history = decisions.scalars().all()
            assert [item.decision for item in history] == ["pending_approval", "rejected", "pending_approval", "approved"]
            assert all(item.user_id == user_id for item in history)
    run_scenario(scenario)
