"""Migrate 1d and 2d lateral and boundary condition tables to new schema

Revision ID: 0225
Revises:
Create Date: 2024-08-05 11:22

"""
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Tuple

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import load_spatialite
from sqlalchemy import Boolean, Column, Integer, Text
from sqlalchemy.event import listen
from sqlalchemy.orm import declarative_base

from threedi_schema.domain.custom_types import Geometry
from threedi_schema.migrations.utils import drop_conflicting, drop_geo_table

# revision identifiers, used by Alembic.
revision = "0225"
down_revision = "0224"
branch_labels = None
depends_on = None

Base = declarative_base()

data_dir = Path(__file__).parent / "data"


# (source table, destination table)
RENAME_TABLES = [
    ("v2_1d_lateral", "lateral_1d"),
    ("v2_2d_lateral", "lateral_2d"),
    ("v2_1d_boundary_conditions", "boundary_condition_1d"),
    ("v2_2d_boundary_conditions", "boundary_condition_2d"),
]


ADD_COLUMNS = [
    ("lateral_1d", Column("code", Text)),
    ("lateral_1d", Column("display_name", Text)),
    ("lateral_1d", Column("tags", Text)),
    ("lateral_1d", Column("time_units", Text)),
    ("lateral_1d", Column("interpolate", Boolean)),
    ("lateral_1d", Column("offset", Integer)),
    ("lateral_1d", Column("units", Text)),

    ("lateral_2d", Column("code", Text)),
    ("lateral_2d", Column("display_name", Text)),
    ("lateral_2d", Column("tags", Text)),
    ("lateral_2d", Column("time_units", Text)),
    ("lateral_2d", Column("interpolate", Boolean)),
    ("lateral_2d", Column("offset", Integer)),
    ("lateral_2d", Column("units", Text)),

    ("boundary_condition_1d", Column("code", Text)),
    ("boundary_condition_1d", Column("display_name", Text)),
    ("boundary_condition_1d", Column("tags", Text)),
    ("boundary_condition_1d", Column("time_units", Text)),
    ("boundary_condition_1d", Column("interpolate", Boolean)),

    ("boundary_condition_2d", Column("code", Text)),
    # display_name was already added in migration 200
    ("boundary_condition_2d", Column("tags", Text)),
    ("boundary_condition_2d", Column("time_units", Text)),
    ("boundary_condition_2d", Column("interpolate", Boolean)),
]

# Geom columns need to be added using geoalchemy, so therefore that's a separate task
NEW_GEOM_COLUMNS = {
    ("lateral_1d", Column("geom", Geometry("POINT"), nullable=False)),
    ("boundary_condition_1d", Column("geom", Geometry("POINT"), nullable=False)),
}


# old name, new name
# the columns will be renamed using raw sql
# this is because alembic has conniptions whenever you try to batch rename a geometry column
RENAME_COLUMNS = {
    "boundary_condition_1d": [
        ("boundary_type", "type"),
    ],
    "boundary_condition_2d": [
        ("boundary_type", "type"),
        ("the_geom", "geom"),
    ],
    "lateral_2d": [
        ("the_geom", "geom"),
    ],
}


DEFAULT_VALUES = {
    "lateral_1d": {
        "time_units": "'minutes'",
        "interpolate": "0",  # false
        "offset": "NULL",
        "units": "'m3/s'"
    },
    "lateral_2d": {
        "time_units": "'minutes'",
        "interpolate": "0",  # false
        "offset": "NULL",
        "units": "'m3/s'"
    },
    "boundary_condition_1d": {
        "time_units": "'minutes'",
        "interpolate": "1",  # true
    },
    "boundary_condition_2d": {
        "time_units": "'minutes'",
        "interpolate": "1",  # true
    },
}

GEOMETRY_TYPES = {"lateral_2d": "POINT",
                  "lateral_1d": "POINT",
                  "boundary_condition_1d": "POINT",
                  "boundary_condition_2d": "LINESTRING"}


def rename_tables(table_sets: List[Tuple[str, str]]):
    # no checks for existence are done, this will fail if a source table doesn't exist
    connection = op.get_bind()
    spatialite_version = connection.execute(sa.text("SELECT spatialite_version();")).fetchall()[0][0]
    for src_name, dst_name in table_sets:
        if spatialite_version.startswith('5'):
            op.execute(sa.text(f"SELECT RenameTable(NULL, '{src_name}', '{dst_name}');"))
        else:
            op.rename_table(src_name, dst_name)


def create_new_tables(new_tables: Dict[str, sa.Column]):
    # no checks for existence are done, this will fail if any table already exists
    for table_name, columns in new_tables.items():
        op.create_table(table_name, sa.Column("id", sa.Integer(), primary_key=True),
                        *columns)


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
        f"SELECT AddGeometryColumn('{table}', '{geocol.name}', {geotype.srid}, '{geotype.geometry_type}', 'XY', {int(not geocol.nullable)});")
    op.execute(sa.text(query))


def rename_columns(table_name: str, columns: List[Tuple[str, str]]):
    # no checks for existence are done, this will fail if table or any source column doesn't exist
    connection = op.get_bind()
    old_columns_result = connection.execute(sa.text(f"PRAGMA table_info('{table_name}')")).fetchall()
    old_columns = []
    for value_list in old_columns_result:
        old_columns.append({"name": value_list[1], "type": value_list[2]})

    columns_dict = dict(columns)

    old_columns_list = [entry["name"] for entry in old_columns]
    if not all(e in old_columns_list for e in columns_dict):
        raise ValueError(f"Cannot rename columns {columns_dict.keys()} in table {table_name}; table does not contain all these columns")
    new_columns = deepcopy(old_columns)
    for i in range(len(new_columns)):
        if new_columns[i]["name"] in columns_dict.keys():
            new_columns[i]["name"] = columns_dict[new_columns[i]["name"]]

    new_columns_list = [entry["name"] for entry in new_columns]

    new_columns_list_sql_formatted = []
    for entry in new_columns:
        entry_string = f"{entry['name']} {entry['type']}"
        if entry['name'] == "id":
            entry_string += f" PRIMARY KEY"
        # in the new database schema only geometries and id will have NOT NULL constraints
        if entry['name'] in ["geom", "id"]:
            entry_string += f" NOT NULL"
        new_columns_list_sql_formatted.append(entry_string)

    temp_name = f'_temp_225_{uuid.uuid4().hex}'
    create_table_query = f"""CREATE TABLE {temp_name} ({', '.join(new_columns_list_sql_formatted)});"""
    op.execute(sa.text(create_table_query))
    op.execute(sa.text(f"INSERT INTO {temp_name} ({','.join(new_columns_list)}) SELECT {','.join(old_columns_list)} from {table_name};"))
    drop_geo_table(op, table_name)
    op.execute(sa.text(f"ALTER TABLE {temp_name} RENAME TO {table_name};"))

    if table_name is not GEOMETRY_TYPES:
        op.execute(sa.text(f"""SELECT RecoverGeometryColumn('{table_name}', 'geom', 4326, '{GEOMETRY_TYPES[table_name]}', 'XY')"""))



def copy_v2_geometries_from_connection_nodes_by_id(dest_table: str, dest_column: str):
    query = (
        f"""
        UPDATE {dest_table}
        SET {dest_column} = (
            SELECT the_geom
            FROM v2_connection_nodes
            WHERE {dest_table}.connection_node_id = v2_connection_nodes.id
        );
        """
    )
    op.execute(sa.text(query))


def populate_table(table: str, values: dict):
    """Populate SQL columns with values"""
    # convert {a: b, c: d} to "a=b, c=d" for the query
    sql_formatted_columns = ', '.join('{} = {}'.format(key, value) for key, value in values.items())
    # then insert it into the query
    query = f"""UPDATE {table} SET {sql_formatted_columns};"""
    op.execute(sa.text(query))


def upgrade():
    # Drop tables that conflict with new table names
    drop_conflicting(op, [new_name for _, new_name in RENAME_TABLES])

    # rename existing tables
    rename_tables(RENAME_TABLES)

    # add new columns to existing tables
    add_columns_to_tables(ADD_COLUMNS)

    # rename columns in renamed tables
    for table_name, columns in RENAME_COLUMNS.items():
        rename_columns(table_name, columns)

    # add geometry columns after renaming columns
    # to not needlessly trigger RecoverGeometryColumn
    add_columns_to_tables(NEW_GEOM_COLUMNS)

    # recover geometry column data from connection nodes
    for table, column in (
        ("lateral_1d", "geom"),
        ("boundary_condition_1d", "geom")
    ):
        copy_v2_geometries_from_connection_nodes_by_id(dest_table=table, dest_column=column)

    # populate new columns in tables
    for key, value in DEFAULT_VALUES.items():
        populate_table(table=key, values=value)


def downgrade():
    # Not implemented on purpose
    raise NotImplementedError("Downgrade back from 0.3xx is not supported")
