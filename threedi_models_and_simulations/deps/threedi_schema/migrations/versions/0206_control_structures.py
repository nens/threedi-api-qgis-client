"""make settings nullable

Revision ID: 0206
Revises: 0205
Create Date: 2021-12-16 13:30:00

"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "0206"
down_revision = "0205"
branch_labels = None
depends_on = None


MIGRATION_QUERIES = """
UPDATE v2_control_measure_map SET weight = 1.0 WHERE weight IS NULL;
"""


def upgrade():
    for q in MIGRATION_QUERIES.split(";"):
        op.execute(text(q))

    with op.batch_alter_table("v2_control_measure_map") as batch_op:
        batch_op.alter_column("object_id", nullable=False)
        batch_op.alter_column("object_type", nullable=False)
        batch_op.alter_column("weight", nullable=False)

    with op.batch_alter_table("v2_control_memory") as batch_op:
        batch_op.alter_column("measure_variable", nullable=False)
        batch_op.alter_column("action_type", nullable=False)
        batch_op.alter_column("action_value", nullable=False)
        batch_op.alter_column("target_type", nullable=False)
        batch_op.alter_column("target_id", nullable=False)

    with op.batch_alter_table("v2_control_table") as batch_op:
        batch_op.alter_column("measure_variable", nullable=False)
        batch_op.alter_column("action_type", nullable=False)
        batch_op.alter_column("action_table", nullable=False)
        batch_op.alter_column("target_type", nullable=False)
        batch_op.alter_column("target_id", nullable=False)

    with op.batch_alter_table("v2_control") as batch_op:
        batch_op.alter_column("control_type", nullable=False)


def downgrade():
    pass
