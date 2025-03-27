"""vegetation drag

Revision ID: 0216
Revises: 0215
Create Date: 2023-03-13 15:05:42.393961

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '0216'
down_revision = '0215'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'v2_vegetation_drag',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('height', sa.Float(), nullable=True),
        sa.Column('height_file', sa.String(length=255), nullable=True),
        sa.Column('stem_count', sa.Float(), nullable=True),
        sa.Column('stem_count_file', sa.String(length=255), nullable=True),
        sa.Column('stem_diameter', sa.Float(), nullable=True),
        sa.Column('stem_diameter_file', sa.String(length=255), nullable=True),
        sa.Column('drag_coefficient', sa.Float(), nullable=True),
        sa.Column('drag_coefficient_file', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.add_column('v2_global_settings', sa.Column('vegetation_drag_settings_id', sa.Integer(), nullable=True))

    ## FIX migration 214:
    for table_name in ["v2_connected_pnt", "v2_calculation_point", "v2_levee"]:
        try:
            op.execute(sa.text(f"SELECT DropTable(NULL, '{table_name}', TRUE)"))
        except sa.exc.OperationalError:
            op.execute(sa.text(f"SELECT DropGeoTable('{table_name}')"))
            op.execute(sa.text(f"DROP TABLE IF EXISTS '{table_name}'"))


def downgrade():
    op.drop_constraint(None, 'v2_global_settings', type_='foreignkey')
    op.drop_column('v2_global_settings', 'vegetation_drag_settings_id')
    op.drop_table('v2_vegetation_drag')
