"""Removed unused columns.

Revision ID: 0203
Revises:
Create Date: 2021-09-29 13:50:19.544275

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0203"
down_revision = "0202"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("v2_aggregation_settings") as batch_op:
        batch_op.drop_column("aggregation_in_space")


def downgrade():
    with op.batch_alter_table("v2_aggregation_settings") as batch_op:
        batch_op.add_column(
            sa.Column("aggregation_in_space", sa.Boolean(), nullable=False),
        )
