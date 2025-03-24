import pytest
from geoalchemy2 import Geometry
from sqlalchemy import Column, Integer, create_engine, func
from sqlalchemy.event import listen
from sqlalchemy.orm import declarative_base, sessionmaker
from threedi_schema.application.threedi_database import load_spatialite
from threedi_schema.infrastructure.spatial_index import (
    create_spatial_index,
    ensure_spatial_indexes,
    get_missing_spatial_indexes,
)

Base = declarative_base()


class Model(Base):
    __tablename__ = "model"

    id = Column(Integer, primary_key=True)
    geom = Column(Geometry("POINT"))


@pytest.fixture()
def engine():
    engine = create_engine("sqlite:///:memory:")
    listen(engine, "connect", load_spatialite)

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.execute(func.gpkgCreateBaseTables())
    return engine


def test_get_missing_spatial_indexes(engine):
    assert get_missing_spatial_indexes(engine, [Model]) == [Model]


def test_create_spatial_index(engine):
    with engine.connect() as connection:
        with connection.begin():
            create_spatial_index(connection, Model.__table__.columns["geom"])
    assert get_missing_spatial_indexes(engine, [Model]) == []


def test_create_spatial_index_fail(engine):
    with engine.connect() as connection:
        with connection.begin():
            create_spatial_index(connection, Model.__table__.columns["geom"])
            with pytest.raises(RuntimeError):
                create_spatial_index(connection, Model.__table__.columns["geom"])


def test_ensure_spatial_index(engine):
    assert get_missing_spatial_indexes(engine, [Model]) == [Model]
    ensure_spatial_indexes(engine, [Model])
    assert get_missing_spatial_indexes(engine, [Model]) == []
