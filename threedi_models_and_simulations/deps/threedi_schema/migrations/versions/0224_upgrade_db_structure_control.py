"""Upgrade settings in schema

Revision ID: 0224
Revises:
Create Date: 2024-06-30 14:50

"""
import uuid
import warnings
from typing import Dict, List, Tuple

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Boolean, Column, Float, Integer, String, Text
from sqlalchemy.orm import declarative_base

from threedi_schema.domain.custom_types import Geometry
from threedi_schema.migrations.utils import drop_conflicting, drop_geo_table

# revision identifiers, used by Alembic.
revision = "0224"
down_revision = "0223"
branch_labels = None
depends_on = None

Base = declarative_base()

DEL_TABLES = ['v2_control',
              'v2_control_delta',
              'v2_control_group',
              'v2_control_measure_group',
              'v2_control_measure_map',
              'v2_control_pid',
              'v2_control_timed']

RENAME_TABLES = [
    ("v2_control_memory", "memory_control"),
    ("v2_control_table", "table_control"),
]

ADD_COLUMNS = [
    ("memory_control", Column("tags", Text)),
    ("memory_control", Column("code", Text)),
    ("memory_control", Column("display_name", Text)),
    ("memory_control", Column("action_value_1", Float)),
    ("memory_control", Column("action_value_2", Float)),
    ("table_control", Column("tags", Text)),
    ("table_control", Column("code", Text)),
    ("table_control", Column("display_name", Text)),
    ('simulation_template_settings', Column('use_structure_control', Boolean)),
    ("control_measure_location", Column("geom", Geometry("POINT"), nullable=False)),
    ("control_measure_map", Column("geom", Geometry("LINESTRING"), nullable=False)),
    ("memory_control", Column("geom", Geometry("POINT"), nullable=False)),
    ("table_control", Column("geom", Geometry("POINT"), nullable=False))
]

ADD_TABLES = {
    "control_measure_location": [
        Column("connection_node_id", Integer),
        Column("measure_variable", Text, server_default="water_level"),
        Column("tags", Text),
        Column("code", Text),
        Column("display_name", Text),
    ],
    "control_measure_map": [
        Column("weight", Float),
        Column("control_measure_location_id", Integer),
        Column("control_id", Integer),
        Column("control_type", Text),
        Column("tags", Text),
        Column("code", Text),
        Column("display_name", Text),
    ],
}


class InvalidConnectionNode(UserWarning):
    pass


def create_new_tables(new_tables: Dict[str, sa.Column]):
    # no checks for existence are done, this will fail if any table already exists
    for table_name, columns in new_tables.items():
        op.create_table(table_name, sa.Column("id", sa.Integer(), primary_key=True),
                        *columns)


def rename_tables(table_sets: List[Tuple[str, str]]):
    # no checks for existence are done, this will fail if a source table doesn't exist
    for src_name, dst_name in table_sets:
        op.rename_table(src_name, dst_name)


def add_columns_to_tables(table_columns: List[Tuple[str, Column]]):
    # no checks for existence are done, this will fail if any column already exists
    for dst_table, col in table_columns:
        if isinstance(col.type, Geometry):
            add_geometry_column(dst_table, col)
        else:
            with op.batch_alter_table(dst_table) as batch_op:
                batch_op.add_column(col)


def make_all_columns_nullable(table_name, id_name: str = 'id'):
    # no checks for existence are done, this will fail if table doesn't exist
    connection = op.get_bind()
    table = sa.Table(table_name, sa.MetaData(), autoload_with=connection)
    with op.batch_alter_table(table_name) as batch_op:
        for column in table.columns:
            if column.name == id_name:
                continue
            batch_op.alter_column(column_name=column.name, nullable=True)


def move_setting(src_table: str, src_col: str, dst_table: str, dst_col: str):
    # This only works for tables with one row, such as settings tables
    op.execute(sa.text(f'UPDATE {dst_table} SET {dst_col} = (SELECT {src_col} FROM {src_table} ORDER BY id LIMIT 1)'))
    remove_column_from_table(src_table, src_col)


def remove_invalid_rows_from_v2_control_measure_map():
    conn = op.get_bind()
    where_clause = """
    WHERE object_id NOT IN (
        SELECT id FROM v2_connection_nodes WHERE the_geom IS NOT NULL
    )
    """
    invalid_rows = conn.execute(sa.text(f"SELECT id FROM v2_control_measure_map {where_clause};")).fetchall()
    if len(invalid_rows) > 0:
        op.execute(sa.text(f"DELETE FROM v2_control_measure_map {where_clause};"))
        msg = (f"Could not migrate the following rows from v2_control_measure_map because "
               f"they are linked to connection nodes that do not exist"
               f"or have no geometry: {invalid_rows}")
        warnings.warn(msg, InvalidConnectionNode)



def remove_orphan_control(table_name):
    query = f"DELETE FROM {table_name} WHERE id NOT IN (SELECT control_id FROM control_measure_map);"
    op.execute(sa.text(query))


def populate_control_measure_map():
    query = """
    INSERT INTO control_measure_map (control_measure_location_id, weight, control_id, control_type)
    SELECT 
        v2_control_measure_map.id, 
        v2_control_measure_map.weight, 
        v2_control.control_id, 
        v2_control.control_type
    FROM 
        v2_control_measure_map
    JOIN 
        v2_control
    ON 
        v2_control_measure_map.measure_group_id = v2_control.measure_group_id;
    """
    op.execute(sa.text(query))


def add_control_geometries(control_name):
    targets = ['v2_channel', 'v2_pipe', 'v2_orifice', 'v2_culvert', 'v2_weir', 'v2_pumpstation']
    for target_type in targets:
        if target_type == 'v2_culvert':
            geom_query = f"""
                SELECT ST_Centroid(object.the_geom)
                FROM v2_culvert AS object
                JOIN v2_cross_section_definition AS def ON object.cross_section_definition_id = def.id
            """
        elif target_type == 'v2_pumpstation':
            geom_query = f"""
                SELECT start_node.the_geom
                FROM {target_type} AS object   
                JOIN v2_connection_nodes AS start_node ON object.connection_node_start_id = start_node.id
            """
        else:
            geom_query = f"""
                SELECT ST_Centroid(MakeLine(start_node.the_geom, end_node.the_geom))
                FROM {target_type} AS object
            """
            if target_type in ['v2_orifice', 'v2_weir']:
                geom_query += """
                JOIN v2_cross_section_definition AS def ON object.cross_section_definition_id = def.id
                """
            geom_query += """
            JOIN v2_connection_nodes AS start_node ON object.connection_node_start_id = start_node.id
            JOIN v2_connection_nodes AS end_node ON object.connection_node_end_id = end_node.id         
            """
        query = f"""
            UPDATE
                {control_name}
            SET geom = ({geom_query}
            WHERE object.id = {control_name}.target_id
            )
            WHERE {control_name}.target_type = '{target_type}';                
        """
        op.execute(sa.text(query))


def get_global_srid():
    conn = op.get_bind()
    use_0d_inflow = conn.execute(sa.text("SELECT use_0d_inflow FROM simulation_template_settings LIMIT 1")).fetchone()
    if use_0d_inflow is not None:
        srid = conn.execute(sa.text("SELECT epsg_code FROM model_settings LIMIT 1")).fetchone()
        if (srid is not None) and (srid[0] is not None):
            return srid[0]
    return 28992


def set_geom_for_control_measure_map():
    srid = get_global_srid()
    for control in ['memory', 'table']:
        control_table = f'{control}_control'
        query = f"""
        UPDATE
            control_measure_map
        SET
            geom = (
                SELECT CASE
                    WHEN ST_Equals(cml.geom, tc.geom) THEN
                        -- Transform to EPSG:4326 for the projection, then back to the original SRID
                        MakeLine(
                            cml.geom,
                            ST_Transform(
                                ST_Translate(
                                    ST_Transform(tc.geom, {srid}),
                                    0, 1, 0
                                ),
                                4326
                            )                   
                        )
                    ELSE
                        MakeLine(cml.geom, tc.geom)
                    END                                           
                FROM 
                    {control_table} AS tc
                JOIN 
                    control_measure_map AS cmm ON cmm.control_id = tc.id
                JOIN 
                    control_measure_location AS cml ON cmm.control_measure_location_id = cml.id
                WHERE 
                    tc.id = control_measure_map.control_id
                )    
            WHERE
                EXISTS (
                    SELECT 1
                    FROM 
                        {control_table} AS tc
                    WHERE 
                        tc.id = control_measure_map.control_id
                );                                     
        """
        op.execute(sa.text(query))


def add_geometry_column(table: str, geocol: Column):
    # Adding geometry columns via alembic doesn't work
    # https://postgis.net/docs/AddGeometryColumn.html
    geotype = geocol.type
    query = (
        f"SELECT AddGeometryColumn('{table}', '{geocol.name}', {geotype.srid}, '{geotype.geometry_type}', 'XY', 0);")
    op.execute(sa.text(query))


def populate_control_measure_location():
    # copy data from
    query = """
    INSERT INTO control_measure_location (id, connection_node_id)
    SELECT 
        v2_control_measure_map.id, 
        v2_control_measure_map.object_id
    FROM 
        v2_control_measure_map;
    """
    op.execute(sa.text(query))
    query = """
    UPDATE control_measure_location   
    SET geom = (
        SELECT v2_connection_nodes.the_geom
        FROM v2_connection_nodes
        JOIN control_measure_location
        ON v2_connection_nodes.id = control_measure_location.connection_node_id
    )
    WHERE EXISTS (
        SELECT 1
        FROM v2_connection_nodes
        WHERE v2_connection_nodes.id = control_measure_location.connection_node_id
    );    
    """
    op.execute(sa.text(query))


def reformat_action_table():
    # Reformat table with action settings to proper csv table:
    # * replace ';' column separators with ','
    # * replace '#' line seperators with '\n'
    # * replace whitespace tabs ('\t') with single whitespace (' ')
    query = """
    UPDATE table_control
    SET action_table = REPLACE(
                          REPLACE(
                              REPLACE(action_table, ';', ','),
                          '#', '\n'),
                      '\t', ' ');
    """
    op.execute(sa.text(query))


def reformat_action_value():
    # Split action_value string (val_1, val_2) into two fields and remove action_value
    # Before: memory_control.action_value = action_value_1, action_value_2
    # After: memory_control.action_value_1 = action_value_1; memory_control.action_value_2 = action_value_2
    query = """
    UPDATE memory_control
    SET action_value_1 = CAST(SUBSTR(action_value, 1, INSTR(REPLACE(REPLACE(REPLACE(action_value, ';', ','), '\t', ' '), '  ', ' '), ',') - 1) AS REAL),
    action_value_2 = CAST(SUBSTR(action_value, INSTR(REPLACE(REPLACE(REPLACE(action_value, ';', ','), '\t', ' '), '  ', ' '), ',') + 1) AS REAL);
    """
    op.execute(sa.text(query))
    remove_column_from_table('memory_control', 'action_value')


def rename_measure_operator(table_name: str):
    op.execute(sa.text(
        f"""
        UPDATE {table_name}
        SET measure_variable = 'water_level'
        WHERE measure_variable = 'waterlevel'
        """
    ))


def remove_column_from_table(table_name: str, column: str):
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.drop_column(column)


def remove_tables(tables: List[str]):
    for table in tables:
        drop_geo_table(op, table)


def make_geom_col_notnull(table_name):
    # Make control_measure_map.geom not nullable by creating a new table with
    # not nullable geometry column, copying the data from control_measure_map
    # to the new table, dropping the original and renaming the new one to control_measure_map
    # For some reason, changing this via batch_op.alter_column does not seem to work

    # Retrieve column names and types from table
    # Note that it is expected that the geometry column is the last column!
    connection = op.get_bind()
    columns = connection.execute(sa.text(f"PRAGMA table_info('{table_name}')")).fetchall()
    col_names = [col[1] for col in columns]
    col_types = [col[2] for col in columns]
    cols = (['id INTEGER PRIMARY KEY'] +
            [f'{cname} {ctype}' for cname, ctype in zip(col_names[:-1], col_types[:-1]) if cname != 'id'] +
            [f'geom {columns[-1][2]} NOT NULL'])
    # Create new table, insert data, drop original and rename to table_name
    temp_name = f'_temp_224_{uuid.uuid4().hex}'
    op.execute(sa.text(f"CREATE TABLE {temp_name} ({','.join(cols)});"))
    op.execute(sa.text(f"INSERT INTO {temp_name} ({','.join(col_names)}) SELECT {','.join(col_names)} FROM {table_name}"))
    drop_geo_table(op, table_name)
    op.execute(sa.text(f"ALTER TABLE {temp_name} RENAME TO {table_name};"))


def fix_geometry_columns():
    GEO_COL_INFO = [(row[0], row[1].name, row[1].type.geometry_type) for row in ADD_COLUMNS
                    if row[1].name == 'geom']
    for table, column, geotype in GEO_COL_INFO:
        make_geom_col_notnull(table)
        migration_query = f"SELECT RecoverGeometryColumn('{table}', '{column}', {4326}, '{geotype}', 'XY')"
        op.execute(sa.text(migration_query))


def update_use_structure_control():
    op.execute("""
        UPDATE simulation_template_settings SET use_structure_control = CASE
            WHEN
                (SELECT COUNT(*) FROM table_control) = 0 AND
                (SELECT COUNT(*) FROM memory_control) = 0 THEN 0
            ELSE use_structure_control
            END;    
    """)


def upgrade():
    # Remove existing tables (outside of the specs) that conflict with new table names
    drop_conflicting(op, list(ADD_TABLES.keys()) + [new_name for _, new_name in RENAME_TABLES])
    # create new tables and rename existing tables
    create_new_tables(ADD_TABLES)
    rename_tables(RENAME_TABLES)
    # add new columns to existing tables
    add_columns_to_tables(ADD_COLUMNS)
    # populate new tables
    remove_invalid_rows_from_v2_control_measure_map()
    populate_control_measure_map()
    populate_control_measure_location()
    remove_orphan_control('table_control')
    remove_orphan_control('memory_control')
    # modify table contents
    reformat_action_table()
    reformat_action_value()
    add_control_geometries('table_control')
    add_control_geometries('memory_control')
    set_geom_for_control_measure_map()
    rename_measure_operator('table_control')
    rename_measure_operator('memory_control')
    move_setting('model_settings', 'use_structure_control',
                 'simulation_template_settings', 'use_structure_control')
    update_use_structure_control()
    remove_tables(DEL_TABLES)
    # Fix geometry columns and also make all but geom column nullable
    fix_geometry_columns()


def downgrade():
    # Not implemented on purpose
    raise NotImplementedError("Downgrade back from 0.3xx is not supported")
