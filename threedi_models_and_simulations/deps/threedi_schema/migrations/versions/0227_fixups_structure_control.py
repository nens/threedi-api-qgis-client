"""Upgrade settings in schema

Revision ID: 0227
Revises:
Create Date: 2024-09-24 15:10

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0227"
down_revision = "0226"
branch_labels = None
depends_on = None

TABLES = ['memory_control', 'table_control']
RENAME_TABLES = [('control_measure_location', 'measure_location'),
                 ('control_measure_map', 'measure_map'), ]


def fix_geometries(downgrade: bool=False):
    op.execute(sa.text("SELECT RecoverGeometryColumn('memory_control', 'geom', 4326, 'POINT', 'XY')"))
    op.execute(sa.text("SELECT RecoverGeometryColumn('table_control', 'geom', 4326, 'POINT', 'XY')"))
    if downgrade:
        op.execute(sa.text("SELECT RecoverGeometryColumn('control_measure_location', 'geom', 4326, 'POINT', 'XY')"))
        op.execute(sa.text("SELECT RecoverGeometryColumn('control_measure_map', 'geom', 4326, 'LINESTRING', 'XY')"))
    else:
        op.execute(sa.text("SELECT RecoverGeometryColumn('measure_location', 'geom', 4326, 'POINT', 'XY')"))
        op.execute(sa.text("SELECT RecoverGeometryColumn('measure_map', 'geom', 4326, 'LINESTRING', 'XY')"))


def upgrade():
    # remove measure variable from memory_control and table_control
    for table_name in TABLES:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_column('measure_variable')
    # rename column
    with op.batch_alter_table('control_measure_map') as batch_op:
        batch_op.alter_column('control_measure_location_id', new_column_name='measure_location_id')
    op.execute(sa.text(f"SELECT DiscardGeometryColumn('control_measure_location', 'geom')"))
    op.execute(sa.text(f"SELECT DiscardGeometryColumn('control_measure_map', 'geom')"))
    # rename tables
    for old_table_name, new_table_name in RENAME_TABLES:
        op.rename_table(old_table_name, new_table_name)
    fix_geometries()


def downgrade():
    # undo remove measure variable from memory_control and table_control
    for table_name in TABLES:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(sa.Column("measure_variable", sa.Text, server_default="water_level"))
    # undo rename columns
    with op.batch_alter_table('measure_map') as batch_op:
        batch_op.alter_column('measure_location_id', new_column_name='control_measure_location_id')
    # rename tables
    op.execute(sa.text(f"SELECT DiscardGeometryColumn('measure_location', 'geom')"))
    op.execute(sa.text(f"SELECT DiscardGeometryColumn('measure_map', 'geom')"))
    for old_table_name, new_table_name in RENAME_TABLES:
        op.rename_table(new_table_name, old_table_name)
    fix_geometries(downgrade=True)
