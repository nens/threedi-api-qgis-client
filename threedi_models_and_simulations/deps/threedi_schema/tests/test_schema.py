from unittest import mock

import pytest
from sqlalchemy import Column, inspect, Integer, MetaData, String, Table, text

from threedi_schema import ModelSchema
from threedi_schema.application import errors
from threedi_schema.application.schema import get_schema_version
from threedi_schema.domain import constants
from threedi_schema.domain.models import DECLARED_MODELS
from threedi_schema.infrastructure.spatial_index import get_missing_spatial_indexes
from threedi_schema.infrastructure.spatialite_versions import get_spatialite_version


@pytest.fixture
def south_migration_table(in_memory_sqlite):
    south_migrationhistory = Table(
        "south_migrationhistory", MetaData(), Column("id", Integer)
    )
    engine = in_memory_sqlite.engine
    south_migrationhistory.create(engine)
    return south_migrationhistory


@pytest.fixture
def alembic_version_table(in_memory_sqlite):
    alembic_version = Table(
        constants.VERSION_TABLE_NAME,
        MetaData(),
        Column("version_num", String(32), nullable=False),
    )
    engine = in_memory_sqlite.engine
    alembic_version.create(engine)
    return alembic_version


def test_get_schema_version():
    """The current version in the library. We start counting at 200."""
    # this will catch future mistakes of setting non-integer revisions
    assert get_schema_version() >= 200


def test_get_version_no_tables(in_memory_sqlite):
    """Get the version of a sqlite with no version tables"""
    schema_checker = ModelSchema(in_memory_sqlite)
    migration_id = schema_checker.get_version()
    assert migration_id is None


def test_get_version_empty_south(in_memory_sqlite, south_migration_table):
    """Get the version of a sqlite with an empty South version table"""
    schema_checker = ModelSchema(in_memory_sqlite)
    migration_id = schema_checker.get_version()
    assert migration_id is None


def test_get_version_south(in_memory_sqlite, south_migration_table):
    """Get the version of a sqlite with a South version table"""
    with in_memory_sqlite.engine.connect() as connection:
        with connection.begin():
            for v in (42, 43):
                connection.execute(south_migration_table.insert().values(id=v))

    schema_checker = ModelSchema(in_memory_sqlite)
    migration_id = schema_checker.get_version()
    assert migration_id == 43


def test_get_version_empty_alembic(in_memory_sqlite, alembic_version_table):
    """Get the version of a sqlite with an empty alembic version table"""
    schema_checker = ModelSchema(in_memory_sqlite)
    migration_id = schema_checker.get_version()
    assert migration_id is None


def test_get_version_alembic(in_memory_sqlite, alembic_version_table):
    """Get the version of a sqlite with an alembic version table"""
    with in_memory_sqlite.engine.connect() as connection:
        with connection.begin():
            connection.execute(
                alembic_version_table.insert().values(version_num="0201")
            )

    schema_checker = ModelSchema(in_memory_sqlite)
    migration_id = schema_checker.get_version()
    assert migration_id == 201


def test_validate_schema(sqlite_latest):
    """Validate a correct schema version"""
    schema = sqlite_latest.schema
    with mock.patch.object(schema, "get_version", return_value=get_schema_version()):
        assert schema.validate_schema()


@pytest.mark.parametrize("version", [-1, 205, None])
def test_validate_schema_missing_migration(sqlite_latest, version):
    """Validate a too low schema version"""
    schema = ModelSchema(sqlite_latest)
    with mock.patch.object(schema, "get_version", return_value=version):
        with pytest.raises(errors.MigrationMissingError):
            schema.validate_schema()


@pytest.mark.parametrize("version", [9999])
def test_validate_schema_too_high_migration(sqlite_latest, version):
    """Validate a too high schema version"""
    schema = ModelSchema(sqlite_latest)
    with mock.patch.object(schema, "get_version", return_value=version):
        with pytest.warns(UserWarning):
            schema.validate_schema()


def get_sql_tables(cursor):
    return [
        item[0]
        for item in cursor.execute(
            text("SELECT name FROM sqlite_master WHERE type='table';")
        ).fetchall()
    ]


def get_columns_from_schema(schema, table_name):
    inspector = inspect(schema.db.get_engine())
    return [column["name"] for column in inspector.get_columns(table_name)]


def get_columns_from_sqlite(session, table_name):
    res = session.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return [col_info[1] for col_info in res]


def test_full_upgrade_oldest(oldest_sqlite):
    """Upgrade a legacy database to the latest version"""
    schema = ModelSchema(oldest_sqlite)
    schema.upgrade(backup=False, upgrade_spatialite_version=False)
    run_upgrade_test(schema)


def test_full_upgrade_empty(empty_sqlite_v4):
    """Upgrade an empty database to the latest version"""
    schema = ModelSchema(empty_sqlite_v4)
    schema.upgrade(
        backup=False, upgrade_spatialite_version=False, epsg_code_override=28992
    )
    run_upgrade_test(schema)


def test_full_upgrade_with_preexisting_version(south_latest_sqlite):
    """Upgrade an empty database to the latest version"""
    schema = ModelSchema(south_latest_sqlite)
    schema.upgrade(
        backup=False, upgrade_spatialite_version=False, epsg_code_override=28992
    )
    run_upgrade_test(schema)


def run_upgrade_test(schema):
    assert schema.get_version() == get_schema_version()
    session = schema.db.get_session()
    sqlite_tables = get_sql_tables(session)
    schema_tables = [model.__tablename__ for model in schema.declared_models]
    assert set(schema_tables).issubset(set(sqlite_tables))
    for table in schema_tables:
        schema_cols = get_columns_from_schema(schema, table)
        sqlite_cols = get_columns_from_sqlite(session, table)
        assert set(schema_cols).issubset(set(sqlite_cols))
    assert get_missing_spatial_indexes(schema.db.engine, DECLARED_MODELS) == []


def test_upgrade_with_epsg_code_override(in_memory_sqlite):
    """Upgrade an empty database to the latest version and set custom epsg"""
    schema = ModelSchema(in_memory_sqlite)
    schema.upgrade(
        revision="0230",
        backup=False,
        upgrade_spatialite_version=False,
        epsg_code_override=28992,
    )
    with schema.db.get_session() as session:
        srids = [
            item[0]
            for item in session.execute(
                text(
                    "SELECT srid FROM geometry_columns WHERE f_table_name NOT LIKE '_%'"
                )
            ).fetchall()
        ]
        assert all([srid == 28992 for srid in srids])


def test_upgrade_with_epsg_code_override_version_too_new(empty_sqlite_v4):
    """Set custom epsg code for schema version > 229"""
    schema = ModelSchema(empty_sqlite_v4)
    schema.upgrade(
        revision="0230",
        backup=False,
        upgrade_spatialite_version=False,
        epsg_code_override=28992,
    )
    with pytest.warns():
        schema.upgrade(
            backup=False, upgrade_spatialite_version=False, epsg_code_override=28992
        )


def test_upgrade_with_epsg_code_override_revision_too_old(in_memory_sqlite):
    """Set custom epsg code when upgrading to 228 or older"""
    schema = ModelSchema(in_memory_sqlite)
    with pytest.warns():
        schema.upgrade(
            revision="0228",
            backup=False,
            upgrade_spatialite_version=False,
            epsg_code_override=28992,
        )


def test_set_custom_epsg_valid(in_memory_sqlite):
    schema = ModelSchema(in_memory_sqlite)
    schema.upgrade(revision="0229", backup=False, upgrade_spatialite_version=False)
    schema._set_custom_epsg_code(custom_epsg_code=28992)
    with in_memory_sqlite.engine.connect() as connection:
        check_result = connection.execute(
            text("SELECT epsg_code FROM model_settings")
        ).scalar()
    assert check_result == 28992


@pytest.mark.parametrize(
    "start_revision, epsg_code_override",
    [(None, None), ("0220", None), ("0230", 28992)],
)
def test_set_custom_epsg_invalid_revision(
    in_memory_sqlite, start_revision, epsg_code_override
):
    schema = ModelSchema(in_memory_sqlite)
    if start_revision is not None:
        schema.upgrade(
            revision=start_revision,
            backup=False,
            upgrade_spatialite_version=False,
            epsg_code_override=epsg_code_override,
        )
    with pytest.raises(ValueError):
        schema._set_custom_epsg_code(custom_epsg_code=28992)


def test_upgrade_south_not_latest_errors(in_memory_sqlite):
    """Upgrading a database that is not at the latest south migration will error"""
    schema = ModelSchema(in_memory_sqlite)
    with mock.patch.object(
        schema, "get_version", return_value=constants.LATEST_SOUTH_MIGRATION_ID - 1
    ):
        with pytest.raises(errors.MigrationMissingError):
            schema.upgrade(backup=False, upgrade_spatialite_version=False)


def test_upgrade_with_backup(south_latest_sqlite):
    """Upgrading with backup=True will proceed on a copy of the database"""
    schema = ModelSchema(south_latest_sqlite)
    with mock.patch(
        "threedi_schema.application.schema._upgrade_database", side_effect=RuntimeError
    ) as upgrade, mock.patch.object(schema, "get_version", return_value=199):
        with pytest.raises(RuntimeError):
            schema.upgrade(backup=True, upgrade_spatialite_version=False)

    (db,), kwargs = upgrade.call_args
    assert db is not south_latest_sqlite


def test_upgrade_without_backup(south_latest_sqlite):
    """Upgrading with backup=True will proceed on the database itself"""
    schema = ModelSchema(south_latest_sqlite)
    with mock.patch(
        "threedi_schema.application.schema._upgrade_database", side_effect=RuntimeError
    ) as upgrade, mock.patch.object(schema, "get_version", return_value=199):
        with pytest.raises(RuntimeError):
            schema.upgrade(backup=False, upgrade_spatialite_version=False)

    (db,), kwargs = upgrade.call_args
    assert db is south_latest_sqlite


@pytest.mark.parametrize(
    "is_var, version",
    [("is_spatialite", constants.LAST_SPTL_SCHEMA_VERSION), ("is_geopackage", 300)],
)
def test_upgrade_incorrect_format(in_memory_sqlite, is_var, version):
    schema = ModelSchema(in_memory_sqlite)
    with mock.patch.object(
        type(schema), is_var, new=mock.PropertyMock(return_value=False)
    ):
        with mock.patch.object(type(schema), "get_version", return_value=version):
            with pytest.raises(errors.UpgradeFailedError):
                schema.upgrade()


def test_upgrade_revision_exception(oldest_sqlite):
    schema = ModelSchema(oldest_sqlite)
    with pytest.raises(ValueError):
        schema.upgrade(revision="foo")


def test_upgrade_spatialite_3(oldest_sqlite):
    lib_version, file_version_before = get_spatialite_version(oldest_sqlite)
    if lib_version == file_version_before:
        pytest.skip("Nothing to test: spatialite library version equals file version")

    schema = ModelSchema(oldest_sqlite)
    schema.upgrade(
        backup=False,
        upgrade_spatialite_version=True,
        revision=f"{constants.LAST_SPTL_SCHEMA_VERSION:04d}",
    )

    _, file_version_after = get_spatialite_version(oldest_sqlite)
    assert file_version_after == 4

    # the spatial indexes are there
    with oldest_sqlite.engine.connect() as connection:
        check_result = connection.execute(
            text("SELECT CheckSpatialIndex('connection_node', 'geom')")
        ).scalar()
    assert check_result == 1


# TODO: remove this because ensure_spatial_indexes is already tested
@pytest.mark.skip(reason="will be removed")
def test_set_spatial_indexes(in_memory_sqlite):
    engine = in_memory_sqlite.engine

    schema = ModelSchema(in_memory_sqlite)
    schema.upgrade(backup=False, epsg_code_override=28992)

    with engine.connect() as connection:
        with connection.begin():
            connection.execute(
                text("SELECT DisableSpatialIndex('connection_node', 'geom')")
            ).scalar()
            connection.execute(text("DROP TABLE idx_connection_node_geom"))

    schema.set_spatial_indexes()

    with engine.connect() as connection:
        check_result = connection.execute(
            text("SELECT CheckSpatialIndex('connection_node', 'geom')")
        ).scalar()

    assert check_result == 1


class TestGetEPSGData:
    def test_no_epsg(self, empty_sqlite_v4):
        schema = ModelSchema(empty_sqlite_v4)
        schema.upgrade(
            backup=False, upgrade_spatialite_version=False, epsg_code_override=28992
        )
        assert schema.epsg_code is None
        assert schema.epsg_source == ""

    def test_with_epsg(self, oldest_sqlite):
        schema = ModelSchema(oldest_sqlite)
        schema.upgrade(backup=False, upgrade_spatialite_version=False)
        assert schema.epsg_code == 28992
        assert schema.epsg_source == "boundary_condition_1d.geom"


def test_is_spatialite(in_memory_sqlite):
    schema = ModelSchema(in_memory_sqlite)
    schema.upgrade(
        backup=False,
        upgrade_spatialite_version=False,
        epsg_code_override=28992,
        revision=f"{constants.LAST_SPTL_SCHEMA_VERSION:04d}",
    )
    assert schema.is_spatialite


def test_is_geopackage(oldest_sqlite):
    schema = ModelSchema(oldest_sqlite)
    schema.upgrade(
        backup=False,
        upgrade_spatialite_version=False,
        epsg_code_override=28992,
        revision=f"{constants.LAST_SPTL_SCHEMA_VERSION:04d}",
    )
    schema.convert_to_geopackage()
    assert schema.is_geopackage


def test_epsg_code(oldest_sqlite):
    schema = ModelSchema(oldest_sqlite)
    schema.upgrade(revision="0221", backup=False)
    assert schema.epsg_code == 28992
    assert schema.epsg_source == "v2_global_settings.epsg_code"

    schema.upgrade(revision="0229", backup=False)
    assert schema.get_version() == 229
    assert schema.epsg_code == 28992
    assert schema.epsg_source == "model_settings.epsg_code"

    schema.upgrade(revision="0230", backup=False)
    assert schema.get_version() == 230
    assert schema.epsg_code == 28992
    assert schema.epsg_source == "boundary_condition_1d.geom"


def test_epsg_code_from_dem(sqlite_with_dem):
    schema = ModelSchema(sqlite_with_dem)
    assert schema._get_dem_epsg() == 28991
    schema.upgrade(epsg_code_override=schema._get_dem_epsg())
    assert schema._get_dem_epsg() == 28991
