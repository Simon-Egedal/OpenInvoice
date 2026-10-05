"""Invitations, password recovery and session revocation."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0008_account_recovery"
down_revision = "0007_delivery_and_approval"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("organization_members", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table("account_tokens", sa.Column("id", UUID(as_uuid=True), primary_key=True), sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("token_hash", sa.String(64), nullable=False, unique=True), sa.Column("purpose", sa.String(20), nullable=False), sa.Column("session_version", sa.Integer(), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("consumed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_account_tokens_organization_id", "account_tokens", ["organization_id"])
    op.create_index("ix_account_tokens_user_id", "account_tokens", ["user_id"])


def downgrade():
    op.drop_table("account_tokens")
    op.drop_column("organization_members", "is_active")
    op.drop_column("users", "session_version")
