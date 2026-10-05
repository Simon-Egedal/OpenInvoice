"""Add logo_key to organizations table

Revision ID: 0002_add_organization_logo
Revises: 0001_initial
Create Date: 2026-10-05 08:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '0002_add_organization_logo'
down_revision = '0001_initial'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('organizations', sa.Column('logo_key', sa.String(length=500), nullable=True))

def downgrade():
    op.drop_column('organizations', 'logo_key')
