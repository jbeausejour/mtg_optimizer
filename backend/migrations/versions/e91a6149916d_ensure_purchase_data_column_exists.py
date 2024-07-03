"""Ensure purchase_data column exists

Revision ID: e91a6149916d
Revises: 8b64deac896f
Create Date: 2024-07-03 16:22:02.779160

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e91a6149916d'
down_revision = '8b64deac896f'
branch_labels = None
depends_on = None


def upgrade():
   # Check if the column exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = inspector.get_columns('card_data')
    column_names = [c['name'] for c in columns]
    
    if 'purchase_data' not in column_names:
        op.add_column('card_data', sa.Column('purchase_data', sa.JSON(), nullable=True))


def downgrade():
    pass
