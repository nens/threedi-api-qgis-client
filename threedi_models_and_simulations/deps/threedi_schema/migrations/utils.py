import sqlite3
from typing import List

import sqlalchemy as sa
from threedi_schema.application.errors import InvalidSRIDException


def drop_geo_table(op, table_name: str):
    """

    Safely drop table, taking into account geometry columns

    Parameters:
    op : object
        An object representing the database operation.
    table_name : str
        The name of the table to be dropped.
    """
    op.execute(sa.text(f"SELECT DropTable(NULL, '{table_name}');"))


def drop_conflicting(op, new_tables: List[str]):
    """
    Drop tables from database that conflict with new tables

    Parameters:
    op: The SQLAlchemy operation context to interact with the database.
    new_tables: A list of new table names to be checked for conflicts with existing tables.
    """
    connection = op.get_bind()
    existing_tables = [
        item[0] for item in connection.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table';")).fetchall()
    ]
    for table_name in set(existing_tables).intersection(new_tables):
        drop_geo_table(op, table_name)


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
    unit = conn.execute(f"SELECT SridGetUnit({srid})").fetchone()[0]
    is_projected = conn.execute(f"SELECT SridIsProjected({srid})").fetchone()[0]
    return unit, is_projected
