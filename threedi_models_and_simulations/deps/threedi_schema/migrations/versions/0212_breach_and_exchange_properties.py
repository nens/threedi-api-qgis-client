"""add breach and exchange properties

Revision ID: 0212
Revises: 0211
Create Date: 2022-12-12 14:48:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0212"
down_revision = "0211"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("v2_exchange_line") as batch_op:
        batch_op.add_column(sa.Column("exchange_level", sa.Float(), nullable=True))
    with op.batch_alter_table("v2_potential_breach") as batch_op:
        batch_op.add_column(sa.Column("exchange_level", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("levee_material", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("maximum_breach_depth", sa.Float(), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("v2_exchange_line") as batch_op:
        batch_op.drop_column("exchange_level")
    with op.batch_alter_table("v2_potential_breach") as batch_op:
        batch_op.drop_column("exchange_level")
        batch_op.drop_column("levee_material")
        batch_op.drop_column("maximum_breach_depth")
