"""remove vegetation_drag_coeficients column

Revision ID: 0221
Revises: 0220
Create Date: 2024-02-04

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0221'
down_revision = '0220'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("v2_cross_section_location") as batch_op:
        batch_op.drop_column("vegetation_drag_coeficients")
    op.execute(sa.text("SELECT RecoverGeometryColumn('v2_cross_section_location', 'the_geom', 4326, 'POINT', 'XY')"))


def downgrade():
    # No downgrade implemented because vegetation_drag_coeficients should
    # never have been addd to v2_cross_section_location
    pass
