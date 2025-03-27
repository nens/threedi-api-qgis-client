"""rename vegetation columns

Revision ID: 0220
Revises: 0219
Create Date: 2024-02-02 12:53

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0220'
down_revision = '0219'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("v2_connection_nodes") as batch_op:
        batch_op.drop_column("the_geom_linestring")
    # Fix v2_connection_nodes table after dropping the_geom_linestring
    # Mostly copied from infrastructure.spatial_index._ensure_spatial_index
    op.execute(sa.text("SELECT RecoverGeometryColumn('v2_connection_nodes', 'the_geom', 4326, 'POINT', 'XY')"))
    op.execute(sa.text(f"DROP TABLE IF EXISTS idx_v2_connection_nodes_the_geom"))
    for prefix in {"gii_", "giu_", "gid_"}:
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {prefix}v2_connection_nodes_the_geom"))
    op.execute(sa.text("SELECT CreateSpatialIndex('v2_connection_nodes', 'the_geom')"))

def downgrade():
    with op.batch_alter_table("v2_connection_nodes") as batch_op:
        batch_op.add_column(sa.Column("the_geom_linestring", None))
