"""rename vegetation columns

Revision ID: 0218
Revises: 0217
Create Date: 2023-12-22 08:33

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0218'
down_revision = '0217'
branch_labels = None
depends_on = None

LOC_COLUMNS = (
    "vegetation_stem_density",
    "vegetation_stem_diameter",
    "vegetation_height",
    "vegetation_drag_coefficient",
    "vegetation_drag_coeficients"
)

DEF_COLUMNS = (
    "friction_values",
    "vegetation_stem_densities",
    "vegetation_stem_diameters",
    "vegetation_heights",
    "vegetation_drag_coefficients"
)


def upgrade():
    with op.batch_alter_table("v2_cross_section_location") as batch_op:
        for column in LOC_COLUMNS:
            batch_op.add_column(sa.Column(column, sa.Float()))
    with op.batch_alter_table("v2_cross_section_definition") as batch_op:
        for column in DEF_COLUMNS:
            batch_op.add_column(sa.Column(column, sa.String()))


def downgrade():
    with op.batch_alter_table("v2_cross_section_location") as batch_op:
        for column in LOC_COLUMNS:
            batch_op.drop_column(column)
    with op.batch_alter_table("v2_cross_section_definition") as batch_op:
        for column in DEF_COLUMNS:
            batch_op.drop_column(column)
