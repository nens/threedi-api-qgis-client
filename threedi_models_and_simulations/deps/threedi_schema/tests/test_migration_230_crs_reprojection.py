import sqlite3

import pytest

from threedi_schema import ModelSchema
from threedi_schema.application.errors import InvalidSRIDException


@pytest.mark.parametrize("epsg_code", [
    999999, # non-existing
    2227, # projected / US survey foot
    4979, # not project
])
def test_check_valid_crs(in_memory_sqlite, epsg_code):
    schema = in_memory_sqlite.schema
    schema.upgrade(revision="0229", backup=False)
    schema._set_custom_epsg_code(epsg_code)
    with pytest.raises(InvalidSRIDException) as exc_info:
        schema.upgrade(backup=False)


def test_migration(tmp_path_factory, oldest_sqlite):
    schema = ModelSchema(oldest_sqlite)
    schema.upgrade(backup=False, revision="0230")
    cursor = sqlite3.connect(schema.db.path).cursor()
    query = cursor.execute("SELECT srid FROM geometry_columns where f_table_name = 'geom'")
    epsg_matches = [int(item[0])==28992 for item in query.fetchall()]
    assert all(epsg_matches)


