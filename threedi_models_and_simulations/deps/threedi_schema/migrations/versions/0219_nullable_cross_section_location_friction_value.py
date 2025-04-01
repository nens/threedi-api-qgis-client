"""rename vegetation columns

Revision ID: 0219
Revises: 0218
Create Date: 2024-01-22 15:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0219'
down_revision = '0218'
branch_labels = None
depends_on = None

MIGRATION_QUERIES = """
SELECT RecoverGeometryColumn('v2_cross_section_location', 'the_geom', 4326, 'POINT', 'XY')
"""


def upgrade():
    with op.batch_alter_table("v2_cross_section_location") as batch_op:
        batch_op.alter_column("friction_value", nullable=True, type_=sa.FLOAT)
    for q in MIGRATION_QUERIES.split(";"):
        op.execute(sa.text(q))


def downgrade():
    with op.batch_alter_table("v2_cross_section_location") as batch_op:
        batch_op.alter_column("friction_value", nullable=False, type_=sa.Float)
