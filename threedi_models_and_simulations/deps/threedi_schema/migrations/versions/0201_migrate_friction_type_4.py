"""Migration the old friction_type 4 to 2 (MANNING)

Revision ID: 0201
Revises:
Create Date: 2021-09-29 13:50:19.544275

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0201"
down_revision = "0200"
branch_labels = None
depends_on = None

TABLES = ("v2_cross_section_location", "v2_pipe", "v2_culvert", "v2_weir", "v2_orifice")
COLUMN_NAME = "friction_type"


def upgrade():
    for table_name in TABLES:
        upgrade_single_table(table_name)


def downgrade():
    pass


def upgrade_single_table(table_name):
    table = sa.table(
        table_name,
        sa.column("friction_type", sa.Integer),
    )
    op.execute(
        table.update()
        .where(table.c.friction_type == op.inline_literal(4))
        .values({"friction_type": op.inline_literal(2)})
    )
