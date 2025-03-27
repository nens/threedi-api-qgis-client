"""fix schema constraints

Revision ID: 0208
Revises: 0207
Create Date: 2022-09-19 16:17

"""
from alembic import op

import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0208"
down_revision = "0207"
branch_labels = None
depends_on = None


def upgrade():
    # First alter the tables to nullable TEXT, because we need to be able to
    # accept any value
    with op.batch_alter_table("v2_global_settings") as batch_op:
        batch_op.add_column(
            sa.Column("maximum_table_step_size", sa.Float(), nullable=True)
        )
        batch_op.drop_column("table_step_size_volume_2d")


def downgrade():
    pass
