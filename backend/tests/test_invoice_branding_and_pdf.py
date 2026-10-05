from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4
import pytest
from PIL import Image

from app.api.v1.router import (
    attach_organization_metadata,
    attach_organization_metadata_list,
    make_pdf,
)
from app.models.entities import Invoice, InvoiceStatus, InvoiceType, Organization
from app.schemas import InvoiceOut


def test_make_pdf_with_org_name_no_logo():
    inv = SimpleNamespace(
        invoice_number="INV-2026-0001",
        issue_date=date(2026, 10, 5),
        due_date=date(2026, 10, 19),
        subtotal=Decimal("500.00"),
        tax_amount=Decimal("125.00"),
        total=Decimal("625.00"),
        currency="DKK",
        notes="Payment within 14 days",
    )
    lines = [
        SimpleNamespace(
            description="Consulting Services",
            quantity=Decimal("5"),
            unit_price=Decimal("100.00"),
            line_total=Decimal("500.00"),
        )
    ]
    pdf = make_pdf(inv, lines, org_name="Nordic Solutions ApS")
    assert pdf.startswith(b"%PDF-")
    assert b"Nordic Solutions ApS" in pdf


def test_make_pdf_with_org_name_and_logo():
    img = Image.new("RGBA", (120, 40), color=(37, 107, 83, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    logo_bytes = buf.getvalue()

    inv = SimpleNamespace(
        invoice_number="INV-2026-0002",
        issue_date=date(2026, 10, 5),
        due_date=date(2026, 10, 19),
        subtotal=Decimal("200.00"),
        tax_amount=Decimal("50.00"),
        total=Decimal("250.00"),
        currency="DKK",
        notes=None,
    )
    lines = [
        SimpleNamespace(
            description="Software License",
            quantity=Decimal("1"),
            unit_price=Decimal("200.00"),
            line_total=Decimal("200.00"),
        )
    ]
    org = SimpleNamespace(name="Branded Enterprise A/S")
    pdf = make_pdf(inv, lines, org=org, logo_bytes=logo_bytes)
    assert pdf.startswith(b"%PDF-")
    assert b"Branded Enterprise A/S" in pdf


def test_make_pdf_fallback_no_org():
    inv = SimpleNamespace(
        invoice_number="INV-2026-0003",
        issue_date=date(2026, 10, 5),
        due_date=date(2026, 10, 19),
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("25.00"),
        total=Decimal("125.00"),
        currency="DKK",
        notes=None,
    )
    lines = [
        SimpleNamespace(
            description="Item",
            quantity=Decimal("1"),
            unit_price=Decimal("100.00"),
            line_total=Decimal("100.00"),
        )
    ]
    pdf = make_pdf(inv, lines)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 500


@pytest.mark.anyio
async def test_attach_organization_metadata():
    org_id = uuid4()
    org = Organization(
        id=org_id,
        name="Global Logistics ApS",
        country="DK",
        currency="DKK",
        logo_key="logos/global.png",
    )
    inv = Invoice(
        id=uuid4(),
        organization_id=org_id,
        created_by=uuid4(),
        invoice_number="INV-2026-0010",
        invoice_type=InvoiceType.outgoing,
        status=InvoiceStatus.draft,
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 10, 15),
        currency="DKK",
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("25.00"),
        total=Decimal("125.00"),
        paid_amount=Decimal("0.00"),
        created_at=datetime.now(timezone.utc),
    )

    class MockDB:
        async def scalar(self, stmt):
            return org

    await attach_organization_metadata(MockDB(), inv)
    assert getattr(inv, "organization_name") == "Global Logistics ApS"
    assert getattr(inv, "organization_logo_url") == f"/organizations/{org_id}/logo"

    # Verify InvoiceOut serializes it
    out = InvoiceOut.model_validate(inv)
    assert out.organization_name == "Global Logistics ApS"
    assert out.organization_logo_url == f"/organizations/{org_id}/logo"
    assert out.organization_id == org_id


@pytest.mark.anyio
async def test_attach_organization_metadata_list():
    org_id = uuid4()
    org = Organization(
        id=org_id,
        name="Global Logistics ApS",
        country="DK",
        currency="DKK",
        logo_key=None,
    )
    inv1 = Invoice(
        id=uuid4(),
        organization_id=org_id,
        created_by=uuid4(),
        invoice_number="INV-2026-0011",
        invoice_type=InvoiceType.outgoing,
        status=InvoiceStatus.draft,
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 10, 15),
        currency="DKK",
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("25.00"),
        total=Decimal("125.00"),
    )

    class MockDB:
        async def scalar(self, stmt):
            return org

    await attach_organization_metadata_list(MockDB(), [inv1], org_id)
    assert getattr(inv1, "organization_name") == "Global Logistics ApS"
    assert getattr(inv1, "organization_logo_url") is None


def test_make_pdf_with_recipient_info():
    inv = SimpleNamespace(
        invoice_number="INV-2026-0099",
        invoice_type="outgoing",
        issue_date=date(2026, 10, 5),
        due_date=date(2026, 10, 19),
        subtotal=Decimal("1500.00"),
        tax_amount=Decimal("375.00"),
        total=Decimal("1875.00"),
        currency="DKK",
        notes="Net 14 days",
    )
    lines = [
        SimpleNamespace(
            description="Enterprise Cloud Architecture",
            quantity=Decimal("15"),
            unit_price=Decimal("100.00"),
            line_total=Decimal("1500.00"),
        )
    ]
    org = SimpleNamespace(name="CloudCorp ApS")
    recipient = SimpleNamespace(
        name="Stark Industries ApS",
        address="Innovationsvej 42",
        postal_code="2100",
        city="Copenhagen",
        country="DK",
        vat_number="DK99887766",
        email="billing@stark.dk",
        phone="+45 12 34 56 78",
    )
    pdf = make_pdf(inv, lines, org=org, recipient=recipient)
    assert pdf.startswith(b"%PDF-")
    assert b"CloudCorp ApS" in pdf
    assert b"BILLED TO" in pdf
    assert b"Stark Industries ApS" in pdf
    assert b"Innovationsvej 42" in pdf
    assert b"2100 Copenhagen, DK" in pdf
    assert b"VAT: DK99887766" in pdf
    assert b"billing@stark.dk" in pdf


@pytest.mark.anyio
async def test_attach_metadata_with_recipient():
    from app.models.entities import Customer
    org_id = uuid4()
    cust_id = uuid4()
    org = Organization(
        id=org_id,
        name="Org With Customer",
        country="DK",
        currency="DKK",
    )
    customer = Customer(
        id=cust_id,
        organization_id=org_id,
        name="Client Alpha A/S",
        email="ap@clientalpha.com",
        phone="+45 88 88 88 88",
        address="Vestergade 10",
        postal_code="8000",
        city="Aarhus",
        country="DK",
        vat_number="DK11223344",
    )
    inv = Invoice(
        id=uuid4(),
        organization_id=org_id,
        customer_id=cust_id,
        created_by=uuid4(),
        invoice_number="INV-2026-0100",
        invoice_type=InvoiceType.outgoing,
        status=InvoiceStatus.draft,
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 10, 15),
        currency="DKK",
        subtotal=Decimal("500.00"),
        tax_amount=Decimal("125.00"),
        total=Decimal("625.00"),
        paid_amount=Decimal("0.00"),
        created_at=datetime.now(timezone.utc),
    )

    class MockDB:
        async def scalar(self, stmt):
            sql = str(stmt).lower()
            if "organizations" in sql:
                return org
            if "customers" in sql:
                return customer
            return None

    await attach_organization_metadata(MockDB(), inv)
    assert getattr(inv, "organization_name") == "Org With Customer"
    assert getattr(inv, "recipient_name") == "Client Alpha A/S"
    assert getattr(inv, "recipient_email") == "ap@clientalpha.com"
    assert getattr(inv, "recipient_vat_number") == "DK11223344"

    out = InvoiceOut.model_validate(inv)
    assert out.organization_name == "Org With Customer"
    assert out.recipient_name == "Client Alpha A/S"
    assert out.recipient_email == "ap@clientalpha.com"
    assert out.recipient_address == "Vestergade 10"
    assert out.recipient_vat_number == "DK11223344"

