"""Carry organization identity on invoice lines."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0010_line_tenant_scope"
down_revision = "0009_issued_status"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("invoice_lines", sa.Column("organization_id", UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE invoice_lines SET organization_id=invoices.organization_id FROM invoices WHERE invoices.id=invoice_lines.invoice_id")
    op.alter_column("invoice_lines", "organization_id", nullable=False)
    op.create_foreign_key("fk_invoice_lines_organization", "invoice_lines", "organizations", ["organization_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_invoice_lines_organization_id", "invoice_lines", ["organization_id"])


def downgrade():
    op.drop_index("ix_invoice_lines_organization_id", table_name="invoice_lines")
    op.drop_constraint("fk_invoice_lines_organization", "invoice_lines", type_="foreignkey")
    op.drop_column("invoice_lines", "organization_id")
