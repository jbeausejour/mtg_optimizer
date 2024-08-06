"""Add set to release_date

Revision ID: c53d61935dff
Revises: 9ae68ac05cee
Create Date: 2024-07-25 15:37:07.737834

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c53d61935dff'
down_revision = '9ae68ac05cee'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('sets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_updated', sa.DateTime(), nullable=True))
        batch_op.alter_column('id',
               existing_type=sa.INTEGER(),
               nullable=False,
               autoincrement=True)
        batch_op.alter_column('set_type',
               existing_type=sa.VARCHAR(length=50),
               nullable=False)
        batch_op.alter_column('is_digital',
               existing_type=sa.INTEGER(),
               type_=sa.Boolean(),
               existing_nullable=True,
               existing_server_default=sa.text('0'))
        batch_op.create_unique_constraint('uq_sets_set_code', ['set_code'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('sets', schema=None) as batch_op:
        batch_op.drop_constraint('uq_sets_set_code', type_='unique')
        batch_op.alter_column('is_digital',
               existing_type=sa.Boolean(),
               type_=sa.INTEGER(),
               existing_nullable=True,
               existing_server_default=sa.text('0'))
        batch_op.alter_column('set_type',
               existing_type=sa.VARCHAR(length=50),
               nullable=True)
        batch_op.alter_column('id',
               existing_type=sa.INTEGER(),
               nullable=True,
               autoincrement=True)
        batch_op.drop_column('last_updated')

    # ### end Alembic commands ###