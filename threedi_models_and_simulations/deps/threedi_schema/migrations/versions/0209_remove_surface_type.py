"""remove surface_type

Revision ID: 0209
Revises: 0208
Create Date: 2022-10-13 10:45

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0209"
down_revision = "0208"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("v2_surface_map") as batch_op:
        batch_op.drop_column("surface_type")


def downgrade():
    with op.batch_alter_table("v2_surface_map") as batch_op:
        batch_op.add_column(
            sa.Column("surface_type", sa.String(length=40), nullable=True)
        )
