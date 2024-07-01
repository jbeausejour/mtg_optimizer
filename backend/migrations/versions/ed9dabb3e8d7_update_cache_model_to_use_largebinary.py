"""Update Cache model to use LargeBinary

Revision ID: ed9dabb3e8d7
Revises: 23f77955d485
Create Date: 2024-07-01 16:56:13.603671

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ed9dabb3e8d7'
down_revision = '23f77955d485'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('cache', schema=None) as batch_op:
        batch_op.alter_column('value',
               existing_type=sa.TEXT(),
               type_=sa.LargeBinary(),
               existing_nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('cache', schema=None) as batch_op:
        batch_op.alter_column('value',
               existing_type=sa.LargeBinary(),
               type_=sa.TEXT(),
               existing_nullable=True)

    # ### end Alembic commands ###
