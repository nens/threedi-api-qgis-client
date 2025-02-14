"""

Revision ID: 022
9Revises:
Create Date: 2024-11-15 14:18

"""
import uuid
from typing import List

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0229"
down_revision = "0228"
branch_labels = None
depends_on = None


def get_geom_type(table_name, geo_col_name):
    connection = op.get_bind()
    columns = connection.execute(sa.text(f"PRAGMA table_info('{table_name}')")).fetchall()
    for col in columns:
        if col[1] == geo_col_name:
            return col[2]

def change_types_in_settings_table():
    temp_table_name = f'_temp_229_{uuid.uuid4().hex}'
    table_name = 'model_settings'
    change_types = {'use_d2_rain': 'bool', 'friction_averaging': 'bool'}
    connection = op.get_bind()
    columns = connection.execute(sa.text(f"PRAGMA table_info('{table_name}')")).fetchall()
    # get all column names and types
    skip_cols = ['id', 'the_geom']
    col_names = [col[1] for col in columns if col[1] not in skip_cols]
    old_col_types = [col[2] for col in columns if col[1] not in skip_cols]
    col_types = [change_types.get(col_name, col_type) for col_name, col_type in zip(col_names, old_col_types)]
    # Create new table, insert data, drop original and rename temp to table_name
    col_str = ','.join(['id INTEGER PRIMARY KEY NOT NULL'] + [f'{cname} {ctype}' for cname, ctype in
                                                                  zip(col_names, col_types)])
    op.execute(sa.text(f"CREATE TABLE {temp_table_name} ({col_str});"))
    # Copy data
    op.execute(sa.text(f"INSERT INTO {temp_table_name} (id, {','.join(col_names)}) "
                       f"SELECT id, {','.join(col_names)} FROM {table_name}"))
    op.execute(sa.text(f"DROP TABLE {table_name}"))
    op.execute(sa.text(f"ALTER TABLE {temp_table_name} RENAME TO {table_name};"))


def remove_tables(tables: List[str]):
    for table in tables:
        op.drop_table(table)


def find_tables_by_pattern(pattern: str) -> List[str]:
    connection = op.get_bind()
    query = connection.execute(
        sa.text(f"select name from sqlite_master where type = 'table' and name like '{pattern}'"))
    return [item[0] for item in query.fetchall()]


def remove_old_tables():
    remaining_v2_idx_tables = find_tables_by_pattern('idx_v2_%_the_geom')
    remaining_alembic = find_tables_by_pattern('%_alembic_%_the_geom')
    remove_tables(remaining_v2_idx_tables + remaining_alembic)


def clean_geometry_columns():
    """ Remove columns referencing v2 in geometry_columns """
    op.execute(sa.text("""
            DELETE FROM geometry_columns WHERE f_table_name IN (
                SELECT g.f_table_name FROM geometry_columns g
                LEFT JOIN sqlite_master m ON g.f_table_name = m.name
                WHERE m.name IS NULL AND g.f_table_name like "%v2%"
            );
        """))


def clean_by_type(type: str):
    connection = op.get_bind()
    items = [item[0] for item in connection.execute(
        sa.text(f"SELECT tbl_name FROM sqlite_master WHERE type='{type}' AND tbl_name LIKE '%v2%';")).fetchall()]
    for item in items:
        op.execute(f"DROP {type} IF EXISTS {item};")


def update_use_settings():
    # Ensure that use_* settings are only True when there is actual data for them
    use_settings = [
        ('use_groundwater_storage', 'groundwater'),
        ('use_groundwater_flow', 'groundwater'),
        ('use_interflow', 'interflow'),
        ('use_simple_infiltration', 'simple_infiltration'),
        ('use_vegetation_drag_2d', 'vegetation_drag_2d'),
        ('use_interception', 'interception')
    ]
    connection = op.get_bind()  # Get the connection for raw SQL execution
    for setting, table in use_settings:
        use_row = connection.execute(sa.text(f"SELECT {setting} FROM model_settings")).scalar()
        if not use_row:
            continue
        row = connection.execute(sa.text(f"SELECT * FROM {table}")).first()
        use_row = (row is not None)
        if use_row:
            use_row = not all(item in (None, "") for item in row[1:])
        if not use_row:
            connection.execute(sa.text(f"UPDATE model_settings SET {setting} = 0"))

            
def upgrade():
    remove_old_tables()
    clean_geometry_columns()
    clean_by_type('trigger')
    clean_by_type('view')
    update_use_settings()
    change_types_in_settings_table()


def downgrade():
    pass
