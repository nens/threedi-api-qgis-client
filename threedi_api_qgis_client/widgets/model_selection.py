# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import logging
import os
from math import ceil
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, QDateTime
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem
from qgis.core import QgsVectorLayer, QgsProject, QgsMapLayer
from threedi_api_client.openapi import ApiException
from ..utils import get_download_file, file_cached, CACHE_PATH
from ..ui_utils import set_named_style
from ..api_calls.threedi_calls import ThreediCalls

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "model_selection.ui"))


logger = logging.getLogger(__name__)


class ThreediModelSelection(uicls, basecls):
    """Dialog with widgets and methods used in logging process."""

    TABLE_LIMIT = 10

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.plugin = plugin
        self.communication = self.plugin.communication
        self.current_user = self.plugin.current_user
        self.threedi_api = self.plugin.threedi_api
        self.threedi_models = None
        self.current_model = None
        self.current_model_cells = None
        self.current_model_breaches = None
        self.cells_layer = None
        self.breaches_layer = None
        self.organisations = None
        self.organisation = None
        self.model_is_loaded = False
        self.tv_model = QStandardItemModel()
        self.models_tv.setModel(self.tv_model)
        self.pb_prev_page.clicked.connect(self.move_backward)
        self.pb_next_page.clicked.connect(self.move_forward)
        self.page_sbox.valueChanged.connect(self.fetch_3di_models)
        self.pb_load.clicked.connect(self.load_model)
        self.pb_cancel_load.clicked.connect(self.cancel_load_model)
        self.search_le.returnPressed.connect(self.search_model)
        self.models_tv.selectionModel().selectionChanged.connect(self.toggle_load_model)
        self.fetch_organisations()
        self.fetch_3di_models()

    def toggle_load_model(self):
        """Toggle load button if any model is selected."""
        selection_model = self.models_tv.selectionModel()
        if selection_model.hasSelection():
            self.pb_load.setEnabled(True)
        else:
            self.pb_load.setDisabled(True)

    def move_backward(self):
        """Moving to the previous results page."""
        self.page_sbox.setValue(self.page_sbox.value() - 1)

    def move_forward(self):
        """Moving to the next results page."""
        self.page_sbox.setValue(self.page_sbox.value() + 1)

    def fetch_organisations(self):
        """Fetching organisations list and populating them inside combo box."""
        try:
            tc = ThreediCalls(self.threedi_api)
            self.organisations = {org.unique_id: org for org in tc.fetch_organisations()}
            for org in self.organisations.values():
                self.organisations_box.addItem(org.name, org)
        except ApiException as e:
            self.close()
            error_body = e.body
            error_details = error_body["details"] if "details" in error_body else error_body
            error_msg = f"Error: {error_details}"
            self.communication.show_error(error_msg)
        except Exception as e:
            self.close()
            error_msg = f"Error: {e}"
            self.communication.show_error(error_msg)

    def fetch_3di_models(self):
        """Fetching 3Di models list."""
        try:
            tc = ThreediCalls(self.threedi_api)
            offset = (self.page_sbox.value() - 1) * self.TABLE_LIMIT
            text = self.search_le.text()
            threedi_models, models_count = tc.fetch_3di_models_with_count(
                limit=self.TABLE_LIMIT, offset=offset, name_contains=text
            )
            pages_nr = ceil(models_count / self.TABLE_LIMIT) or 1
            self.page_sbox.setMaximum(pages_nr)
            self.page_sbox.setSuffix(f" / {pages_nr}")
            self.tv_model.clear()
            header = ["Model", "Repository", "Revision", "Last updated", "Updated by"]
            self.tv_model.setHorizontalHeaderLabels(header)
            for sim_model in threedi_models:
                name_item = QStandardItem(sim_model.name)
                name_item.setData(sim_model, role=Qt.UserRole)
                repo_item = QStandardItem(sim_model.repository_slug)
                rev_item = QStandardItem(sim_model.revision_number)
                last_updated_day = sim_model.revision_commit_date.split("T")[0]
                lu_datetime = QDateTime.fromString(last_updated_day, "yyyy-MM-dd")
                lu_item = QStandardItem(lu_datetime.toString("dd-MMMM-yyyy"))
                ub_item = QStandardItem(sim_model.user)
                self.tv_model.appendRow([name_item, repo_item, rev_item, lu_item, ub_item])
            for i in range(len(header)):
                self.models_tv.resizeColumnToContents(i)
            self.threedi_models = threedi_models
        except ApiException as e:
            self.close()
            error_body = e.body
            error_details = error_body["details"] if "details" in error_body else error_body
            error_msg = f"Error: {error_details}"
            self.communication.show_error(error_msg)
        except Exception as e:
            self.close()
            error_msg = f"Error: {e}"
            self.communication.show_error(error_msg)

    def search_model(self):
        """Method used for searching models with text typed withing search bar."""
        self.page_sbox.valueChanged.disconnect(self.fetch_3di_models)
        self.page_sbox.setValue(1)
        self.page_sbox.valueChanged.connect(self.fetch_3di_models)
        self.fetch_3di_models()

    def load_cached_layers(self):
        """Loading cached layers into the map canvas."""
        if self.current_model_cells is not None:
            self.cells_layer = QgsVectorLayer(self.current_model_cells, "cells", "ogr")
            set_named_style(self.cells_layer, "cells.qml")
            QgsProject.instance().addMapLayer(self.cells_layer, False)
            QgsProject.instance().layerTreeRoot().insertLayer(0, self.cells_layer)
            self.cells_layer.setFlags(QgsMapLayer.Searchable | QgsMapLayer.Identifiable)
        if self.current_model_breaches is not None:
            self.breaches_layer = QgsVectorLayer(self.current_model_breaches, "breaches", "ogr")
            set_named_style(self.breaches_layer, "breaches.qml")
            QgsProject.instance().addMapLayer(self.breaches_layer, False)
            QgsProject.instance().layerTreeRoot().insertLayer(0, self.breaches_layer)
            self.breaches_layer.setFlags(QgsMapLayer.Searchable | QgsMapLayer.Identifiable)
        if self.current_model_cells is not None:
            self.plugin.iface.setActiveLayer(self.cells_layer)
            self.plugin.iface.zoomToActiveLayer()

    def unload_cached_layers(self):
        """Removing model related vector layers from map canvas."""
        try:
            if self.breaches_layer is not None:
                QgsProject.instance().removeMapLayer(self.breaches_layer)
                self.breaches_layer = None
            if self.cells_layer is not None:
                QgsProject.instance().removeMapLayer(self.cells_layer)
                self.cells_layer = None
            self.plugin.iface.mapCanvas().refresh()
        except AttributeError:
            pass

    def load_model(self):
        """Loading selected model."""
        index = self.models_tv.currentIndex()
        if index.isValid():
            self.organisation = self.organisations_box.currentData()
            self.unload_cached_layers()
            current_row = index.row()
            name_item = self.tv_model.item(current_row, 0)
            self.current_model = name_item.data(Qt.UserRole)
            self.current_model_cells = self.get_cached_data("cells")
            self.current_model_breaches = self.get_cached_data("breaches")
            self.load_cached_layers()
        self.model_is_loaded = True
        self.close()

    def cancel_load_model(self):
        """Cancel loading model."""
        self.model_is_loaded = False
        self.close()

    def get_cached_data(self, geojson_name):
        """Get model data that should be cached."""
        cached_file_path = None
        try:
            tc = ThreediCalls(self.threedi_api)
            model_id = self.current_model.id
            if geojson_name == "breaches":
                download = tc.fetch_3di_model_geojson_breaches_download(model_id)
            elif geojson_name == "cells":
                download = tc.fetch_3di_model_geojson_cells_download(model_id)
            else:
                return cached_file_path
            filename = f"{geojson_name}_{model_id}_{download.etag}.json"
            file_path = os.path.join(CACHE_PATH, filename)
            if not file_cached(file_path):
                get_download_file(download, file_path)
            cached_file_path = file_path
            self.communication.bar_info(f"Model {geojson_name} cached.")
        except ApiException as e:
            error_body = e.body
            error_details = error_body["details"] if "details" in error_body else error_body
            error_msg = f"Error: {error_details}"
            if "geojson file not found" in error_msg:
                pass
            else:
                self.communication.bar_error(error_msg)
        except Exception as e:
            logger.exception("Error when getting to-be-cached data")
            error_msg = f"Error: {e}"
            self.communication.bar_error(error_msg)
        return cached_file_path
