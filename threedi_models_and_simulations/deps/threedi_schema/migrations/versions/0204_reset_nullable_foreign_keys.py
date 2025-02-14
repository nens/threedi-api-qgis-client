"""List nullable foreign keys and set them to NULL if they refer to a nonexisting object.

Revision ID: 0204
Revises:
Create Date: 2021-09-29 13:50:19.544275

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0204"
down_revision = "0203"
branch_labels = None
depends_on = None


NULLABLE_FOREIGN_KEYS = [
    {
        "table": "v2_global_settings",
        "column": "interflow_settings_id",
        "referring": "v2_interflow",
    },
    {
        "table": "v2_global_settings",
        "column": "control_group_id",
        "referring": "v2_control_group",
    },
    {
        "table": "v2_global_settings",
        "column": "simple_infiltration_settings_id",
        "referring": "v2_simple_infiltration",
    },
    {
        "table": "v2_global_settings",
        "column": "groundwater_settings_id",
        "referring": "v2_groundwater",
    },
    {
        "table": "v2_aggregation_settings",
        "column": "global_settings_id",
        "referring": "v2_global_settings",
    },
]


def upgrade():
    for fk in NULLABLE_FOREIGN_KEYS:
        upgrade_single(fk)


def upgrade_single(fk):
    """Replace non-existing ForeignKey references with NULL"""

    # construct dummy tables to be able to use the ORM
    table = sa.table(
        fk["table"],
        sa.column("id", sa.Integer),
        sa.column(fk["column"], sa.Integer),
    )
    referring = sa.table(
        fk["referring"],
        sa.column("id", sa.Integer),
    )
    column = getattr(table.c, fk["column"])

    # execute the query
    op.execute(
        table.update()
        .where(column.notin_(sa.orm.Query(referring)) & (column != None))
        .values({fk["column"]: sa.null()})
    )


def downgrade():
    pass
