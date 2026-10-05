"""Add organization products for invoice line presets

Revision ID: 0004_products
Revises: 0003_payments_and_matches
Create Date: 2026-10-05 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "0004_products"
down_revision = "0003_payments_and_matches"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "products",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_products_organization_id"), "products", ["organization_id"], unique=False)
    op.create_index(op.f("ix_products_name"), "products", ["name"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_products_name"), table_name="products")
    op.drop_index(op.f("ix_products_organization_id"), table_name="products")
    op.drop_table("products")
