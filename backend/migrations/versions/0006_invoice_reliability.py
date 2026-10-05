"""Invoice identities, seller details, preserved issue documents and match uniqueness."""
from alembic import op
import sqlalchemy as sa

revision = "0006_invoice_reliability"
down_revision = "0005_transaction_direction"
branch_labels = None
depends_on = None


def upgrade():
    # Never silently rewrite financial identities or discard duplicate allocations.
    connection = op.get_bind()
    for query, label in [
        ("SELECT 1 FROM invoices WHERE invoice_type='outgoing' GROUP BY organization_id, invoice_number HAVING count(*) > 1", "outgoing invoice numbers"),
        ("SELECT 1 FROM invoices WHERE invoice_type='incoming' GROUP BY organization_id, supplier_id, invoice_number HAVING count(*) > 1", "supplier invoice numbers"),
        ("SELECT 1 FROM invoice_transaction_matches GROUP BY organization_id, invoice_id, transaction_id HAVING count(*) > 1", "transaction matches"),
    ]:
        if connection.execute(sa.text(query)).first():
            raise RuntimeError(f"Resolve duplicate {label} before applying migration 0006; no records were changed.")
    for name, kind in [("address", sa.String(300)), ("postal_code", sa.String(30)), ("city", sa.String(100)), ("vat_number", sa.String(80)), ("payment_information", sa.Text()), ("payment_terms", sa.Text())]:
        op.add_column("organizations", sa.Column(name, kind, nullable=True))
    op.add_column("organizations", sa.Column("invoice_prefix", sa.String(20), nullable=False, server_default="INV"))
    op.add_column("organizations", sa.Column("next_invoice_number", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("invoices", sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoices", sa.Column("issued_snapshot", sa.JSON(), nullable=True))
    op.add_column("invoices", sa.Column("issued_pdf_key", sa.String(500), nullable=True))
    op.add_column("invoice_lines", sa.Column("position", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("uq_outgoing_number", "invoices", ["organization_id", "invoice_number"], unique=True, postgresql_where=sa.text("invoice_type = 'outgoing'"))
    op.create_index("uq_supplier_invoice_number", "invoices", ["organization_id", "supplier_id", "invoice_number"], unique=True, postgresql_where=sa.text("invoice_type = 'incoming'"))
    op.create_unique_constraint("uq_invoice_transaction", "invoice_transaction_matches", ["organization_id", "invoice_id", "transaction_id"])


def downgrade():
    op.drop_constraint("uq_invoice_transaction", "invoice_transaction_matches", type_="unique")
    op.drop_index("uq_supplier_invoice_number", table_name="invoices")
    op.drop_index("uq_outgoing_number", table_name="invoices")
    op.drop_column("invoice_lines", "position")
    for name in ["issued_pdf_key", "issued_snapshot", "issued_at"]:
        op.drop_column("invoices", name)
    for name in ["next_invoice_number", "invoice_prefix", "payment_terms", "payment_information", "vat_number", "city", "postal_code", "address"]:
        op.drop_column("organizations", name)
