# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import sqlite3
from qgis.core import QgsDataSourceUri, QgsVectorLayer


def sqlite_layer(sqlite_path, table_name, layer_name=None, geom_column="the_geom", schema=""):
    """Creating vector layer out of Spatialite source."""
    uri = QgsDataSourceUri()
    uri.setDatabase(sqlite_path)
    uri.setDataSource(schema, table_name, geom_column)
    layer_name = table_name if layer_name is None else layer_name
    vlayer = QgsVectorLayer(uri.uri(), layer_name, "spatialite")
    return vlayer


def execute_sqlite_query(sqlite_filepath, sql_query):
    """Run SQL query on sqlite database."""
    connection = sqlite3.connect(sqlite_filepath)
    c = connection.cursor()
    c.executescript(sql_query)
    connection.commit()
    connection.close()
