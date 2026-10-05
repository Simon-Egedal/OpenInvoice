"""Distinguish invoice issuance from email acceptance."""
from alembic import op

revision = "0009_issued_status"
down_revision = "0008_account_recovery"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE invoice_status ADD VALUE IF NOT EXISTS 'issued'")


def downgrade():
    # PostgreSQL does not support removing an enum value in place.
    op.execute("UPDATE invoices SET status='sent' WHERE status='issued'")
