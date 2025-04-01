"""clean the tables associated with 1D-2D exchange

Revision ID: 0214
Revises: 0213
Create Date: 2022-12-22 11:42:00

"""
import sqlalchemy as sa
from alembic import op

from threedi_schema.domain.custom_types import Geometry

# revision identifiers, used by Alembic.
revision = "0214"
down_revision = "0213"
branch_labels = None
depends_on = None


LEVEE_TO_OBSTACLE = """
INSERT INTO v2_obstacle (code, crest_level, the_geom) SELECT code, crest_level, the_geom FROM v2_levee
"""

OBSTACLE_TO_LEVEE = """
INSERT INTO v2_levee (code, crest_level, the_geom) SELECT code, crest_level, the_geom FROM v2_obstacle
"""


def upgrade():
    op.execute(sa.text(LEVEE_TO_OBSTACLE))

    for table_name in ["v2_connected_pnt", "v2_calculation_point", "v2_levee"]:
        try:
            op.execute(sa.text(f"SELECT DropTable(NULL, '{table_name}')"))
        except sa.exc.OperationalError:
            op.execute(sa.text(f"SELECT DropGeoTable('{table_name}')"))
            op.execute(sa.text(f"DROP TABLE IF EXISTS '{table_name}'"))


def downgrade():
    op.create_table(
        "v2_levee",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=True),
        sa.Column("crest_level", sa.Float(), nullable=True),
        sa.Column("the_geom", Geometry("LINESTRING"), nullable=True),
        sa.Column("material", sa.Integer(), nullable=True),
        sa.Column("max_breach_depth", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "v2_calculation_point",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_type_id", sa.Integer(), nullable=True),
        sa.Column("user_ref", sa.String(length=80), nullable=True),
        sa.Column("calc_type", sa.Integer(), nullable=True),
        sa.Column("the_geom", Geometry("POINT"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "v2_connected_pnt",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("calculation_pnt_id", sa.Integer(), nullable=True),
        sa.Column("levee_id", sa.Integer(), nullable=True),
        sa.Column("exchange_level", sa.Float(), nullable=True),
        sa.Column("the_geom", Geometry("POINT"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
