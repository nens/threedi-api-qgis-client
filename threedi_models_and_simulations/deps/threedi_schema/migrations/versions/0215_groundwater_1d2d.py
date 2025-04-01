"""groundwater 1d2d

Revision ID: 0215
Revises: 0214
Create Date: 2023-02-06 10:11

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0215"
down_revision = "0214"
branch_labels = None
depends_on = None

TABLES = ("v2_channel", "v2_pipe", "v2_manhole")
COLUMNS = (
    "exchange_thickness",
    "hydraulic_conductivity_in",
    "hydraulic_conductivity_out",
)


def upgrade():
    for table in TABLES:
        with op.batch_alter_table(table) as batch_op:
            for column in COLUMNS:
                batch_op.add_column(sa.Column(column, sa.Float(), nullable=True))


def downgrade():
    for table in TABLES:
        with op.batch_alter_table(table) as batch_op:
            for column in COLUMNS:
                batch_op.drop_column(column)
