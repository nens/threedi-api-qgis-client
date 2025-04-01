"""global raster values

Revision ID: 0210
Revises: 0209
Create Date: 2022-11-08 16:37

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0210"
down_revision = "0209"
branch_labels = None
depends_on = None


MIGRATION_QUERIES = """
UPDATE v2_interflow SET hydraulic_conductivity = NULL WHERE hydraulic_conductivity < 0;
UPDATE v2_groundwater SET initial_infiltration_rate = NULL WHERE initial_infiltration_rate < 0;
UPDATE v2_groundwater SET equilibrium_infiltration_rate = NULL WHERE equilibrium_infiltration_rate < 0;
UPDATE v2_groundwater SET infiltration_decay_period = NULL WHERE infiltration_decay_period <= 0;
UPDATE v2_groundwater SET groundwater_hydro_connectivity = NULL WHERE groundwater_hydro_connectivity < 0;
"""


def upgrade():
    for q in MIGRATION_QUERIES.split(";"):
        op.execute(sa.text(q))

    with op.batch_alter_table("v2_simple_infiltration") as batch_op:
        batch_op.add_column(
            sa.Column("max_infiltration_capacity", sa.Float(), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("v2_simple_infiltration") as batch_op:
        batch_op.drop_column("max_infiltration_capacity")
