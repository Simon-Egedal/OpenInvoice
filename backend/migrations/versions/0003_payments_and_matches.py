"""Add payments and transaction matching amount

Revision ID: 0003_payments_and_matches
Revises: 0002_add_organization_logo
Create Date: 2026-10-05 10:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '0003_payments_and_matches'
down_revision = '0002_add_organization_logo'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('invoices', sa.Column('paid_amount', sa.Numeric(precision=14, scale=2), server_default='0.00', nullable=False))
    op.add_column('invoice_transaction_matches', sa.Column('amount', sa.Numeric(precision=14, scale=2), server_default='0.00', nullable=False))
    
    op.create_index(op.f('ix_invoice_transaction_matches_invoice_id'), 'invoice_transaction_matches', ['invoice_id'], unique=False)
    op.create_index(op.f('ix_invoice_transaction_matches_transaction_id'), 'invoice_transaction_matches', ['transaction_id'], unique=False)

    op.create_table(
        'invoice_payments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('invoice_id', sa.UUID(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('payment_date', sa.Date(), nullable=False),
        sa.Column('payment_method', sa.String(length=50), server_default='manual', nullable=False),
        sa.Column('reference', sa.String(length=200), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_invoice_payments_organization_id'), 'invoice_payments', ['organization_id'], unique=False)
    op.create_index(op.f('ix_invoice_payments_invoice_id'), 'invoice_payments', ['invoice_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_invoice_payments_invoice_id'), table_name='invoice_payments')
    op.drop_index(op.f('ix_invoice_payments_organization_id'), table_name='invoice_payments')
    op.drop_table('invoice_payments')

    op.drop_index(op.f('ix_invoice_transaction_matches_transaction_id'), table_name='invoice_transaction_matches')
    op.drop_index(op.f('ix_invoice_transaction_matches_invoice_id'), table_name='invoice_transaction_matches')

    op.drop_column('invoice_transaction_matches', 'amount')
    op.drop_column('invoices', 'paid_amount')
