"""Durable deliveries and invoice approval decisions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0007_delivery_and_approval"
down_revision = "0006_invoice_reliability"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("email_deliveries", "invoice_id", existing_type=UUID(as_uuid=True), nullable=True)
    for column in [sa.Column("kind", sa.String(20), nullable=False, server_default="invoice"), sa.Column("idempotency_key", sa.String(200)), sa.Column("encrypted_payload", sa.Text()), sa.Column("next_attempt_at", sa.DateTime(timezone=True)), sa.Column("started_at", sa.DateTime(timezone=True))]:
        op.add_column("email_deliveries", column)
    # Old nonterminal records did not contain a durable message. Do not send them automatically.
    op.execute("UPDATE email_deliveries SET status='uncertain' WHERE status IN ('queued','sending','failed')")
    op.create_index("ix_email_deliveries_next_attempt_at", "email_deliveries", ["next_attempt_at"])
    op.create_unique_constraint("uq_delivery_request", "email_deliveries", ["organization_id", "idempotency_key"])
    op.create_table("invoice_decisions", sa.Column("id", UUID(as_uuid=True), primary_key=True), sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False), sa.Column("invoice_id", UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False), sa.Column("decision", sa.String(30), nullable=False), sa.Column("reason", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_invoice_decisions_organization_id", "invoice_decisions", ["organization_id"])
    op.create_index("ix_invoice_decisions_invoice_id", "invoice_decisions", ["invoice_id"])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT 1 FROM email_deliveries WHERE invoice_id IS NULL LIMIT 1")).first():
        raise RuntimeError("Cannot downgrade while account deliveries exist; archive the outbox before removing account-message support.")
    op.drop_table("invoice_decisions")
    op.drop_constraint("uq_delivery_request", "email_deliveries", type_="unique")
    op.drop_index("ix_email_deliveries_next_attempt_at", table_name="email_deliveries")
    for name in ["started_at", "next_attempt_at", "encrypted_payload", "idempotency_key", "kind"]:
        op.drop_column("email_deliveries", name)
    # Account messages cannot be represented by the old schema.
    op.alter_column("email_deliveries", "invoice_id", existing_type=UUID(as_uuid=True), nullable=False)
