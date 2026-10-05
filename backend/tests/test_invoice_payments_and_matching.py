from datetime import date, datetime, timezone
from decimal import Decimal
import asyncio
from uuid import uuid4
import pytest

from app.models.entities import BankTransaction, Invoice, InvoicePayment, InvoiceStatus, InvoiceTransactionMatch, InvoiceType
from app.services import (
    delete_manual_payment,
    link_invoice_to_transaction,
    recalculate_invoice_payment,
    record_manual_payment,
    unlink_invoice_transaction,
)


def test_invoice_due_amount_property():
    inv = Invoice(
        id=uuid4(),
        organization_id=uuid4(),
        created_by=uuid4(),
        invoice_number="INV-001",
        invoice_type=InvoiceType.outgoing,
        status=InvoiceStatus.sent,
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 10, 15),
        total=Decimal("150.00"),
        paid_amount=Decimal("0.00"),
    )
    assert inv.due_amount == Decimal("150.00")

    inv.paid_amount = Decimal("50.00")
    assert inv.due_amount == Decimal("100.00")

    inv.paid_amount = Decimal("150.00")
    assert inv.due_amount == Decimal("0.00")

    # Overpayment safety
    inv.paid_amount = Decimal("200.00")
    assert inv.due_amount == Decimal("0.00")


class InMemoryDB:
    def __init__(self, entities=None):
        self.entities = list(entities or [])
        self.added = []
        self.deleted = []

    def add(self, entity):
        if not getattr(entity, "id", None):
            entity.id = uuid4()
        self.entities.append(entity)
        self.added.append(entity)

    async def delete(self, entity):
        self.deleted.append(entity)
        if entity in self.entities:
            self.entities.remove(entity)

    async def flush(self):
        pass

    async def commit(self):
        pass

    async def refresh(self, entity):
        pass

    async def scalar(self, statement):
        sql = str(statement.compile(compile_kwargs={"literal_binds": True})).lower().replace("-", "")
        # Sum of manual payments
        if "sum(invoice_payments.amount)" in sql:
            for e in self.entities:
                if isinstance(e, Invoice):
                    inv_id = e.id.hex.lower()
                    if inv_id in sql:
                        total = sum(p.amount for p in self.entities if isinstance(p, InvoicePayment) and p.invoice_id.hex.lower() == inv_id)
                        return total
            return Decimal("0.00")

        # Sum of matches
        if "sum(invoice_transaction_matches.amount)" in sql:
            if "invoice_transaction_matches.invoice_id !=" in sql or "transaction_id" in sql and "invoice_id !=" in sql:
                for tx in self.entities:
                    if isinstance(tx, BankTransaction):
                        tx_id = tx.id.hex.lower()
                        if tx_id in sql:
                            total = Decimal("0.00")
                            for m in self.entities:
                                if isinstance(m, InvoiceTransactionMatch) and m.transaction_id.hex.lower() == tx_id and m.confirmed:
                                    if m.invoice_id.hex.lower() not in sql:
                                        total += m.amount
                            return total
                return Decimal("0.00")

            for e in self.entities:
                if isinstance(e, Invoice):
                    inv_id = e.id.hex.lower()
                    if inv_id in sql:
                        total = sum(m.amount for m in self.entities if isinstance(m, InvoiceTransactionMatch) and m.invoice_id.hex.lower() == inv_id and m.confirmed)
                        return total
            return Decimal("0.00")

        # Select invoice
        if "from invoices" in sql:
            for e in self.entities:
                if isinstance(e, Invoice) and e.id.hex.lower() in sql:
                    # If organization_id is checked in WHERE clause, verify it matches
                    where_part = sql.split("where", 1)[1] if "where" in sql else ""
                    if "organization_id" in where_part and e.organization_id.hex.lower() not in where_part:
                        return None
                    return e
            return None

        # Select transaction
        if "from bank_transactions" in sql:
            for e in self.entities:
                if isinstance(e, BankTransaction) and e.id.hex.lower() in sql:
                    where_part = sql.split("where", 1)[1] if "where" in sql else ""
                    if "organization_id" in where_part and e.organization_id.hex.lower() not in where_part:
                        return None
                    return e
            return None

        # Select match
        if "from invoice_transaction_matches" in sql:
            for e in self.entities:
                if isinstance(e, InvoiceTransactionMatch):
                    where_part = sql.split("where", 1)[1] if "where" in sql else ""
                    if "organization_id" in where_part and e.organization_id.hex.lower() not in where_part:
                        return None
                    if e.id.hex.lower() in sql:
                        return e
                    if e.invoice_id.hex.lower() in sql and e.transaction_id.hex.lower() in sql:
                        return e
            return None

        # Select payment
        if "from invoice_payments" in sql:
            for e in self.entities:
                if isinstance(e, InvoicePayment) and e.id.hex.lower() in sql:
                    where_part = sql.split("where", 1)[1] if "where" in sql else ""
                    if "organization_id" in where_part and e.organization_id.hex.lower() not in where_part:
                        return None
                    return e
            return None

        return None


def test_manual_partial_payment_deducts_due_and_sets_partially_paid():
    org_id = uuid4()
    user_id = uuid4()
    inv = Invoice(
        id=uuid4(),
        organization_id=org_id,
        created_by=user_id,
        invoice_number="INV-200",
        invoice_type=InvoiceType.outgoing,
        status=InvoiceStatus.sent,
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 10, 15),
        total=Decimal("500.00"),
        paid_amount=Decimal("0.00"),
    )
    db = InMemoryDB([inv])

    async def run():
        # Record partial payment of 200.00
        payment = await record_manual_payment(
            db=db,
            organization_id=org_id,
            user_id=user_id,
            invoice_id=inv.id,
            amount=Decimal("200.00"),
            payment_method="cash",
        )
        assert payment.amount == Decimal("200.00")
        assert inv.paid_amount == Decimal("200.00")
        assert inv.due_amount == Decimal("300.00")
        assert inv.status == InvoiceStatus.partially_paid

        # Record remaining payment of 300.00
        p2 = await record_manual_payment(
            db=db,
            organization_id=org_id,
            user_id=user_id,
            invoice_id=inv.id,
            amount=None,  # Full remaining
        )
        assert p2.amount == Decimal("300.00")
        assert inv.paid_amount == Decimal("500.00")
        assert inv.due_amount == Decimal("0.00")
        assert inv.status == InvoiceStatus.paid

    asyncio.run(run())


def test_link_smaller_transaction_deducts_amount_from_due():
    org_id = uuid4()
    user_id = uuid4()
    inv = Invoice(
        id=uuid4(),
        organization_id=org_id,
        created_by=user_id,
        invoice_number="INV-300",
        invoice_type=InvoiceType.outgoing,
        status=InvoiceStatus.sent,
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 10, 15),
        total=Decimal("1000.00"),
        paid_amount=Decimal("0.00"),
    )
    tx = BankTransaction(
        id=uuid4(),
        organization_id=org_id,
        account_id=uuid4(),
        provider_transaction_id="tx-1",
        booked_at=datetime.now(timezone.utc),
        description="Customer transfer partial",
        amount=Decimal("350.00"),
        currency="DKK",
    )
    db = InMemoryDB([inv, tx])

    async def run():
        match = await link_invoice_to_transaction(
            db=db,
            organization_id=org_id,
            user_id=user_id,
            invoice_id=inv.id,
            transaction_id=tx.id,
        )
        assert match.amount == Decimal("350.00")
        assert inv.paid_amount == Decimal("350.00")
        assert inv.due_amount == Decimal("650.00")
        assert inv.status == InvoiceStatus.partially_paid

    asyncio.run(run())


def test_link_multiple_transactions_to_one_invoice():
    org_id = uuid4()
    user_id = uuid4()
    inv = Invoice(
        id=uuid4(),
        organization_id=org_id,
        created_by=user_id,
        invoice_number="INV-400",
        invoice_type=InvoiceType.outgoing,
        status=InvoiceStatus.sent,
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 10, 15),
        total=Decimal("500.00"),
        paid_amount=Decimal("0.00"),
    )
    tx1 = BankTransaction(
        id=uuid4(),
        organization_id=org_id,
        account_id=uuid4(),
        provider_transaction_id="tx-1",
        booked_at=datetime.now(timezone.utc),
        description="First installment",
        amount=Decimal("200.00"),
        currency="DKK",
    )
    tx2 = BankTransaction(
        id=uuid4(),
        organization_id=org_id,
        account_id=uuid4(),
        provider_transaction_id="tx-2",
        booked_at=datetime.now(timezone.utc),
        description="Second installment",
        amount=Decimal("300.00"),
        currency="DKK",
    )
    db = InMemoryDB([inv, tx1, tx2])

    async def run():
        # Link first transaction
        await link_invoice_to_transaction(
            db=db,
            organization_id=org_id,
            user_id=user_id,
            invoice_id=inv.id,
            transaction_id=tx1.id,
        )
        assert inv.paid_amount == Decimal("200.00")
        assert inv.due_amount == Decimal("300.00")
        assert inv.status == InvoiceStatus.partially_paid

        # Link second transaction
        await link_invoice_to_transaction(
            db=db,
            organization_id=org_id,
            user_id=user_id,
            invoice_id=inv.id,
            transaction_id=tx2.id,
        )
        assert inv.paid_amount == Decimal("500.00")
        assert inv.due_amount == Decimal("0.00")
        assert inv.status == InvoiceStatus.paid

    asyncio.run(run())


def test_transaction_larger_than_due_caps_allocation():
    org_id = uuid4()
    user_id = uuid4()
    inv = Invoice(
        id=uuid4(),
        organization_id=org_id,
        created_by=user_id,
        invoice_number="INV-500",
        invoice_type=InvoiceType.outgoing,
        status=InvoiceStatus.sent,
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 10, 15),
        total=Decimal("250.00"),
        paid_amount=Decimal("0.00"),
    )
    # 1000 DKK transaction
    tx = BankTransaction(
        id=uuid4(),
        organization_id=org_id,
        account_id=uuid4(),
        provider_transaction_id="tx-large",
        booked_at=datetime.now(timezone.utc),
        description="Bulk wire transfer",
        amount=Decimal("1000.00"),
        currency="DKK",
    )
    db = InMemoryDB([inv, tx])

    async def run():
        match = await link_invoice_to_transaction(
            db=db,
            organization_id=org_id,
            user_id=user_id,
            invoice_id=inv.id,
            transaction_id=tx.id,
        )
        # Should cap allocation to 250.00
        assert match.amount == Decimal("250.00")
        assert inv.paid_amount == Decimal("250.00")
        assert inv.due_amount == Decimal("0.00")
        assert inv.status == InvoiceStatus.paid

    asyncio.run(run())


def test_unlink_transaction_restores_status_and_due():
    org_id = uuid4()
    user_id = uuid4()
    inv = Invoice(
        id=uuid4(),
        organization_id=org_id,
        created_by=user_id,
        invoice_number="INV-600",
        invoice_type=InvoiceType.outgoing,
        status=InvoiceStatus.sent,
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 10, 15),
        total=Decimal("400.00"),
        paid_amount=Decimal("0.00"),
    )
    tx = BankTransaction(
        id=uuid4(),
        organization_id=org_id,
        account_id=uuid4(),
        provider_transaction_id="tx-600",
        booked_at=datetime.now(timezone.utc),
        description="Wire transfer",
        amount=Decimal("400.00"),
        currency="DKK",
    )
    db = InMemoryDB([inv, tx])

    async def run():
        match = await link_invoice_to_transaction(
            db=db,
            organization_id=org_id,
            user_id=user_id,
            invoice_id=inv.id,
            transaction_id=tx.id,
        )
        assert inv.status == InvoiceStatus.paid
        assert inv.due_amount == Decimal("0.00")

        # Now unlink
        updated_inv = await unlink_invoice_transaction(
            db=db,
            organization_id=org_id,
            user_id=user_id,
            match_id=match.id,
        )
        assert updated_inv.paid_amount == Decimal("0.00")
        assert updated_inv.due_amount == Decimal("400.00")
        assert updated_inv.status == InvoiceStatus.sent

    asyncio.run(run())


def test_routes_mapping_for_payments_and_matching():
    from app.api.v1.router import router

    endpoints = {(r.path, tuple(r.methods)): r.endpoint.__name__ for r in router.routes}
    assert endpoints.get(("/invoices/{invoice_id}/payments", ("POST",))) == "add_invoice_payment"
    assert endpoints.get(("/invoices/{invoice_id}/payments", ("GET",))) == "list_invoice_payments"
    assert endpoints.get(("/invoices/{invoice_id}/payments/{payment_id}", ("DELETE",))) == "remove_invoice_payment"
    assert endpoints.get(("/invoices/{invoice_id}/link-transaction", ("POST",))) == "link_transaction_route"
    assert endpoints.get(("/invoices/{invoice_id}/matches", ("GET",))) == "list_invoice_matches"
    assert endpoints.get(("/invoices/{invoice_id}/matches/{match_id}", ("DELETE",))) == "unlink_transaction_route"
    assert endpoints.get(("/invoices/{invoice_id}/linkable-transactions", ("GET",))) == "linkable_transactions_route"
    assert endpoints.get(("/banking/transactions/{transaction_id}/link-invoice", ("POST",))) == "banking_link_invoice"
    assert endpoints.get(("/banking/matches/{match_id}", ("DELETE",))) == "banking_unlink_match"


def test_cross_organization_payment_and_linking_blocked():
    org1 = uuid4()
    org2 = uuid4()
    user_id = uuid4()

    inv = Invoice(
        id=uuid4(),
        organization_id=org1,
        created_by=user_id,
        invoice_number="INV-ORG1",
        invoice_type=InvoiceType.outgoing,
        status=InvoiceStatus.sent,
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 10, 15),
        total=Decimal("100.00"),
        paid_amount=Decimal("0.00"),
    )
    tx = BankTransaction(
        id=uuid4(),
        organization_id=org2,  # Different organization
        account_id=uuid4(),
        provider_transaction_id="tx-org2",
        booked_at=datetime.now(timezone.utc),
        description="Foreign tx",
        amount=Decimal("100.00"),
        currency="DKK",
    )
    db = InMemoryDB([inv, tx])

    async def run():
        # Paying invoice from org2 should fail
        with pytest.raises(ValueError, match="Invoice not found"):
            await record_manual_payment(
                db=db,
                organization_id=org2,
                user_id=user_id,
                invoice_id=inv.id,
                amount=Decimal("50.00"),
            )

        # Linking transaction from org2 into org1 should fail because transaction belongs to org2
        with pytest.raises(ValueError, match="Bank transaction not found"):
            await link_invoice_to_transaction(
                db=db,
                organization_id=org1,
                user_id=user_id,
                invoice_id=inv.id,
                transaction_id=tx.id,
            )

    asyncio.run(run())

