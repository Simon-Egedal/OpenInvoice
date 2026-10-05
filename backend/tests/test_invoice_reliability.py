import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.schemas import InvoiceIn
from app.services import link_invoice_to_transaction, record_manual_payment, delete_manual_payment, unlink_invoice_transaction
from app.models.entities import Invoice, InvoiceStatus, InvoiceType, BankTransaction, InvoicePayment, InvoiceTransactionMatch
from app.invoice_pdf import make_pdf
from app.api.v1.reports import aging_report
from app.api.v1.router import router
from app.auth import write_membership
from test_invoice_payments_and_matching import InMemoryDB


def entities():
    organization_id = uuid4()
    invoice = Invoice(id=uuid4(), organization_id=organization_id, created_by=uuid4(), invoice_number="INV-1", invoice_type=InvoiceType.outgoing, status=InvoiceStatus.sent, currency="DKK", issue_date=date.today(), due_date=date.today(), total=Decimal("100"), paid_amount=Decimal("0"))
    transaction = BankTransaction(id=uuid4(), organization_id=organization_id, account_id=uuid4(), direction="credit", currency="DKK", amount=Decimal("200"))
    return invoice, transaction


def test_matching_rejects_currency_mismatch_and_overallocation():
    invoice, transaction = entities()
    transaction.currency = "EUR"
    db = InMemoryDB([invoice, transaction])
    with pytest.raises(ValueError, match="currencies"):
        asyncio.run(link_invoice_to_transaction(db, invoice.organization_id, invoice.created_by, invoice.id, transaction.id))
    transaction.currency = "DKK"
    with pytest.raises(ValueError, match="remaining invoice balance"):
        asyncio.run(link_invoice_to_transaction(db, invoice.organization_id, invoice.created_by, invoice.id, transaction.id, Decimal("150")))


def test_manual_overpayment_and_draft_payment_are_rejected():
    invoice, _ = entities()
    db = InMemoryDB([invoice])
    with pytest.raises(ValueError, match="remaining invoice balance"):
        asyncio.run(record_manual_payment(db, invoice.organization_id, invoice.created_by, invoice.id, Decimal("101")))
    invoice.status = InvoiceStatus.draft
    with pytest.raises(ValueError, match="Issue or approve"):
        asyncio.run(record_manual_payment(db, invoice.organization_id, invoice.created_by, invoice.id))


def test_deletion_checks_parent_invoice():
    invoice, transaction = entities()
    payment = InvoicePayment(id=uuid4(), organization_id=invoice.organization_id, invoice_id=invoice.id, amount=Decimal("10"))
    match = InvoiceTransactionMatch(id=uuid4(), organization_id=invoice.organization_id, invoice_id=invoice.id, transaction_id=transaction.id, amount=Decimal("10"), confirmed=True)
    db = InMemoryDB([invoice, payment, match])
    with pytest.raises(ValueError, match="Payment not found"):
        asyncio.run(delete_manual_payment(db, invoice.organization_id, invoice.created_by, payment.id, expected_invoice_id=uuid4()))
    with pytest.raises(ValueError, match="match not found"):
        asyncio.run(unlink_invoice_transaction(db, invoice.organization_id, invoice.created_by, match.id, expected_invoice_id=uuid4()))
    assert not db.deleted


def test_mutating_routes_require_write_membership():
    for path in ["/invoices/{invoice_id}/send", "/banking/sync", "/banking/connections/authorize", "/banking/connections/callback"]:
        route = next(route for route in router.routes if route.path == path)
        assert write_membership in [dependency.call for dependency in route.dependant.dependencies]


def test_invoice_validation_bounds_dates_and_precision():
    payload = {"issue_date": "2026-10-05", "due_date": "2026-10-01", "lines": [{"description": "Test", "quantity": "1", "unit_price": "10", "tax_rate": "25"}]}
    with pytest.raises(ValidationError, match="Due date"):
        InvoiceIn(**payload)
    payload["due_date"] = "2026-10-10"
    payload["lines"][0]["unit_price"] = "1.001"
    with pytest.raises(ValidationError):
        InvoiceIn(**payload)


def test_pdf_flows_across_pages_with_seller_payment_details():
    invoice, _ = entities()
    invoice.subtotal = Decimal("100")
    invoice.tax_amount = Decimal("25")
    invoice.notes = "Invoice notes"
    lines = [SimpleNamespace(description="Long description " * 20, quantity=Decimal("1"), unit_price=Decimal("1"), line_total=Decimal("1"), tax_rate=Decimal("25")) for _ in range(80)]
    pdf = make_pdf(invoice, lines, org={"name": "Seller", "address": "Seller Street", "vat_number": "DK12345678", "payment_information": "Bank account 1234", "payment_terms": "Net 14 days"})
    assert pdf.count(b"/Type /Page\n") > 1
    assert b"Seller Street" in pdf and b"Bank account 1234" in pdf and b"Net 14 days" in pdf


def test_aging_separates_currency_direction_and_partial_balances():
    invoice, _ = entities()
    invoice.paid_amount = Decimal("40")
    invoice.due_date = datetime.now(timezone.utc).date() - timedelta(days=31)
    incoming, _ = entities()
    incoming.invoice_type = InvoiceType.incoming
    incoming.currency = "EUR"
    class DB:
        async def execute(self, statement):
            assert "organization_id" in str(statement)
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [invoice, incoming]))
    groups = asyncio.run(aging_report(SimpleNamespace(organization_id=invoice.organization_id), DB()))
    outgoing = next(group for group in groups if group["invoice_type"] == "outgoing")
    assert outgoing["outstanding"] == "60.00"
    assert outgoing["days_31_60"] == "60.00"
    assert outgoing["paid"] == "40.00"
    assert len(groups) == 2
