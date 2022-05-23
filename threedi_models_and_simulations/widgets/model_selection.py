# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2022 by Lutra Consulting for 3Di Water Management
import logging
import os
from math import ceil
from operator import attrgetter
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, QDateTime, QItemSelectionModel
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem
from qgis.core import QgsVectorLayer, QgsProject, QgsMapLayer
from threedi_api_client.openapi import ApiException
from ..utils import extract_error_message, get_download_file, file_cached, CACHE_PATH
from ..utils_ui import set_named_style
from ..api_calls.threedi_calls import ThreediCalls

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "model_selection.ui"))


logger = logging.getLogger(__name__)


class ModelSelectionDialog(uicls, basecls):
    """Dialog for model selection."""

    TABLE_LIMIT = 10
    NAME_COLUMN_IDX = 1

    def __init__(self, plugin_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.plugin_dock = plugin_dock
        self.communication = self.plugin_dock.communication
        self.current_user = self.plugin_dock.current_user
        self.threedi_api = self.plugin_dock.threedi_api
        self.organisations = self.plugin_dock.organisations
        self.threedi_models = None
        self.simulation_templates = None
        self.current_model = None
        self.current_model_cells = None
        self.current_model_breaches = None
        self.current_simulation_template = None
        self.cells_layer = None
        self.breaches_layer = None
        self.organisation = None
        self.model_is_loaded = False
        self.models_model = QStandardItemModel()
        self.models_tv.setModel(self.models_model)
        self.templates_model = QStandardItemModel()
        self.templates_tv.setModel(self.templates_model)
        self.pb_prev_page.clicked.connect(self.move_models_backward)
        self.pb_next_page.clicked.connect(self.move_models_forward)
        self.page_sbox.valueChanged.connect(self.fetch_3di_models)
        self.pb_load.clicked.connect(self.load_model)
        self.pb_cancel_load.clicked.connect(self.cancel_load_model)
        self.search_le.returnPressed.connect(self.search_model)
        self.models_tv.selectionModel().selectionChanged.connect(self.refresh_templates_list)
        self.templates_tv.selectionModel().selectionChanged.connect(self.toggle_load_model)
        self.populate_organisations()
        self.fetch_3di_models()

    def refresh_templates_list(self):
        """Refresh simulation templates list if any model is selected."""
        selection_model = self.models_tv.selectionModel()
        self.templates_model.clear()
        self.templates_page_sbox.setMaximum(1)
        self.templates_page_sbox.setSuffix(" / 1")
        if selection_model.hasSelection():
            self.fetch_simulation_templates()
            if self.templates_model.rowCount() > 0:
                row_idx = self.templates_model.index(0, 0)
                self.templates_tv.selectionModel().setCurrentIndex(row_idx, QItemSelectionModel.ClearAndSelect)
        self.toggle_load_model()

    def toggle_load_model(self):
        """Toggle load button if any model is selected."""
        selection_model = self.templates_tv.selectionModel()
        if selection_model.hasSelection():
            self.pb_load.setEnabled(True)
        else:
            self.pb_load.setDisabled(True)

    def move_models_backward(self):
        """Moving to the models previous results page."""
        self.page_sbox.setValue(self.page_sbox.value() - 1)

    def move_models_forward(self):
        """Moving to the models next results page."""
        self.page_sbox.setValue(self.page_sbox.value() + 1)

    def move_templates_backward(self):
        """Moving to the templates previous results page."""
        self.templates_page_sbox.setValue(self.page_sbox.value() - 1)

    def move_templates_forward(self):
        """Moving to the templates next results page."""
        self.templates_page_sbox.setValue(self.page_sbox.value() + 1)

    def populate_organisations(self):
        """Populating organisations list inside combo box."""
        for org in self.organisations.values():
            self.organisations_box.addItem(org.name, org)

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
            self.models_model.clear()
            header = ["ID", "Model", "Schematisation", "Revision", "Last updated", "Updated by"]
            self.models_model.setHorizontalHeaderLabels(header)
            for sim_model in sorted(threedi_models, key=attrgetter("revision_commit_date"), reverse=True):
                id_item = QStandardItem(str(sim_model.id))
                name_item = QStandardItem(sim_model.name)
                name_item.setData(sim_model, role=Qt.UserRole)
                schema_item = QStandardItem(sim_model.schematisation_name)
                rev_item = QStandardItem(sim_model.revision_number)
                last_updated_day = sim_model.revision_commit_date.split("T")[0]
                lu_datetime = QDateTime.fromString(last_updated_day, "yyyy-MM-dd")
                lu_item = QStandardItem(lu_datetime.toString("dd-MMMM-yyyy"))
                ub_item = QStandardItem(sim_model.user)
                self.models_model.appendRow([id_item, name_item, schema_item, rev_item, lu_item, ub_item])
            self.threedi_models = threedi_models
        except ApiException as e:
            self.close()
            error_msg = extract_error_message(e)
            self.communication.show_error(error_msg)
        except Exception as e:
            self.close()
            error_msg = f"Error: {e}"
            self.communication.show_error(error_msg)

    def fetch_simulation_templates(self):
        """Fetching simulation templates list."""
        try:
            tc = ThreediCalls(self.threedi_api)
            offset = (self.templates_page_sbox.value() - 1) * self.TABLE_LIMIT
            selected_model = self.get_selected_model()
            model_pk = selected_model.id
            templates, templates_count = tc.fetch_simulation_templates_with_count(
                model_pk, limit=self.TABLE_LIMIT, offset=offset
            )
            pages_nr = ceil(templates_count / self.TABLE_LIMIT) or 1
            self.templates_page_sbox.setMaximum(pages_nr)
            self.templates_page_sbox.setSuffix(f" / {pages_nr}")
            self.templates_model.clear()
            header = ["Template ID", "Template name", "Creation date"]
            self.templates_model.setHorizontalHeaderLabels(header)
            for template in sorted(templates, key=attrgetter("id"), reverse=True):
                id_item = QStandardItem(str(template.id))
                name_item = QStandardItem(template.name)
                name_item.setData(template, role=Qt.UserRole)
                creation_date = template.created.strftime("%d-%m-%Y") if template.created else ""
                creation_date_item = QStandardItem(creation_date)
                self.templates_model.appendRow([id_item, name_item, creation_date_item])
            for i in range(len(header)):
                self.templates_tv.resizeColumnToContents(i)
            self.simulation_templates = templates
        except ApiException as e:
            error_msg = extract_error_message(e)
            self.communication.show_error(error_msg)
        except Exception as e:
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
            self.plugin_dock.iface.setActiveLayer(self.cells_layer)
            self.plugin_dock.iface.zoomToActiveLayer()

    def unload_cached_layers(self):
        """Removing model related vector layers from map canvas."""
        try:
            if self.breaches_layer is not None:
                QgsProject.instance().removeMapLayer(self.breaches_layer)
                self.breaches_layer = None
            if self.cells_layer is not None:
                QgsProject.instance().removeMapLayer(self.cells_layer)
                self.cells_layer = None
            self.plugin_dock.iface.mapCanvas().refresh()
        except AttributeError:
            pass

    def load_model(self):
        """Loading selected model."""
        index = self.models_tv.currentIndex()
        if index.isValid():
            self.organisation = self.organisations_box.currentData()
            self.unload_cached_layers()
            current_row = index.row()
            name_item = self.models_model.item(current_row, self.NAME_COLUMN_IDX)
            self.current_model = name_item.data(Qt.UserRole)
            self.current_model_cells = self.get_cached_data("cells")
            self.current_model_breaches = self.get_cached_data("breaches")
            self.current_simulation_template = self.get_selected_template()
            self.load_cached_layers()
            self.model_is_loaded = True
        self.close()

    def cancel_load_model(self):
        """Cancel loading model."""
        self.current_simulation_template = None
        self.model_is_loaded = False
        self.close()

    def get_selected_model(self):
        """Get currently selected model."""
        index = self.models_tv.currentIndex()
        if index.isValid():
            current_row = index.row()
            name_item = self.models_model.item(current_row, self.NAME_COLUMN_IDX)
            selected_model = name_item.data(Qt.UserRole)
        else:
            selected_model = None
        return selected_model

    def get_selected_template(self):
        """Get currently selected simulation template."""
        index = self.templates_tv.currentIndex()
        if index.isValid():
            current_row = index.row()
            name_item = self.templates_model.item(current_row, self.NAME_COLUMN_IDX)
            selected_template = name_item.data(Qt.UserRole)
        else:
            selected_template = None
        return selected_template

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
            error_msg = extract_error_message(e)
            if "geojson file not found" in error_msg:
                pass
            else:
                self.communication.bar_error(error_msg)
        except Exception as e:
            logger.exception("Error when getting to-be-cached data")
            error_msg = f"Error: {e}"
            self.communication.bar_error(error_msg)
        return cached_file_path
