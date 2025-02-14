from typing import List

import sqlalchemy as sa


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
    existing_tables = [item[0] for item in connection.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table';")).fetchall()]
    for table_name in set(existing_tables).intersection(new_tables):
        drop_geo_table(op, table_name)