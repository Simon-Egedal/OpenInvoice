"""PDF rendering using flowing tables, wrapped text and repeated page headers."""
from html import escape
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def value(obj, name, default=None):
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


def make_pdf(invoice, lines, org=None, logo_bytes=None, org_name=None, recipient=None):
    output = BytesIO()
    styles = getSampleStyleSheet()
    styles["Normal"].fontSize = 9
    styles["Normal"].leading = 12
    def paragraph(text, style="Normal"):
        return Paragraph(escape(str(text or "")).replace("\n", "<br/>"), styles[style])
    story = [paragraph("INVOICE", "Title"), paragraph(invoice.invoice_number, "Heading2")]
    if logo_bytes:
        try:
            logo = Image(BytesIO(logo_bytes))
            ratio = min(140 / logo.imageWidth, 50 / logo.imageHeight)
            logo.drawWidth = logo.imageWidth * ratio
            logo.drawHeight = logo.imageHeight * ratio
            logo.hAlign = "RIGHT"
            story.append(logo)
        except Exception:
            pass
    story.append(paragraph(org_name or value(org, "name") or value(invoice, "organization_name") or ""))
    for name in ("address", "vat_number"):
        text = value(org, name)
        if text:
            story.append(paragraph(f"VAT: {text}" if name == "vat_number" else text))
    city = " ".join(filter(None, [value(org, "postal_code"), value(org, "city")]))
    if city:
        story.append(paragraph(city))
    story.extend([Spacer(1, 12), paragraph(f"Issue date {invoice.issue_date}     Due date {invoice.due_date}")])
    if recipient is None and value(invoice, "recipient_name"):
        recipient = {name: value(invoice, f"recipient_{name}") for name in ("name", "address", "postal_code", "city", "country", "vat_number", "email", "phone")}
    if recipient:
        kind = value(invoice, "invoice_type", "outgoing")
        story.extend([Spacer(1, 12), paragraph("BILLED TO" if kind == "outgoing" else "SUPPLIER", "Heading3")])
        for name in ("name", "address"):
            if value(recipient, name):
                story.append(paragraph(value(recipient, name)))
        city = " ".join(filter(None, [value(recipient, "postal_code"), value(recipient, "city")]))
        city_country = ", ".join(filter(None, [city, value(recipient, "country")]))
        if city_country:
            story.append(paragraph(city_country))
        if value(recipient, "vat_number"):
            story.append(paragraph(f"VAT: {value(recipient, 'vat_number')}"))
        for name in ("email", "phone"):
            if value(recipient, name):
                story.append(paragraph(value(recipient, name)))
    story.append(Spacer(1, 18))
    rows = [[paragraph(text) for text in ("DESCRIPTION", "QTY", "PRICE", "VAT %", "TOTAL")]]
    for line in lines:
        rows.append([paragraph(line.description), paragraph(str(line.quantity)), paragraph(f"{line.unit_price:.2f}"), paragraph(str(value(line, "tax_rate", ""))), paragraph(f"{line.line_total:.2f}")])
    table = Table(rows, colWidths=[255, 40, 65, 45, 70], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), .5, colors.HexColor("#cccccc")), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story.extend([table, Spacer(1, 14)])
    for label, amount in [("Subtotal", invoice.subtotal), ("VAT", invoice.tax_amount), ("Total", invoice.total)]:
        story.append(paragraph(f"{label}: {invoice.currency} {amount:.2f}"))
    for label, text in [("Payment information", value(org, "payment_information")), ("Payment terms", value(org, "payment_terms")), ("Notes", value(invoice, "notes"))]:
        if text:
            story.extend([Spacer(1, 10), paragraph(label, "Heading3"), paragraph(text)])
    def footer(canvas, document):
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(A4[0] - 48, 25, f"Page {document.page}")
    SimpleDocTemplate(output, pagesize=A4, leftMargin=48, rightMargin=48, topMargin=42, bottomMargin=42, pageCompression=0).build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
