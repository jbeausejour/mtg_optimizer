"""Add site_id to scan_result table

Revision ID: 38559da2e740
Revises: e91a6149916d
Create Date: 2024-07-03 16:43:21.547743

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '38559da2e740'
down_revision = 'e91a6149916d'
branch_labels = None
depends_on = None


def upgrade():
    # Create a new table with the desired schema
    op.create_table('new_scan_result',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scan_id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['scan_id'], ['scan.id'], ),
        sa.ForeignKeyConstraint(['card_id'], ['card.id'], ),
        sa.ForeignKeyConstraint(['site_id'], ['site.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Copy data from the old table to the new table
    op.execute('INSERT INTO new_scan_result (id, scan_id, card_id, price) SELECT id, scan_id, card_id, price FROM scan_result')
    
    # Drop the old table
    op.drop_table('scan_result')
    
    # Rename the new table to the original name
    op.rename_table('new_scan_result', 'scan_result')

def downgrade():
    op.drop_column('scan_result', 'site_id')
