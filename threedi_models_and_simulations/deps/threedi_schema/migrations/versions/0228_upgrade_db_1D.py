"""Upgrade 1d settings

Revision ID: 0225
Revises:
Create Date: 2024-09-10 09:00

"""
import csv
import uuid
from pathlib import Path
from typing import Dict, List, Tuple

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Column, Float, func, Integer, select, String, Text
from sqlalchemy.orm import declarative_base, Session

from threedi_schema.domain import constants
from threedi_schema.domain.custom_types import Geometry, IntegerEnum
from threedi_schema.migrations.utils import drop_conflicting, drop_geo_table

Base = declarative_base()

data_dir = Path(__file__).parent / "data"


# revision identifiers, used by Alembic.
revision = "0228"
down_revision = "0227"
branch_labels = None
depends_on = None

RENAME_TABLES = [
    ("v2_channel", "channel"),
    ("v2_windshielding", "windshielding_1d"),
    ("v2_cross_section_location", "cross_section_location"),
    ("v2_pipe", "pipe"),
    ("v2_culvert", "culvert"),
    ("v2_weir", "weir"),
    ("v2_orifice", "orifice"),
    ("v2_pumpstation", "pump")
]

DELETE_TABLES = ["v2_cross_section_definition",
                 "v2_floodfill",
                 "v2_connection_nodes"]

RENAME_COLUMNS = {
    "culvert": {"calculation_type": "exchange_type",
                "dist_calc_points": "calculation_point_distance",
                "invert_level_start_point": "invert_level_start",
                "invert_level_end_point": "invert_level_end",
                "connection_node_start_id": "connection_node_id_start",
                "connection_node_end_id": "connection_node_id_end"},
    "pipe": {"calculation_type": "exchange_type",
             "dist_calc_points": "calculation_point_distance",
             "material": "material_id",
                "invert_level_start_point": "invert_level_start",
                "invert_level_end_point": "invert_level_end",
                "connection_node_start_id": "connection_node_id_start",
                "connection_node_end_id": "connection_node_id_end"},
    "channel": {"calculation_type": "exchange_type",
                "dist_calc_points": "calculation_point_distance",
                "connection_node_start_id": "connection_node_id_start",
                "connection_node_end_id": "connection_node_id_end"},
    "weir": {"calculation_type": "exchange_type",
                "dist_calc_points": "calculation_point_distance",
                "connection_node_start_id": "connection_node_id_start",
                "connection_node_end_id": "connection_node_id_end"},
    "orifice": {"calculation_type": "exchange_type",
                "dist_calc_points": "calculation_point_distance",
                "connection_node_start_id": "connection_node_id_start",
                "connection_node_end_id": "connection_node_id_end"},
    "pump": {"connection_node_start_id": "connection_node_id"}
}

REMOVE_COLUMNS = {
    "channel": ["zoom_category",],
    "cross_section_location": ["definition_id", "vegetation_drag_coeficients"],
    "culvert": ["zoom_category", "cross_section_definition_id"],
    "pipe": ["zoom_category", "original_length", "cross_section_definition_id", "profile_num"],
    "orifice": ["zoom_category", "cross_section_definition_id"],
    "weir": ["zoom_category", "cross_section_definition_id"],
    "pump": ["connection_node_end_id", "zoom_category", "classification"]
}

ADD_COLUMNS = [
    ("channel", Column("tags", Text)),
    ("cross_section_location", Column("tags", Text)),
    ("culvert", Column("tags", Text)),
    ("culvert", Column("material_id", Integer)),
    ("orifice", Column("tags", Text)),
    ("orifice", Column("material_id", Integer)),
    ("pipe", Column("tags", Text)),
    ("pump", Column("tags", Text)),
    ("weir", Column("tags", Text)),
    ("weir", Column("material_id", Integer)),
    ("windshielding_1d", Column("tags", Text)),
]

RETYPE_COLUMNS = {}

GEOM_TYPES = {'channel': 'LINESTRING',
              'orifice': 'LINESTRING',
              'weir': 'LINESTRING',
              'culvert': 'LINESTRING',
              'pipe': 'LINESTRING',
              'pump': 'POINT',
              'pump_map': 'LINESTRING',
              'connection_node': 'POINT',
              'cross_section_location': 'POINT',
              'windshielding_1d': 'POINT',
              }

def add_columns_to_tables(table_columns: List[Tuple[str, Column]]):
    # no checks for existence are done, this will fail if any column already exists
    for dst_table, col in table_columns:
        if isinstance(col.type, Geometry):
            add_geometry_column(dst_table, col)
        else:
            with op.batch_alter_table(dst_table) as batch_op:
                batch_op.add_column(col)


def add_geometry_column(table: str, geocol: Column):
    # Adding geometry columns via alembic doesn't work
    # https://postgis.net/docs/AddGeometryColumn.html
    geotype = geocol.type
    query = (
        f"SELECT AddGeometryColumn('{table}', '{geocol.name}', {geotype.srid}, '{geotype.geometry_type}', 'XY', 1);")
    op.execute(sa.text(query))


class Schema228UpgradeException(Exception):
    pass


def add_columns_to_tables(table_columns: List[Tuple[str, Column]]):
    # no checks for existence are done, this will fail if any column already exists
    for dst_table, col in table_columns:
        with op.batch_alter_table(dst_table) as batch_op:
            batch_op.add_column(col)


def remove_tables(tables: List[str]):
    for table in tables:
        drop_geo_table(op, table)

def modify_table(old_table_name, new_table_name):
    # Create a new table named `new_table_name` by copying the
    # data from `old_table_name`.
    # Use the columns from `old_table_name`, with the following exceptions:
    # * columns in `REMOVE_COLUMNS[new_table_name]` are skipped
    # * columns in `RENAME_COLUMNS[new_table_name]` are renamed
    # * columns in `RETYPE_COLUMNS[new_table_name]` change type
    # * `the_geom` is renamed to `geom` and NOT NULL is enforced
    connection = op.get_bind()
    columns = connection.execute(sa.text(f"PRAGMA table_info('{old_table_name}')")).fetchall()
    # get all column names and types
    col_names = [col[1] for col in columns]
    col_types = [col[2] for col in columns]
    # get type of the geometry column
    geom_type = GEOM_TYPES[new_table_name]
    # create list of new columns and types for creating the new table
    # create list of old columns to copy to new table
    skip_cols = ['id', 'the_geom']
    if new_table_name in REMOVE_COLUMNS:
        skip_cols += REMOVE_COLUMNS[new_table_name]
    old_col_names = []
    new_col_names = []
    new_col_types = []
    for cname, ctype in zip(col_names, col_types):
        if cname in skip_cols:
            continue
        old_col_names.append(cname)
        if new_table_name in RENAME_COLUMNS and cname in RENAME_COLUMNS[new_table_name]:
            new_col_names.append(RENAME_COLUMNS[new_table_name][cname])
        else:
            new_col_names.append(cname)
        if new_table_name in RETYPE_COLUMNS and cname in RETYPE_COLUMNS[new_table_name]:
            new_col_types.append(RETYPE_COLUMNS[new_table_name][cname])
        else:
            new_col_types.append(ctype)
    # add to the end manually
    old_col_names.append('the_geom')
    new_col_names.append('geom')
    new_col_types.append(f'{geom_type} NOT NULL')
    # Create new table (temp), insert data, drop original and rename temp to table_name
    new_col_str = ','.join(['id INTEGER PRIMARY KEY NOT NULL'] + [f'{cname} {ctype}' for cname, ctype in
                                                                  zip(new_col_names, new_col_types)])
    op.execute(sa.text(f"CREATE TABLE {new_table_name} ({new_col_str});"))
    # Copy data
    op.execute(sa.text(f"INSERT INTO {new_table_name} (id, {','.join(new_col_names)}) "
                       f"SELECT id, {','.join(old_col_names)} FROM {old_table_name}"))


def fix_geometry_columns():
    tables = ['channel', 'connection_node', 'cross_section_location', 'culvert',
              'orifice', 'pipe', 'pump', 'pump_map', 'weir', 'windshielding_1d']
    for table in tables:
        geom_type = GEOM_TYPES[table]
        op.execute(sa.text(f"SELECT RecoverGeometryColumn('{table}', "
                           f"'geom', {4326}, '{geom_type}', 'XY')"))
        op.execute(sa.text(f"SELECT CreateSpatialIndex('{table}', 'geom')"))


class Temp(Base):
    __tablename__ = f'_temp_228_{uuid.uuid4().hex}'

    id = Column(Integer, primary_key=True)
    cross_section_table = Column(String)
    cross_section_friction_values = Column(String)
    cross_section_vegetation_table = Column(String)
    cross_section_shape = Column(IntegerEnum(constants.CrossSectionShape))
    cross_section_width = Column(Float)
    cross_section_height = Column(Float)


def extend_cross_section_definition_table():
    conn = op.get_bind()
    session = Session(bind=op.get_bind())
    # create temporary table
    op.execute(sa.text(
        f"""CREATE TABLE {Temp.__tablename__} 
            (id INTEGER PRIMARY KEY, 
             cross_section_table TEXT,
             cross_section_shape INT,
             cross_section_width REAL,
             cross_section_height REAL,
             cross_section_friction_values TEXT,
             cross_section_vegetation_table TEXT)
        """))
    res = conn.execute(sa.text("SELECT id, shape, width, height FROM v2_cross_section_definition")).fetchall()
    # process data from v2_cross_section_definition by setting width and height to None when it's not a single float
    # omitting this stop results in issues with the data types in the database
    data_to_insert = []
    for row in res:
        id, shape, width, height = row
        try:
            width = float(width)
        except (ValueError, TypeError):
            width = None
        try:
            height = float(height)
        except (ValueError, TypeError):
            height = None
        data_to_insert.append({"id": id, "shape": shape, "width": width, "height": height})    # insert data into the temp table
    for data in data_to_insert:
        conn.execute(sa.text(
            f"""INSERT INTO {Temp.__tablename__} (id, cross_section_shape, cross_section_width, cross_section_height)
            VALUES (:id, :shape, :width, :height)"""), data)  # Pass parameters as dictionary directly
    def make_table(*args):
        split_args = [arg.split() for arg in args]
        if not all(len(args) == len(split_args[0]) for args in split_args):
            return
        return '\n'.join([','.join(row) for row in zip(*split_args)])
    # Create cross_section_table for tabulated
    res = conn.execute(sa.text(f"""
        SELECT id, height, width, shape FROM v2_cross_section_definition 
        WHERE v2_cross_section_definition.shape IN (5,6,7)   
        AND height IS NOT NULL AND width IS NOT NULL
    """)).fetchall()
    update_data = []
    for id, h, w, s in res:
        # tabulated_YZ: width -> Y; height -> Z
        if s == constants.CrossSectionShape.TABULATED_YZ.value:
            cross_section_table = make_table(w, h)
        # tabulated_trapezium or tabulated_rectangle: height, width
        else:
            cross_section_table = make_table(h, w)
        update_data.append({"id": id, "cross_section_table": cross_section_table})
    session.bulk_update_mappings(Temp, update_data)
    session.commit()
    # add cross_section_friction_table to cross_section_definition
    res = conn.execute(sa.text("""
        SELECT id, friction_values FROM v2_cross_section_definition 
        WHERE friction_values IS NOT NULL
        AND v2_cross_section_definition.shape = 7 
    """)).fetchall()
    for id, friction_values in res:
        temp_row = session.query(Temp).filter_by(id=id).first()
        temp_row.cross_section_friction_values = friction_values.replace(' ',',')
        session.commit()
    # add cross_section_vegetation_table to cross_section_definition
    res = conn.execute(sa.text("""
        SELECT id, vegetation_stem_densities, vegetation_stem_diameters, vegetation_heights, vegetation_drag_coefficients
        FROM v2_cross_section_definition 
        WHERE vegetation_stem_densities IS NOT NULL
        AND vegetation_stem_diameters IS NOT NULL
        AND vegetation_heights IS NOT NULL
        AND v2_cross_section_definition.shape = 7 
        AND vegetation_drag_coefficients IS NOT NULL
    """)).fetchall()
    for id, dens, diam, h, c in res:
        temp_row = session.query(Temp).filter_by(id=id).first()
        temp_row.cross_section_vegetation_table = make_table(dens, diam, h, c)
        session.commit()


def migrate_cross_section_definition_from_temp(target_table: str,
                                               cols: List[Tuple[str, str]],
                                               def_id_col: str):
    for cname, ctype in cols:
        op.execute(sa.text(f'ALTER TABLE {target_table} ADD COLUMN {cname} {ctype}'))
    # ensure that types work properly
    # e.g. heights cannot be text!!
    set_query = ','.join(
        f'{cname} = (SELECT {cname} FROM {Temp.__tablename__} WHERE id = {target_table}.{def_id_col})' for cname, _ in
        cols)
    op.execute(sa.text(f"""
        UPDATE {target_table}
        SET {set_query}
        WHERE EXISTS (SELECT 1 FROM {Temp.__tablename__} WHERE id = {target_table}.{def_id_col});
    """))
    op.execute(sa.text(f"UPDATE {target_table} SET cross_section_width = NULL WHERE cross_section_shape IN (5,6,7)"))
    op.execute(sa.text(f"UPDATE {target_table} SET cross_section_height = NULL WHERE cross_section_shape IN (5,6,7)"))



def migrate_cross_section_definition_to_location():
    cols = [('cross_section_table', 'TEXT'),
            ('cross_section_friction_values', 'TEXT'),
            ('cross_section_vegetation_table', 'TEXT'),
            ('cross_section_shape', 'INT'),
            ('cross_section_width', 'REAL'),
            ('cross_section_height', 'REAL')]
    migrate_cross_section_definition_from_temp(target_table='v2_cross_section_location',
                                               cols=cols,
                                               def_id_col='definition_id')

def migrate_cross_section_definition_to_object(table_name: str):
    cols = [('cross_section_table', 'TEXT'),
            ('cross_section_shape', 'INT'),
            ('cross_section_width', 'REAL'),
            ('cross_section_height', 'REAL')]
    migrate_cross_section_definition_from_temp(target_table=table_name,
                                               cols=cols,
                                               def_id_col='cross_section_definition_id')


def set_geom_for_object(table_name: str, col_name: str = 'the_geom'):
    op.execute(sa.text(f"SELECT AddGeometryColumn('{table_name}', '{col_name}', 4326, 'LINESTRING', 'XY', 0);"))
    q = f"""
        UPDATE
            {table_name} AS object
        SET 
            {col_name} = (
                SELECT 
                    MakeLine(start_node.the_geom, end_node.the_geom) 
                FROM 
                    v2_connection_nodes AS start_node,
                    v2_connection_nodes AS end_node 
                WHERE 
                    object.connection_node_start_id = start_node.id
                    AND 
                    object.connection_node_end_id = end_node.id
            )         
    """
    op.execute(sa.text(q))


def fix_geom_for_culvert():
    new_table_name = f'_temp_228_fix_culvert_{uuid.uuid4().hex}'
    old_table_name = 'v2_culvert'
    connection = op.get_bind()
    columns = connection.execute(sa.text(f"PRAGMA table_info('{old_table_name}')")).fetchall()
    # get all column names and types
    col_names = [col[1] for col in columns if col[1] not in ['id', 'the_geom']]
    col_types = [col[2] for col in columns if col[1] in col_names]
    # Create new table (temp), insert data, drop original and rename temp to table_name
    new_col_str = ','.join(['id INTEGER PRIMARY KEY NOT NULL'] + [f'{cname} {ctype}' for cname, ctype in
                                                                  zip(col_names, col_types)])
    op.execute(sa.text(f"CREATE TABLE {new_table_name} ({new_col_str});"))
    op.execute(sa.text(f"SELECT AddGeometryColumn('{new_table_name}', 'the_geom', 4326, 'LINESTRING', 'XY', 0);"))
    # Copy data
    op.execute(sa.text(f"INSERT INTO {new_table_name} (id, {','.join(col_names)}, the_geom) "
                       f"SELECT id, {','.join(col_names)}, the_geom FROM {old_table_name}"))
    op.execute(sa.text("DROP TABLE v2_culvert"))
    op.execute(sa.text(f"ALTER TABLE {new_table_name} RENAME TO v2_culvert"))


def set_geom_for_v2_pumpstation():
    op.execute(sa.text(f"SELECT AddGeometryColumn('v2_pumpstation', 'the_geom', 4326, 'POINT', 'XY', 0);"))
    q = """
        UPDATE
            v2_pumpstation as p
        SET the_geom = (
            SELECT node.the_geom FROM v2_connection_nodes AS node 
            WHERE p.connection_node_start_id = node.id
        )   
    """
    op.execute(sa.text(q))


def create_pump_map():
    # Create table
    query = """
        CREATE TABLE pump_map (
                id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, 
                pump_id INTEGER,connection_node_id_end INTEGER,tags TEXT,code VARCHAR(100),display_name VARCHAR(255),
                geom LINESTRING NOT NULL
            );
    """
    op.execute(sa.text(query))
    # Create geometry
    op.execute(sa.text(f"SELECT AddGeometryColumn('v2_pumpstation', 'map_geom', 4326, 'LINESTRING', 'XY', 0);"))
    op.execute(sa.text("""
        UPDATE v2_pumpstation
        SET map_geom = (
            SELECT MakeLine(start_geom.the_geom, end_geom.the_geom)
            FROM v2_connection_nodes AS start_geom, v2_connection_nodes AS end_geom
            WHERE v2_pumpstation.connection_node_start_id = start_geom.id
            AND v2_pumpstation.connection_node_end_id = end_geom.id
        )
        WHERE EXISTS (
            SELECT 1
            FROM v2_connection_nodes AS start_geom, v2_connection_nodes AS end_geom
            WHERE v2_pumpstation.connection_node_start_id = start_geom.id
            AND v2_pumpstation.connection_node_end_id = end_geom.id
        );
    """))

    # Copy data from v2_pumpstation
    new_col_names = ["pump_id", "connection_node_id_end", "code", "display_name", "geom"]
    old_col_names = ["id", "connection_node_end_id", "code", "display_name", "map_geom"]
    op.execute(sa.text(f"""
        INSERT INTO pump_map ({','.join(new_col_names)}) 
        SELECT {','.join(old_col_names)} FROM v2_pumpstation
        WHERE v2_pumpstation.connection_node_end_id IS NOT NULL
        AND v2_pumpstation.connection_node_start_id IS NOT NULL
    """))


def create_connection_node():
    # Create table
    query = """
            CREATE TABLE connection_node (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, 
            code VARCHAR(100),
            tags TEXT,
            display_name TEXT,
            storage_area FLOAT,
            initial_water_level FLOAT,
            visualisation INTEGER DEFAULT -1,
            manhole_surface_level FLOAT,
            bottom_level FLOAT,
            exchange_level FLOAT,
            exchange_type INTEGER,
            exchange_thickness FLOAT,
            hydraulic_conductivity_in FLOAT,
            hydraulic_conductivity_out FLOAT,
            geom POINT NOT NULL
        );    
    """
    op.execute(sa.text(query))
    # copy from v2_connection_nodes
    old_col_names = ["id", "initial_waterlevel", "storage_area", "the_geom", "code"]
    rename_map = {"initial_waterlevel": "initial_water_level", "the_geom": "geom"}
    new_col_names = [rename_map.get(old_name, old_name) for old_name in old_col_names]
    op.execute(sa.text(f"""
        INSERT INTO connection_node ({','.join(new_col_names)}) 
        SELECT {','.join(old_col_names)} FROM v2_connection_nodes
    """))
    # conditional copy from v2_manhole
    old_col_names = ["display_name", "code", "manhole_indicator",
                     "surface_level", "bottom_level", "drain_level",
                     "calculation_type", "exchange_thickness",
                     "hydraulic_conductivity_in", "hydraulic_conductivity_out"]
    rename_map = {"surface_level": "manhole_surface_level",
                  "bottom_level": "bottom_level",
                  "drain_level": "exchange_level",
                  "calculation_type": "exchange_type",
                  "manhole_indicator": "visualisation"}
    set_items = ',\n'.join(f"""{rename_map.get(col_name, col_name)} = (
        SELECT v2_manhole.{col_name} FROM v2_manhole
        WHERE v2_manhole.connection_node_id = connection_node.id)""" for col_name in old_col_names)
    op.execute("CREATE INDEX IF NOT EXISTS idx_v2_manhole_connection_node_id ON v2_manhole(connection_node_id)")
    op.execute(sa.text(f"""
        UPDATE connection_node
        SET {set_items}
        FROM v2_manhole
        WHERE v2_manhole.connection_node_id = connection_node.id;
    """))


# define Material class needed to populate table in create_material
class Material(Base):
    __tablename__ = "material"
    id = Column(Integer, primary_key=True)
    description = Column(Text)
    friction_type = Column(IntegerEnum(constants.FrictionType))
    friction_coefficient = Column(Float)


def create_material():
    op.execute(sa.text("""
    CREATE TABLE material (
    id INTEGER PRIMARY KEY NOT NULL,
    description TEXT,
    friction_type INTEGER,
    friction_coefficient REAL);
    """))
    connection = op.get_bind()
    nof_settings = connection.execute(sa.text("SELECT COUNT(*) FROM model_settings")).scalar()
    session = Session(bind=op.get_bind())
    if nof_settings > 0:
        with open(data_dir.joinpath('0228_materials.csv')) as file:
            reader = csv.DictReader(file)
            session.bulk_save_objects([Material(**row) for row in reader])
            session.commit()


def modify_obstacle():
    op.execute(sa.text(f'ALTER TABLE obstacle ADD COLUMN affects_2d BOOLEAN DEFAULT TRUE;'))
    op.execute(sa.text(f'ALTER TABLE obstacle ADD COLUMN affects_1d2d_open_water BOOLEAN DEFAULT TRUE;'))
    op.execute(sa.text(f'ALTER TABLE obstacle ADD COLUMN affects_1d2d_closed BOOLEAN DEFAULT FALSE;'))


def modify_control_target_type():
    for table_name in ['table_control', 'memory_control']:
        op.execute(sa.text(f"""
            UPDATE {table_name}
            SET target_type = REPLACE(target_type, 'v2_pumpstation', 'pump')
            WHERE target_type = 'v2_pumpstation';
        """))
        op.execute(sa.text(f"""
            UPDATE {table_name}
            SET target_type = REPLACE(target_type, 'v2_', '')
            WHERE target_type LIKE 'v2_%';
        """))



def modify_model_settings():
    op.execute(sa.text(f'ALTER TABLE model_settings ADD COLUMN node_open_water_detection INTEGER DEFAULT 1;'))


def check_for_null_geoms():
    tables = ["v2_connection_nodes", "v2_cross_section_location", "v2_culvert", "v2_channel", "v2_windshielding"]
    conn = op.get_bind()
    for table in tables:
        nof_null = conn.execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE the_geom IS NULL;")).fetchone()[0]
        if nof_null > 0:
            raise Schema228UpgradeException("Cannot migrate because of empty geometries in table {table}")


def fix_material_id():
    # Replace migrated material_id's with correct values
    replace_map = {9 : 2, 10 : 7}
    material_id_tables = ['pipe', 'culvert', 'weir', 'orifice']
    for table in material_id_tables:
        op.execute(sa.text(f"UPDATE {table} SET material_id = CASE material_id "
                           f"{' '.join([f'WHEN {old} THEN {new}' for old, new in replace_map.items()])} "
                           "ELSE material_id END"))

def upgrade():
    # Empty or non-existing connection node id (start or end) in Orifice, Pipe, Pumpstation or Weir will break
    # migration, so an error is raised in these cases
    check_for_null_geoms()
    # Prevent custom tables in schematisation from breaking migration when they conflict with new table names
    drop_conflicting(op, [new_name for _, new_name in RENAME_TABLES] + ['material', 'pump_map'])
    # Extent cross section definition table (actually stored in temp)
    extend_cross_section_definition_table()
    # Migrate data from cross_section_definition to cross_section_location
    migrate_cross_section_definition_to_location()
    # Prepare object tables for renaming by copying cross section data and setting the_geom
    for table_name in ['v2_culvert', 'v2_weir', 'v2_pipe', 'v2_orifice']:
        migrate_cross_section_definition_to_object(table_name)
        # Set geometry for tables without one
        if table_name != 'v2_culvert':
            set_geom_for_object(table_name)
        else:
            fix_geom_for_culvert()
    set_geom_for_v2_pumpstation()
    for old_table_name, new_table_name in RENAME_TABLES:
        modify_table(old_table_name, new_table_name)
    add_columns_to_tables(ADD_COLUMNS)
    # Create new tables
    create_pump_map()
    create_material()
    create_connection_node()
    # Modify exsiting tables
    modify_model_settings()
    modify_obstacle()
    modify_control_target_type()
    fix_material_id()
    fix_geometry_columns()
    remove_tables([old for old, _ in RENAME_TABLES]+DELETE_TABLES+[Temp.__tablename__, 'v2_manhole'])


def downgrade():
    # Not implemented on purpose
    raise NotImplementedError("Downgrade back from 0.3xx is not supported")
