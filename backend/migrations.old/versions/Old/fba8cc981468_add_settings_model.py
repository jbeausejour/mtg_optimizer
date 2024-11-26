"""Add Settings model

Revision ID: fba8cc981468
Revises: consolidated_migration
Create Date: 2024-09-13 14:49:43.825253

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "fba8cc981468"
down_revision = "consolidated_migration"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    with op.batch_alter_table("scan", schema=None) as batch_op:
        batch_op.alter_column("created_at", existing_type=sa.DATETIME(), nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("scan", schema=None) as batch_op:
        batch_op.alter_column("created_at", existing_type=sa.DATETIME(), nullable=False)

    op.drop_table("settings")
    # ### end Alembic commands ###