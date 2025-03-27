"""fix schema constraints

Revision ID: 0207
Revises: 0206
Create Date: 2022-05-18 10:15:20.851968

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0207"
down_revision = "0206"
branch_labels = None
depends_on = None


MIGRATION_QUERIES = """
DELETE FROM v2_grid_refinement WHERE (refinement_level IS NULL) OR (the_geom IS NULL);

DELETE FROM v2_grid_refinement_area WHERE (refinement_level IS NULL) OR (the_geom IS NULL);

UPDATE v2_orifice SET sewerage = NULL WHERE sewerage NOT IN (0, 1);
UPDATE v2_pumpstation SET sewerage = NULL WHERE sewerage NOT IN (0, 1);
UPDATE v2_weir SET sewerage = NULL WHERE sewerage NOT IN (0, 1);

UPDATE v2_weir SET external = NULL WHERE external NOT IN (0, 1);

DROP TRIGGER IF EXISTS ggi_v2_connection_nodes_the_geom;
DROP TRIGGER IF EXISTS ggu_v2_connection_nodes_the_geom;
DROP TRIGGER IF EXISTS ggi_v2_connection_nodes_the_geom_linestring;
DROP TRIGGER IF EXISTS ggu_v2_connection_nodes_the_geom_linestring;
UPDATE v2_connection_nodes SET the_geom_linestring = NULL;
"""


def upgrade():
    # First alter the tables to nullable TEXT, because we need to be able to
    # accept any value
    with op.batch_alter_table("v2_orifice") as batch_op:
        batch_op.alter_column("sewerage", nullable=True, type_=sa.TEXT)

    with op.batch_alter_table("v2_pumpstation") as batch_op:
        batch_op.alter_column("sewerage", nullable=True, type_=sa.TEXT)

    with op.batch_alter_table("v2_weir") as batch_op:
        batch_op.alter_column("sewerage", nullable=True, type_=sa.TEXT)
        batch_op.alter_column("external", nullable=True, type_=sa.TEXT)

    for q in MIGRATION_QUERIES.split(";"):
        op.execute(q)

    # After the data migration; alter the tables to nullable BOOLEAN
    with op.batch_alter_table("v2_orifice") as batch_op:
        batch_op.alter_column("sewerage", nullable=True, type_=sa.BOOLEAN)

    with op.batch_alter_table("v2_pumpstation") as batch_op:
        batch_op.alter_column("sewerage", nullable=True, type_=sa.BOOLEAN)

    with op.batch_alter_table("v2_weir") as batch_op:
        batch_op.alter_column("sewerage", nullable=True, type_=sa.BOOLEAN)
        batch_op.alter_column("external", nullable=True, type_=sa.BOOLEAN)


def downgrade():
    pass
