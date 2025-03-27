"""rename vegetation columns

Revision ID: 0217
Revises: 0216
Create Date: 2023-05-05 11:52:34.238859

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '0217'
down_revision = '0216'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("v2_vegetation_drag") as batch_op:
        batch_op.alter_column(
            "height", new_column_name="vegetation_height"
        )
        batch_op.alter_column(
            "height_file", new_column_name="vegetation_height_file"
        )
        batch_op.alter_column(
            "stem_count", new_column_name="vegetation_stem_count"
        )
        batch_op.alter_column(
            "stem_count_file", new_column_name="vegetation_stem_count_file"
        )
        batch_op.alter_column(
            "stem_diameter", new_column_name="vegetation_stem_diameter"
        )
        batch_op.alter_column(
            "stem_diameter_file", new_column_name="vegetation_stem_diameter_file"
        )
        batch_op.alter_column(
            "drag_coefficient", new_column_name="vegetation_drag_coefficient"
        )
        batch_op.alter_column(
            "drag_coefficient_file", new_column_name="vegetation_drag_coefficient_file"
        )


def downgrade():
    with op.batch_alter_table("v2_vegetation_drag") as batch_op:
        batch_op.alter_column(
            "vegetation_height", new_column_name="height"
        )
        batch_op.alter_column(
            "vegetation_height_file", new_column_name="height_file"
        )
        batch_op.alter_column(
            "vegetation_stem_count", new_column_name="stem_count"
        )
        batch_op.alter_column(
            "vegetation_stem_count_file", new_column_name="stem_count_file"
        )
        batch_op.alter_column(
            "vegetation_stem_diameter", new_column_name="stem_diameter"
        )
        batch_op.alter_column(
            "vegetation_stem_diameter_file", new_column_name="stem_diameter_file"
        )
        batch_op.alter_column(
            "vegetation_drag_coefficient", new_column_name="drag_coefficient"
        )
        batch_op.alter_column(
            "vegetation_drag_coefficient_file", new_column_name="drag_coefficient_file"
        )
