"""Store bank transaction credit or debit direction

Revision ID: 0005_transaction_direction
Revises: 0004_products
Create Date: 2026-10-05 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "0005_transaction_direction"
down_revision = "0004_products"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("bank_transactions", sa.Column("direction", sa.String(length=10), nullable=True))
    op.execute("UPDATE bank_transactions SET direction = CASE WHEN amount < 0 THEN 'debit' ELSE 'credit' END")
    op.alter_column("bank_transactions", "direction", nullable=False, server_default="credit")


def downgrade():
    op.drop_column("bank_transactions", "direction")
