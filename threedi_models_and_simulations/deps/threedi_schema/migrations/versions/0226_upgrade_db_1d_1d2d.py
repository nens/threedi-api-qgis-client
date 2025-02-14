"""Upgrade settings in schema

Revision ID: 0225
Revises:
Create Date: 2024-08-30 07:52

"""
from typing import Dict, List, Tuple

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Boolean, Column, Float, Integer, String, Text
from sqlalchemy.orm import declarative_base

from threedi_schema.migrations.utils import drop_conflicting, drop_geo_table

# revision identifiers, used by Alembic.
revision = "0226"
down_revision = "0225"
branch_labels = None
depends_on = None

RENAME_TABLES = [
    ("v2_dem_average_area", "dem_average_area"),
    ("v2_exchange_line", "exchange_line"),
    ("v2_grid_refinement", "grid_refinement_line"),
    ("v2_grid_refinement_area", "grid_refinement_area"),
    ("v2_obstacle", "obstacle"),
    ("v2_potential_breach", "potential_breach"),
]

NEW_COLUMNS = [
    ("dem_average_area", Column("tags", Text)),
    ("dem_average_area", Column("code", Text)),
    ("dem_average_area", Column("display_name", Text)),
    ("exchange_line", Column("tags", Text)),
    ("exchange_line", Column("code", Text)),
    ("exchange_line", Column("display_name", Text)),
    ("grid_refinement_line", Column("tags", Text)),
    ("grid_refinement_area", Column("tags", Text)),
    ("obstacle", Column("tags", Text)),
    ("obstacle", Column("display_name", Text)),
    ("potential_breach", Column("tags", Text)),
    ("potential_breach", Column("final_exchange_level", Float))
]

RENAME_COLUMNS = {
    "grid_refinement_line": {"refinement_level": "grid_level"},
    "grid_refinement_area": {"refinement_level": "grid_level"},
    "potential_breach": {"exchange_level": "initial_exchange_level"}
}

RETYPE_COLUMNS = {
    "potential_breach": [("channel_id", "INTEGER")],
    "exchange_line": [("channel_id", "INTEGER")],
}

REMOVE_COLUMNS = {
    "exchange_line": ["channel"],
    "potential_breach": ["channel", "maximum_breach_depth"]
}


class Schema225UpgradeException(Exception):
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
    geom_type = None
    for col in columns:
        if col[1] == 'the_geom':
            geom_type = col[2]
            break
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
    GEO_COL_INFO = [
        ('dem_average_area', 'geom', 'POLYGON'),
        ('exchange_line', 'geom', 'LINESTRING'),
        ('grid_refinement_line', 'geom', 'LINESTRING'),
        ('grid_refinement_area', 'geom', 'POLYGON'),
        ('obstacle', 'geom', 'LINESTRING'),
        ('potential_breach', 'geom', 'LINESTRING'),
    ]
    for table, column, geotype in GEO_COL_INFO:
        migration_query = f"SELECT RecoverGeometryColumn('{table}', '{column}', {4326}, '{geotype}', 'XY')"
        op.execute(sa.text(migration_query))


def set_potential_breach_final_exchange_level():
    conn = op.get_bind()
    res = conn.execute(sa.text(
        """
        SELECT id FROM v2_potential_breach
        WHERE exchange_level IS NOT NULL AND maximum_breach_depth IS NULL;
        """
    )).fetchall()
    if len(res) > 0:
        raise Schema225UpgradeException(
            f"Could not set final_exchange_level because maximum_breach_depth was not defined for rows: {res}")
    op.execute(sa.text(
        """
        UPDATE potential_breach
        SET final_exchange_level = (
            SELECT vb.exchange_level - vb.maximum_breach_depth
            FROM v2_potential_breach vb
            WHERE vb.id = potential_breach.id
            AND exchange_level IS NOT NULL
        );
        """
    ))


def upgrade():
    # Drop tables that conflict with new table names
    drop_conflicting(op, [new_name for _, new_name in RENAME_TABLES])
    rem_tables = []
    for old_table_name, new_table_name in RENAME_TABLES:
        modify_table(old_table_name, new_table_name)
        rem_tables.append(old_table_name)
    add_columns_to_tables(NEW_COLUMNS)
    set_potential_breach_final_exchange_level()
    fix_geometry_columns()
    remove_tables(rem_tables)


def downgrade():
    # Not implemented on purpose
    raise NotImplementedError("Downgrade back from 0.3xx is not supported")
