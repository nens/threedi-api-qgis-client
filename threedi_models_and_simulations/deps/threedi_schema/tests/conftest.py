import os
import pathlib
import shutil

import pytest

from threedi_schema import ThreediDatabase

data_dir = pathlib.Path(__file__).parent / "data"


def pytest_sessionstart(session):
    """
    Called after the Session object has been created and
    before performing collection and entering the run test loop.
    """
    os.environ["SQLALCHEMY_SILENCE_UBER_WARNING"] = "1"


@pytest.fixture
def empty_sqlite_v3(tmp_path):
    """A function-scoped empty spatialite v3 in the latest migration state"""
    tmp_sqlite = tmp_path / "empty_v3.sqlite"
    shutil.copyfile(data_dir / "empty_v3.sqlite", tmp_sqlite)
    return ThreediDatabase(tmp_sqlite)


@pytest.fixture
def empty_sqlite_v4(tmp_path):
    """An function-scoped empty spatialite v4 in the latest migration state"""
    tmp_sqlite = tmp_path / "empty_v4.sqlite"
    shutil.copyfile(data_dir / "empty_v4.sqlite", tmp_sqlite)
    return ThreediDatabase(tmp_sqlite)


@pytest.fixture
def south_latest_sqlite(tmp_path):
    """An empty SQLite that is in its latest South migration state"""
    tmp_sqlite = tmp_path / "south_latest.sqlite"
    shutil.copyfile(data_dir / "south_latest.sqlite", tmp_sqlite)
    return ThreediDatabase(tmp_sqlite)


@pytest.fixture
def oldest_sqlite(tmp_path):
    """A real SQLite that is in its oldest possible south migration state (160)"""
    tmp_sqlite = tmp_path / "noordpolder.sqlite"
    shutil.copyfile(data_dir / "noordpolder.sqlite", tmp_sqlite)
    return ThreediDatabase(tmp_sqlite)


@pytest.fixture
def in_memory_sqlite():
    """An in-memory database with no schema"""
    return ThreediDatabase("")


@pytest.fixture
def sqlite_latest(empty_sqlite_v4):
    """An in-memory database with the latest schema version"""
    empty_sqlite_v4.schema.upgrade("head", backup=False, epsg_code_override=28992)
    return empty_sqlite_v4
