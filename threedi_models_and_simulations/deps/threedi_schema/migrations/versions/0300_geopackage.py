"""Convert to geopackage

Revision ID: 0230
Revises:
Create Date: 2024-11-12 12:30

"""

import sqlite3
import uuid

import sqlalchemy as sa
from alembic import op
from threedi_schema.application.errors import InvalidSRIDException

# revision identifiers, used by Alembic.
revision = "0300"
down_revision = "0230"
branch_labels = None
depends_on = None


def upgrade():
    # this upgrade only changes the model version
    pass


def downgrade():
    # Not implemented on purpose
    pass
