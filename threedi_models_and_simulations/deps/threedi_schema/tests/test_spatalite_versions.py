from sqlalchemy import Column, func, Integer, String
from sqlalchemy.orm import declarative_base

from threedi_schema.domain.custom_types import Geometry
from threedi_schema.infrastructure.spatialite_versions import (
    copy_model,
    get_spatialite_version,
)


def test_get_spatialite_version(empty_sqlite_v3):
    lib_version, file_version = get_spatialite_version(empty_sqlite_v3)
    assert lib_version in (3, 4, 5)
    assert file_version == 3


def test_copy_model(empty_sqlite_v3, empty_sqlite_v4):
    db_from = empty_sqlite_v3
    db_to = empty_sqlite_v4
    # Create v2_grid_refinement_area on the fly to match database scheme in the used sqlitest
    Base = declarative_base()
    TestModel = type(
        "TestModel",
        (Base,),
        {
            "__tablename__": "v2_connection_nodes",
            "id": Column(Integer, primary_key=True),
            "code": Column(String(100)),
            "the_geom": Column(
                Geometry("POINT")
            ),  # Use Text as a placeholder for Geometry
        },
    )
    # Add a record to 'db_from'
    obj = TestModel(id=3, code="test", the_geom="SRID=4326;POINT(-71.064544 42.287870)")
    with db_from.session_scope() as session:
        session.add(obj)
        session.commit()

    # Copy it
    copy_model(db_from, db_to, TestModel)

    # Check if it is present in 'db_to'
    with db_to.session_scope() as session:
        records = list(
            session.query(
                TestModel.id,
                TestModel.code,
                func.ST_AsText(TestModel.the_geom),
            )
        )

        assert records == [(3, "test", "POINT(-71.064544 42.28787)")]


def test_copy_invalid_geometry(empty_sqlite_v3, empty_sqlite_v4):
    """Copying an invalid geometry (ST_IsValid evaluates to False) is possible"""
    db_from = empty_sqlite_v3
    db_to = empty_sqlite_v4
    # Create v2_grid_refinement_area on the fly to match database scheme in the used sqlitest
    Base = declarative_base()
    TestModel = type(
        "TestModel",
        (Base,),
        {
            "__tablename__": "v2_grid_refinement_area",
            "id": Column(Integer, primary_key=True),
            "display_name": Column(String(255)),
            "code": Column(String(100)),
            "the_geom": Column(
                Geometry("POINT")
            ),  # Use Text as a placeholder for Geometry
        },
    )
    obj = TestModel(
        id=3,
        code="test",
        display_name="test",
        the_geom="SRID=4326;POLYGON((0 0, 10 10, 0 10, 10 0, 0 0))",
    )
    with db_from.session_scope() as session:
        session.add(obj)
        session.commit()

    copy_model(db_from, db_to, TestModel)

    with db_to.session_scope() as session:
        records = list(
            session.query(
                TestModel.id,
                func.ST_AsText(TestModel.the_geom),
            )
        )

        assert records == [(3, "POLYGON((0 0, 10 10, 0 10, 10 0, 0 0))")]
