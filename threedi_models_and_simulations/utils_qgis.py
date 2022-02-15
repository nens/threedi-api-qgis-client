# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2022 by Lutra Consulting for 3Di Water Management
import os
import sqlite3
from qgis.core import QgsDataSourceUri, QgsVectorLayer
from qgis.utils import plugins


def sqlite_layer(sqlite_path, table_name, layer_name=None, geom_column="the_geom", schema=""):
    """Creating vector layer out of Spatialite source."""
    uri = QgsDataSourceUri()
    uri.setDatabase(sqlite_path)
    uri.setDataSource(schema, table_name, geom_column)
    layer_name = table_name if layer_name is None else layer_name
    vlayer = QgsVectorLayer(uri.uri(), layer_name, "spatialite")
    return vlayer


def execute_sqlite_queries(sqlite_filepath, sql_script):
    """Run SQL queries on sqlite database."""
    connection = sqlite3.connect(sqlite_filepath)
    c = connection.cursor()
    c.executescript(sql_script)
    connection.commit()
    connection.close()


def is_toolbox_spatialite_loaded(local_schematisation_sqlite):
    """Check if local schematisation sqlite is loaded in 3Di Toolbox."""
    if local_schematisation_sqlite is None:
        return None
    try:
        toolbox = plugins["ThreeDiToolbox"]
        toolbox_sqlite = toolbox.ts_datasources.model_spatialite_filepath
        if toolbox_sqlite and local_schematisation_sqlite:
            if os.path.normpath(toolbox_sqlite) == os.path.normpath(local_schematisation_sqlite):
                return True
            else:
                return False
        else:
            return None
    except KeyError:
        return None
