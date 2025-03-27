import os

from alembic import context
from sqlalchemy import text

import threedi_schema.domain.models  # NOQA needed for autogenerate
from threedi_schema import ThreediDatabase
from threedi_schema.domain import constants
from threedi_schema.domain.models import Base

target_metadata = Base.metadata
config = context.config


def get_url():
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise RuntimeError(
            "Database URL must be specified using the environment variable DB_URL"
        )
    return db_url


def run_migrations_online():
    """Run migrations in 'online' mode.

    Note: SQLite does not (completely) support transactions, so, backup the
    SQLite before running migrations.
    """
    unsafe = config.attributes.get("unsafe")
    
    engine = config.attributes.get("engine")
    if engine is None:
        engine = ThreediDatabase(get_url()).engine
    

    with engine.connect() as connection:
        # the following 5 lines have been commented out because for some reason the
        # spatialite schema_version doesn't get updated when journal_mode is set to MEMORY
        # TODO: make this work again.
        # if unsafe:
        #     # Speed up by journalling in memory; in case of a crash the database
        #     # will likely go corrupt.
        #     # NB: This setting is scoped to this connection.
        #     connection.execute(text("PRAGMA journal_mode = MEMORY"))

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table=constants.VERSION_TABLE_NAME,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise ValueError("Offline mode is not supported")
else:
    run_migrations_online()
