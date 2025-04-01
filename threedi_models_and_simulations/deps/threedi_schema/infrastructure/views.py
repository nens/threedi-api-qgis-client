from sqlalchemy import text
from sqlalchemy.exc import OperationalError

__all__ = ["recreate_views"]


def drop_view(connection, name):
    try:
        connection.execute(text(f"SELECT DropTable(NULL, '{name}')"))
    except OperationalError:
        connection.execute(text(f"SELECT DropGeoTable('{name}')"))
        connection.execute(text(f"DROP VIEW IF EXISTS '{name}'"))
    connection.execute(
        text(f"DELETE FROM views_geometry_columns WHERE view_name = '{name}'")
    )


def recreate_views(db, file_version, all_views, views_to_delete):
    """Recreate predefined views in a ThreediDatabase instance"""
    engine = db.engine
    with engine.connect() as connection:
        with connection.begin():
            for name, view in all_views.items():
                drop_view(connection, name)

                connection.execute(text(f"CREATE VIEW {name} AS {view['definition']}"))
                if file_version == 3:
                    connection.execute(
                        text(
                            f"INSERT INTO views_geometry_columns (view_name, view_geometry,view_rowid,f_table_name,f_geometry_column) VALUES('{name}', '{view['view_geometry']}', '{view['view_rowid']}', '{view['f_table_name']}', '{view['f_geometry_column']}')"
                        )
                    )
                else:
                    connection.execute(
                        text(
                            f"INSERT INTO views_geometry_columns (view_name, view_geometry,view_rowid,f_table_name,f_geometry_column,read_only) VALUES('{name}', '{view['view_geometry']}', '{view['view_rowid']}', '{view['f_table_name']}', '{view['f_geometry_column']}', 0)"
                        )
                    )
            for name in views_to_delete:
                drop_view(connection, name)
