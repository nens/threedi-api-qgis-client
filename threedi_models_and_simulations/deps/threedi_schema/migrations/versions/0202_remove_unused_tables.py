"""Removed unused v1 tables.

Revision ID: 0202
Revises:
Create Date: 2021-09-29 13:50:19.544275

"""
import re

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision = "0202"
down_revision = "0201"
branch_labels = None
depends_on = None


V1_TABLES = [
    "boundary_line",
    "boundary_line_chk",
    "boundary_point",
    "boundary_point_chk",
    "bridge",
    "bridge_chk",
    "channel",
    "channel_chk",
    "check_boundary_nodes",
    "cross_section",
    "cross_section_chk",
    "cross_section_definition",
    "cross_section_definition_chk",
    "culvert",
    "culvert_chk",
    "floodfill",
    "global_settings",
    "grid_refinement",
    "initial_waterlevel",
    "initial_waterlevel_chk",
    "lateral",
    "lateral_chk",
    "levee",
    "levee_chk",
    "manhole_2d",
    "manhole_2d_chk",
    "orifice",
    "orifice_chk",
    "potential_cross_section",
    "pumped_drainage_area",
    "pumped_drainage_area_chk",
    "pumpstation",
    "pumpstation_chk",
    "qualitycheckresult",
    "rain_event",
    "settings",
    "sewerage_boundary_conditions",
    "sewerage_boundary_conditions_chk",
    "sewerage_cross_section_definition",
    "sewerage_cross_section_definition_chk",
    "sewerage_impervious_surface",
    "sewerage_impervious_surface_chk",
    "sewerage_impervious_surface",
    "sewerage_impervious_surface_pipe_map",
    "sewerage_lateral",
    "sewerage_lateral_chk",
    "sewerage_manhole",
    "sewerage_manhole_chk",
    "sewerage_orifice",
    "sewerage_orifice_chk",
    "sewerage_outlet",
    "sewerage_outlet_chk",
    "sewerage_pipe",
    "sewerage_pipe_chk",
    "sewerage_pumpstation",
    "sewerage_pumpstation_chk",
    "sewerage_weir",
    "sewerage_weir_chk",
    "sisp_map_chk",
    "weir",
    "weir_chk",
    "wind",
]

# Don't try to delete Spatialite views.
# See https://www.gaia-gis.it/fossil/libspatialite/wiki?name=GetDbObjectScope%28%29
SPATIALITE_VIEWS = [
    "geom_cols_ref_sys",
    "spatial_ref_sys_all",
    "vector_coverages_ref_sys",
]

options = "|".join(V1_TABLES)
VIEW_REGEX = re.compile(f".*(\\w+{options}\\w+).*")


def upgrade():
    # first list views that refer to V1 TABLES
    conn = op.get_bind()
    inspector = inspect(conn)
    view_names = inspector.get_view_names()
    for view_name in view_names:
        if view_name.startswith("v2_") or view_name in SPATIALITE_VIEWS:
            continue
        defn = inspector.get_view_definition(view_name)
        if VIEW_REGEX.match(defn):
            op.execute(text(f"DROP VIEW {view_name}"))

    # then delete the actual tables if they exist
    existing = set(inspector.get_table_names())
    to_delete = set(existing).intersection(V1_TABLES)
    for table_name in to_delete:
        op.drop_table(table_name)


def downgrade():
    pass
