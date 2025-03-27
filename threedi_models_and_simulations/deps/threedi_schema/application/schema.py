import warnings
from pathlib import Path
from typing import Optional, Tuple

# This import is needed for alembic to recognize the geopackage dialect
import geoalchemy2.alembic_helpers  # noqa: F401
import sqlalchemy as sa
from alembic import command as alembic_command
from alembic.config import Config
from alembic.environment import EnvironmentContext
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from geoalchemy2.admin.dialects.geopackage import create_spatial_ref_sys_view
from geoalchemy2.functions import ST_SRID
from osgeo import gdal, ogr, osr
from sqlalchemy import Column, Integer, MetaData, Table, text
from sqlalchemy.exc import IntegrityError

from ..domain import constants, models
from ..infrastructure.spatial_index import ensure_spatial_indexes
from ..infrastructure.spatialite_versions import copy_models, get_spatialite_version
from .errors import InvalidSRIDException, MigrationMissingError, UpgradeFailedError
from .upgrade_utils import setup_logging

gdal.UseExceptions()

__all__ = ["ModelSchema"]


def get_alembic_config(engine=None, unsafe=False):
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "threedi_schema:migrations")
    alembic_cfg.set_main_option("version_table", constants.VERSION_TABLE_NAME)
    if engine is not None:
        alembic_cfg.attributes["engine"] = engine
    alembic_cfg.attributes["unsafe"] = unsafe
    return alembic_cfg


def get_schema_version():
    """Returns the version of the schema in this library"""
    config = get_alembic_config()
    script = ScriptDirectory.from_config(config)
    with EnvironmentContext(config=config, script=script) as env:
        return int(env.get_head_revision())


def _upgrade_database(db, revision="head", unsafe=True, config=None):
    """Upgrade ThreediDatabase instance"""
    engine = db.engine
    if config is None:
        config = get_alembic_config(engine, unsafe=unsafe)
    alembic_command.upgrade(config, revision)


class GdalErrorHandler:
    def __call__(self, err_level, err_no, err_msg):
        self.err_level = err_level
        self.err_no = err_no
        self.err_msg = err_msg


class ModelSchema:
    def __init__(self, threedi_db, declared_models=models.DECLARED_MODELS):
        self.db = threedi_db
        self.declared_models = declared_models

    def _get_version_old(self):
        """The version of the database using the old 'south' versioning."""
        south_migrationhistory = Table(
            "south_migrationhistory", MetaData(), Column("id", Integer)
        )
        engine = self.db.engine
        if not self.db.has_table("south_migrationhistory"):
            return
        with engine.connect() as connection:
            query = south_migrationhistory.select().order_by(
                south_migrationhistory.columns["id"].desc()
            )
            versions = list(connection.execute(query.limit(1)))
            if len(versions) == 1:
                return versions[0][0]
            else:
                return None

    def get_version(self):
        """Returns the id (integer) of the latest migration"""
        with self.db.engine.connect() as connection:
            context = MigrationContext.configure(
                connection, opts={"version_table": constants.VERSION_TABLE_NAME}
            )
            version = context.get_current_revision()
        if version is not None:
            return int(version)
        else:
            return self._get_version_old()

    def _get_epsg_data(self) -> Tuple[Optional[int], str]:
        """
        Retrieve epsg code for schematisation loaded in session. This is done by
        iterating over all geometries in the declared models and all raster files, and
        stopping at the first geometry or raster file with data.

        Returns the epsg code and the name (table.column) of the source.
        """
        session = self.db.get_session()
        version = self.get_version()

        # for revision < 230 read explicit epsg from schematisation
        if version is not None and version < 230:
            try:
                epsg_code = get_model_srid(
                    connection=session, v2_global_settings=version < 222
                )
            except InvalidSRIDException:
                return None, ""

            return (
                epsg_code,
                "v2_global_settings.epsg_code"
                if version < 222
                else "model_settings.epsg_code",
            )
        # for version 230 (implicit crs in spatialite) get epsg from first geometry object found in the model
        elif version == 230:
            for model in self.declared_models:
                if hasattr(model, "geom"):
                    srids = [
                        item[0] for item in session.query(ST_SRID(model.geom)).all()
                    ]
                    if len(srids) > 0:
                        return srids[0], f"{model.__tablename__}.geom"
            return None, ""
        # for version >= 300 (implicit crs in geopackage) get epsg from connection_node table in geopackage
        else:
            datasource = ogr.Open(str(self.db.path))
            layer = datasource.GetLayerByName("connection_node")
            epsg = layer.GetSpatialRef().GetAuthorityCode(None)
            try:
                epsg = int(epsg)
            except TypeError:
                raise InvalidSRIDException(epsg, "the epsg_code must be an integer")
            return epsg, ""

    def _get_dem_epsg(self, raster_path: str = None) -> int:
        """
        Extract EPSG code from DEM.

        Only works in local filesystem. The raster path references do not resolve correctly in the object store.
        """
        if not raster_path:
            with self.db.get_session() as session:
                settings_table = (
                    "v2_global_settings"
                    if self.get_version() < 222
                    else "model_settings"
                )
                raster_path = session.execute(
                    text(f"SELECT dem_file FROM {settings_table};")
                ).scalar()
            if raster_path is None:
                raise InvalidSRIDException(None, "no DEM is provided")
        # old dem paths include rasters/ but new ones do not
        # to work around this, we remove "rasters/" if present and then add it again
        raster_path = raster_path.replace("\\", "/").split("/")[-1]
        directory = Path(self.db.path).parent
        raster_path = str(directory / "rasters" / Path(raster_path))
        try:
            dataset = gdal.Open(raster_path)
        except RuntimeError as e:
            raise InvalidSRIDException(f"Cannot open filepath {raster_path}") from e
        proj = osr.SpatialReference(wkt=dataset.GetProjection())
        return int(proj.GetAuthorityCode("PROJCS"))

    @property
    def epsg_code(self):
        """
        Raises threedi_schema.migrations.exceptions.InvalidSRIDException if the epsg_code count not be determined or is invalid.
        """
        return self._get_epsg_data()[0]

    @property
    def epsg_source(self):
        """
        Raises threedi_schema.migrations.exceptions.InvalidSRIDException if the epsg_code count not be determined or is invalid.
        """
        return self._get_epsg_data()[1]

    @property
    def is_geopackage(self):
        with self.db.get_session() as session:
            return bool(
                session.execute(
                    text(
                        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='gpkg_contents';"
                    )
                ).scalar()
            )

    @property
    def is_spatialite(self):
        with self.db.get_session() as session:
            return bool(
                session.execute(
                    text(
                        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='spatial_ref_sys';"
                    )
                ).scalar()
            )

    def upgrade(
        self,
        revision="head",
        backup=True,
        upgrade_spatialite_version=False,
        progress_func=None,
        epsg_code_override=None,
    ):
        """Upgrade the database to the latest version.

        This requires either a completely empty database or a database with its
        current schema version at least 174 (the latest migration of the old
        model databank).

        The upgrade is done using database transactions. However, for SQLite,
        database transactions are only partially supported. To ensure that the
        database file does not become corrupt, enable the "backup" parameter.
        If the database is temporary already (or if it is PostGIS), disable
        it.

        Specify 'upgrade_spatialite_version=True' to also upgrade the
        spatialite file version after the upgrade.

        Specify a 'progress_func' to handle progress updates. `progress_func` should
        expect two arguments: the percentage of progress and a string describing the migration step

        Specify a `epsg_code_override` to set the model epsg_code before migration.
        This can be used for testing and for setting the DEM epsg_code when self.epsg_code is None.
        """
        try:
            rev_nr = get_schema_version() if revision == "head" else int(revision)
        except ValueError:
            raise ValueError(
                f"Incorrect version format: {revision}. Expected 'head' or a numeric value."
            )
        v = self.get_version()

        if v is not None and v < constants.LATEST_SOUTH_MIGRATION_ID:
            raise MigrationMissingError(
                f"This tool cannot update versions below "
                f"{constants.LATEST_SOUTH_MIGRATION_ID}. Please consult the "
                f"3Di documentation on how to update legacy databases."
            )
        if (
            v is not None
            and v <= constants.LAST_SPTL_SCHEMA_VERSION
            and not self.is_spatialite
        ):
            raise UpgradeFailedError(
                f"Cannot upgrade from {revision=} because {self.db.path} is not a spatialite"
            )
        elif (
            v is not None
            and v > constants.LAST_SPTL_SCHEMA_VERSION
            and not self.is_geopackage
        ):
            raise UpgradeFailedError(
                f"Cannot upgrade from {revision=} because {self.db.path} is not a geopackage"
            )

        config = None
        if progress_func is not None:
            config = get_alembic_config(self.db.engine, unsafe=backup)
            setup_logging(self.db.schema, revision, config, progress_func)

        def run_upgrade(_revision):
            if backup:
                with self.db.file_transaction() as work_db:
                    _upgrade_database(
                        work_db,
                        revision=_revision,
                        unsafe=True,
                        config=config,
                    )
            else:
                _upgrade_database(
                    self.db,
                    revision=_revision,
                    unsafe=False,
                    config=config,
                )

        if epsg_code_override is not None:
            if self.get_version() is not None and self.get_version() > 229:
                warnings.warn(
                    "Cannot set epsg_code_override when upgrading from 230 or newer"
                )
            elif rev_nr < 230:
                warnings.warn(
                    "Warning: cannot set epsg_code_override when upgrading to 229 or older."
                )
            else:
                if self.get_version() is None or self.get_version() < 229:
                    run_upgrade("0229")
                self._set_custom_epsg_code(epsg_code_override)
                run_upgrade("0230")
                self._remove_temporary_model_settings()
        # First upgrade to LAST_SPTL_SCHEMA_VERSION.
        # When the requested revision <= LAST_SPTL_SCHEMA_VERSION, this is the only upgrade step
        run_upgrade(
            revision
            if rev_nr <= constants.LAST_SPTL_SCHEMA_VERSION
            else f"{constants.LAST_SPTL_SCHEMA_VERSION:04d}"
        )
        # only upgrade spatialite version is target revision is <= LAST_SPTL_SCHEMA_VERSION
        if rev_nr <= constants.LAST_SPTL_SCHEMA_VERSION and upgrade_spatialite_version:
            self.upgrade_spatialite_version()
        # Finish upgrade if target revision > LAST_SPTL_SCHEMA_VERSION
        elif rev_nr > constants.LAST_SPTL_SCHEMA_VERSION:
            self.convert_to_geopackage()
            run_upgrade(revision)

    def _set_custom_epsg_code(self, custom_epsg_code: int):
        """Temporarily set epsg code in model settings for migration 230"""
        if (
            self.get_version() is None
            or self.get_version() < 222
            or self.get_version() > 229
        ):
            raise ValueError(f"Cannot set epsg code for revision {self.get_version()}")
        # modify epsg_code
        with self.db.get_session() as session:
            settings_row_count = session.execute(
                text("SELECT COUNT(id) FROM model_settings;")
            ).scalar()
            # to update empty databases, they must have model_settings.epsg_code set
            if settings_row_count == 0:
                session.execute(
                    text(
                        f"INSERT INTO model_settings (id, epsg_code) VALUES (99999, {custom_epsg_code});"
                    )
                )
            else:
                session.execute(
                    text(f"UPDATE model_settings SET epsg_code = {custom_epsg_code};")
                )
            session.commit()

    def _remove_temporary_model_settings(self):
        """Remove temporary model settings entry introduced for the epsg code"""
        with self.db.get_session() as session:
            session.execute(text("DELETE FROM model_settings WHERE id = 99999;"))
            session.commit()

    def validate_schema(self):
        """Very basic validation of 3Di schema.

        Check that the database has the latest migration applied. If the
        latest migrations is applied, we assume the database also contains all
        tables and columns defined in threedi_model.models.py.

        :return: True if the threedi_db schema is valid, raises an error otherwise.
        :raise MigrationMissingError, MigrationTooHighError
        """
        version = self.get_version()
        schema_version = get_schema_version()
        if version is None or version < schema_version:
            raise MigrationMissingError(
                f"This tool requires at least schema version "
                f"{schema_version}. Current version: {version}."
            )

        if version > schema_version:
            warnings.warn(
                f"The database version is higher than the threedi-schema version "
                f"({version} > {schema_version}). This may lead to unexpected "
                f"results. "
            )
        return True

    def set_spatial_indexes(self):
        """(Re)create spatial indexes in the spatialite according to the latest definitions."""
        version = self.get_version()
        schema_version = get_schema_version()
        if version != schema_version:
            raise MigrationMissingError(
                f"Setting views requires schema version "
                f"{schema_version}. Current version: {version}."
            )

        ensure_spatial_indexes(self.db.engine, models.DECLARED_MODELS)

    def upgrade_spatialite_version(self):
        """Upgrade the version of the spatialite file to the version of the
        current spatialite library.

        Does nothing if the current file version > 3 or if the current library
        version is not 4 or 5.

        Raises UpgradeFailedError if there are any SQL constraints violated.
        """
        lib_version, file_version = get_spatialite_version(self.db)
        if file_version == 3 and lib_version in (4, 5):
            if self.get_version() != constants.LAST_SPTL_SCHEMA_VERSION:
                raise MigrationMissingError(
                    f"This tool requires schema version "
                    f"{constants.LAST_SPTL_SCHEMA_VERSION:}. Current version: {self.get_version()}."
                )
            with self.db.file_transaction(start_empty=True) as work_db:
                rev_nr = min(get_schema_version(), 229)
                first_rev = f"{rev_nr:04d}"
                _upgrade_database(work_db, revision=first_rev, unsafe=True)
                with self.db.get_session() as session:
                    srid = session.execute(
                        text(
                            "SELECT srid FROM geometry_columns WHERE f_geometry_column = 'geom' AND f_table_name NOT LIKE '_alembic%';"
                        )
                    ).fetchone()[0]
                with work_db.get_session() as session:
                    session.execute(
                        text(f"INSERT INTO model_settings (epsg_code) VALUES ({srid});")
                    )
                    session.commit()
                if get_schema_version() > 229:
                    _upgrade_database(work_db, revision="head", unsafe=True)
                with work_db.get_session() as session:
                    session.execute(text("DELETE FROM model_settings;"))
                    session.commit()
                try:
                    copy_models(self.db, work_db, self.declared_models)
                except IntegrityError as e:
                    raise UpgradeFailedError(e.orig.args[0])

    def convert_to_geopackage(self):
        """
        Convert spatialite to geopackage using gdal.VectorTranslate.

        Does nothing if the current database is already a geopackage.

        Raises UpgradeFailedError if the conversion of spatialite to geopackage with VectorTranslate fails.
        """

        handler = GdalErrorHandler()
        gdal.PushErrorHandler(handler)
        gdal.UseExceptions()

        warnings_list = []

        if self.is_geopackage:
            return

        # Ensure database is upgraded and views are recreated
        revision = self.get_version()
        if revision is None or revision < constants.LAST_SPTL_SCHEMA_VERSION:
            self.upgrade(
                revision=f"{constants.LAST_SPTL_SCHEMA_VERSION:04d}", backup=False
            )
        elif revision > constants.LAST_SPTL_SCHEMA_VERSION:
            UpgradeFailedError(
                f"Cannot convert schema version {revision} to geopackage"
            )
        # Make necessary modifications for conversion on temporary database
        with self.db.file_transaction(start_empty=False, copy_results=False) as work_db:
            # remove spatialite specific tables that break conversion
            with work_db.get_session() as session:
                session.execute(text("DROP TABLE IF EXISTS spatialite_history;"))
                session.execute(text("DROP TABLE IF EXISTS views_geometry_columns;"))

                all_tablenames = [model.__tablename__ for model in self.declared_models]
                geometry_tablenames = (
                    session.execute(text("SELECT f_table_name FROM geometry_columns;"))
                    .scalars()
                    .all()
                )
                non_geometry_tablenames = list(
                    set(all_tablenames) - set(geometry_tablenames)
                )

                if (
                    session.execute(
                        text(
                            "SELECT count(*) FROM sqlite_master WHERE name='schema_version';"
                        )
                    ).scalar()
                    > 0
                ):
                    non_geometry_tablenames.append("schema_version")

            infile = str(work_db.path)
            outfile = str(Path(self.db.path).with_suffix(".gpkg"))

            conversion_list = []
            conversion_list.append(
                gdal.VectorTranslateOptions(
                    format="gpkg",
                    skipFailures=True,
                )
            )
            for table in non_geometry_tablenames:
                conversion_list.append(
                    gdal.VectorTranslateOptions(
                        format="gpkg",
                        accessMode="update",
                        layers=[table],
                        layerName=table,
                        options=["-preserve_fid"],
                    )
                )
            for conversion_options in conversion_list:
                try:
                    ds = gdal.VectorTranslate(
                        destNameOrDestDS=outfile,
                        srcDS=infile,
                        options=conversion_options,
                    )
                    # dereference dataset before writing additional layers to ensure the data is written
                    del ds
                except RuntimeError as err:
                    raise UpgradeFailedError from err
                else:
                    if (
                        hasattr(handler, "err_level")
                        and handler.err_level >= gdal.CE_Warning
                        and handler.err_msg != "Feature id 0 not preserved"
                    ):
                        warnings_list.append(handler.err_msg)

            if len(warnings_list) > 0:
                warning_string = "\n".join(
                    ["GeoPackage conversion didn't finish as expected:"] + warnings_list
                )
                warnings.warn(warning_string)

        # Correct path of current database
        self.db.path = Path(self.db.path).with_suffix(".gpkg")
        # Reset engine so new path is used on the next call of get_engine()
        self.db._engine = None
        # Recreate views_geometry_columns so set_views works as expected
        with self.db.get_session() as session:
            session.execute(
                text(
                    "CREATE TABLE views_geometry_columns(view_name TEXT, view_geometry TEXT, view_rowid TEXT, f_table_name VARCHAR(256), f_geometry_column VARCHAR(256))"
                )
            )
            create_spatial_ref_sys_view(session)
        ensure_spatial_indexes(self.db.engine, models.DECLARED_MODELS)


def get_model_srid(connection, v2_global_settings: bool = False) -> int:
    table = "v2_global_settings" if v2_global_settings else "model_settings"
    srid_str = connection.execute(sa.text(f"SELECT epsg_code FROM {table}")).fetchone()
    if srid_str is None or srid_str[0] is None:
        raise InvalidSRIDException(None, "no epsg_code is defined")
    try:
        srid = int(srid_str[0])
    except TypeError:
        raise InvalidSRIDException(srid_str[0], "the epsg_code must be an integer")
    return srid
