from geoalchemy2.types import Geometry
from sqlalchemy import func, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError

__all__ = ["copy_models"]


def get_spatialite_version(db):
    with db.session_scope() as session:
        ((lib_version,),) = session.execute(
            text("SELECT spatialite_version()")
        ).fetchall()

    # Identify Spatialite version
    inspector = inspect(db.engine)
    spatial_ref_sys_cols = [x["name"] for x in inspector.get_columns("spatial_ref_sys")]
    if len(spatial_ref_sys_cols) == 0:
        raise ValueError("Not a spatialite file")

    if "srs_wkt" in spatial_ref_sys_cols:
        file_version = 3
    else:
        file_version = 4

    return int(lib_version.split(".")[0]), file_version


def cast_if_geometry(column):
    """Cast Geometry columns to EWKT (so that we can save it right back later)"""
    if isinstance(column.type, Geometry):
        return func.AsEWKT(column).label(column.name)
    else:
        return column


def model_count(session, model) -> int:
    q = text(f"SELECT COUNT(*) FROM {model.__tablename__}")
    try:
        return session.execute(q).fetchall()[0][0]
    except OperationalError as e:
        if "no such table" in str(e):
            return 0
        raise e


def model_query(session, model):
    """Query fields explicitly, so that we end up with an iterator of row tuples"""
    return session.query(*[cast_if_geometry(c) for c in model.__table__.columns])


def model_from_tuple(model, tpl):
    return model(**{c.key: v for (c, v) in zip(model.__table__.columns, tpl)})


def copy_model(from_db, to_db, model):
    with from_db.session_scope() as input_session:
        if model_count(input_session, model) == 0:
            return
        objs = [model_from_tuple(model, x) for x in model_query(input_session, model)]
    with to_db.session_scope() as work_session:
        try:
            work_session.bulk_save_objects(objs)
        except IntegrityError:
            work_session.rollback()
            raise
        else:
            work_session.commit()


def copy_models(from_db, to_db, models):
    for model in models:
        copy_model(from_db, to_db, model)
