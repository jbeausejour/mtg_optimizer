"""Recreate Sets table with new structure

Revision ID: 0e4819adbdb2
Revises: c53d61935dff
Create Date: 2024-08-05 14:37:52.084780

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0e4819adbdb2'
down_revision = 'c53d61935dff'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the old table
    op.drop_table('sets')

    # Create the new table with the updated structure
    op.create_table('sets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('tcgplayer_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('uri', sa.String(length=255), nullable=True),
        sa.Column('scryfall_uri', sa.String(length=255), nullable=True),
        sa.Column('search_uri', sa.String(length=255), nullable=True),
        sa.Column('released_at', sa.Date(), nullable=True),
        sa.Column('set_type', sa.String(length=50), nullable=True),
        sa.Column('card_count', sa.Integer(), nullable=True),
        sa.Column('printed_size', sa.Integer(), nullable=True),
        sa.Column('digital', sa.Boolean(), nullable=True),
        sa.Column('nonfoil_only', sa.Boolean(), nullable=True),
        sa.Column('foil_only', sa.Boolean(), nullable=True),
        sa.Column('icon_svg_uri', sa.String(length=255), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_sets_code')
    )


def downgrade():
    # Drop the new table
    op.drop_table('sets')

    # Recreate the old table structure
    op.create_table('sets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('set_name', sa.String(length=255), nullable=False),
        sa.Column('set_code', sa.String(length=10), nullable=False),
        sa.Column('set_symbol', sa.String(length=50), nullable=True),
        sa.Column('set_type', sa.String(length=50), nullable=False),
        sa.Column('release_date', sa.Date(), nullable=True),
        sa.Column('card_count', sa.Integer(), nullable=True),
        sa.Column('is_digital', sa.Boolean(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('set_code', name='uq_sets_set_code')
    )