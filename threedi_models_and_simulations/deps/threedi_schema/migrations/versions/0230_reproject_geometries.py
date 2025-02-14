"""Reproject geometries to model CRS

Revision ID: 0230
Revises:
Create Date: 2024-11-12 12:30

"""
import sqlite3
import uuid

import sqlalchemy as sa
from alembic import op

from threedi_schema.migrations.exceptions import InvalidSRIDException

# revision identifiers, used by Alembic.
revision = "0230"
down_revision = "0229"
branch_labels = None
depends_on = None

GEOM_TABLES = ['boundary_condition_1d', 'boundary_condition_2d', 'channel', 'connection_node', 'measure_location',
               'measure_map', 'memory_control', 'table_control', 'cross_section_location', 'culvert',
               'dem_average_area', 'dry_weather_flow', 'dry_weather_flow_map', 'exchange_line', 'grid_refinement_line',
               'grid_refinement_area', 'lateral_1d', 'lateral_2d', 'obstacle', 'orifice', 'pipe', 'potential_breach',
               'pump', 'pump_map', 'surface', 'surface_map', 'weir', 'windshielding_1d']


def get_crs_info(srid):
    # Create temporary spatialite to find crs unit and projection
    conn = sqlite3.connect(":memory:")
    conn.enable_load_extension(True)
    conn.load_extension("mod_spatialite")
    # Initialite spatialite without any meta data
    conn.execute("SELECT InitSpatialMetaData(1, 'NONE');")
    # Add CRS
    success = conn.execute(f"SELECT InsertEpsgSrid({srid})").fetchone()[0]
    if not success:
        raise InvalidSRIDException(srid, "the supplied epsg_code is invalid")
    # retrieve units and is_projected
    unit = conn.execute(f'SELECT SridGetUnit({srid})').fetchone()[0]
    is_projected = conn.execute(f'SELECT SridIsProjected({srid})').fetchone()[0]
    return unit, is_projected


def get_model_srid() -> int:
    # Note: this will not work for models which are allowed to have no CRS (no geometries)
    conn = op.get_bind()
    srid_str = conn.execute(sa.text("SELECT epsg_code FROM model_settings")).fetchone()
    if srid_str is None or srid_str[0] is None:
        raise InvalidSRIDException(None, "no epsg_code is defined")
    try:
        srid = int(srid_str[0])
    except TypeError:
        raise InvalidSRIDException(srid_str[0], "the epsg_code must be an integer")
    unit, is_projected = get_crs_info(srid)
    if unit != "metre":
        raise InvalidSRIDException(srid, f"the CRS must be in metres, not {unit}")
    if not is_projected:
        raise InvalidSRIDException(srid, "the CRS must be in projected")
    return srid


def get_geom_type(table_name, geo_col_name):
    # map geometry numbers to names
    geom_type_map = {
        1: 'POINT',
        2: 'LINESTRING',
        3: 'POLYGON',
        4: 'MULTIPOINT',
        5: 'MULTILINESTRING',
        6: 'MULTIPOLYGON',
        7: 'GEOMETRYCOLLECTION',
    }
    connection = op.get_bind()
    # use metadata to determine spatialite version because the geometry type column differs
    srs_wkt_exists = connection.execute(sa.text("select count(name) from pragma_table_info('spatial_ref_sys') where name is 'srs_wkt'")).scalar() == 1
    # spatialite 3
    if srs_wkt_exists:
        return connection.execute(
            sa.text(f"SELECT type from geometry_columns where f_table_name='{table_name}'")).fetchone()[0]
    else:
        geom_type_num = connection.execute(
            sa.text(f"SELECT geometry_type from geometry_columns where f_table_name='{table_name}'")).fetchone()[0]
        return geom_type_map.get(geom_type_num, 'GEOMETRY')

def add_geometry_column(table: str, name: str, srid: int, geometry_type: str):
    # Adding geometry columns via alembic doesn't work
    query = (
        f"SELECT AddGeometryColumn('{table}', '{name}', {srid}, '{geometry_type}', 'XY', 1);")
    op.execute(sa.text(query))


def transform_column(table_name, srid):
    connection = op.get_bind()
    columns = connection.execute(sa.text(f"PRAGMA table_info('{table_name}')")).fetchall()
    # get all column names and types
    skip_cols = ['id', 'geom']
    col_names = [col[1] for col in columns if col[1] not in skip_cols]
    col_types = [col[2] for col in columns if col[1] not in skip_cols]
    # Create temporary table
    temp_table_name = f'_temp_230_{table_name}_{uuid.uuid4().hex}'
    # Create new table, insert data, drop original and rename temp to table_name
    col_str = ','.join(['id INTEGER PRIMARY KEY NOT NULL'] + [f'{cname} {ctype}' for cname, ctype in
                                                              zip(col_names, col_types)])
    op.execute(sa.text(f"CREATE TABLE {temp_table_name} ({col_str});"))
    # Add geometry column with new srid!
    geom_type = get_geom_type(table_name, 'geom')
    add_geometry_column(temp_table_name, 'geom', srid, geom_type)
    # Copy transformed geometry and other columns to temp table
    col_str = ','.join(['id'] + col_names)
    query = op.execute(sa.text(f"""
        INSERT INTO {temp_table_name} ({col_str}, geom) 
        SELECT {col_str}, ST_Transform(geom, {srid}) AS geom FROM {table_name}
        """))
    # Discard geometry column in old table
    op.execute(sa.text(f"SELECT DiscardGeometryColumn('{table_name}', 'geom')"))
    op.execute(sa.text(f"SELECT DiscardGeometryColumn('{temp_table_name}', 'geom')"))
    # Remove old table
    op.execute(sa.text(f"DROP TABLE '{table_name}'"))
    # Rename temp table
    op.execute(sa.text(f"ALTER TABLE '{temp_table_name}' RENAME TO '{table_name}';"))
    # Recover geometry stuff
    # This gives a bunch of warnings but seems to be needed to fix spatialite stuff
    op.execute(sa.text(f"SELECT RecoverGeometryColumn('{table_name}', "
                       f"'geom', {srid}, '{geom_type}', 'XY')"))
    op.execute(sa.text(f"SELECT CreateSpatialIndex('{table_name}', 'geom')"))
    op.execute(sa.text(f"SELECT RecoverSpatialIndex('{table_name}', 'geom')"))


def prep_spatialite(srid: int):
    conn = op.get_bind()
    has_srid = conn.execute(sa.text(f'SELECT COUNT(*) FROM spatial_ref_sys WHERE srid = {srid};')).fetchone()[0] > 0
    if not has_srid:
        conn.execute(sa.text(f"InsertEpsgSrid({srid})"))


def upgrade():
    # retrieve srid from model settings
    # raise exception if there is no srid, or if the srid is not valid
    srid = get_model_srid()
    if srid is not None:
        # prepare spatialite databases
        prep_spatialite(srid)
        # transform all geometries
        for table_name in GEOM_TABLES:
            transform_column(table_name, srid)
    else:
        print('Model without geometries and epsg code, we need to think about this')
    # remove crs from model_settings
    with op.batch_alter_table('model_settings') as batch_op:
        batch_op.drop_column('epsg_code')


def downgrade():
    # Not implemented on purpose
    raise NotImplementedError("Downgrade back from 0.3xx is not supported")
