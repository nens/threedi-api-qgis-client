from sqlalchemy import func, inspect, text

__all__ = ["ensure_spatial_indexes"]


def create_spatial_index(connection, column):
    """
    Create spatial index for given column.
    Note that this will fail if the spatial index already exists!
    """
    idx_name = f"{column.table.name}_{column.name}"
    try:
        connection.execute(func.gpkgAddSpatialIndex(column.table.name, column.name))
    except Exception as e:
        raise RuntimeError(f"Spatial index creation for {idx_name} failed with error {e}")
    return True


def get_missing_spatial_indexes(engine, models):
    """
    Collect all rtree tables that should exist
    There can only be one geometry column per table and we assume any geometry column is named geom
    """
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    return [
        model
        for model in models
        if "geom" in model.__table__.columns and f"rtree_{model.__table__.name}_geom" not in table_names
    ]


def ensure_spatial_indexes(engine, models):
    """Ensure presence of spatial indexes for all geometry columns"""
    created = False
    no_spatial_index_models = get_missing_spatial_indexes(engine, models)
    with engine.connect() as connection:
        with connection.begin():
            for model in no_spatial_index_models:
                created &= create_spatial_index(connection, model.__table__.columns["geom"])
            if created:
                connection.execute(text("VACUUM"))
