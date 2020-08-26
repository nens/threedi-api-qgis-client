# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
from math import ceil
from time import sleep
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, QDateTime
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem
from qgis.core import QgsVectorLayer, QgsProject, QgsMapLayer
from openapi_client import ApiException
from ..utils import get_download_file, file_cached, CACHE_PATH
from ..ui_utils import set_named_style
from ..api_calls.threedi_calls import get_api_client, ThreediCalls

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_log, basecls_log = uic.loadUiType(os.path.join(base_dir, "ui", "sim_log_in.ui"))


class LogInDialog(uicls_log, basecls_log):
    """Dialog with widgets and methods used in logging process."""

    TABLE_LIMIT = 10

    def __init__(self, parent_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.parent_dock = parent_dock
        self.communication = self.parent_dock.communication
        self.user = None
        self.api_client = None
        self.repositories = None
        self.organisations = None
        self.organisation = None
        self.simulations = None
        self.revisions = None
        self.threedi_models = None
        self.current_model = None
        self.current_model_cells = None
        self.current_model_breaches = None
        self.cells_layer = None
        self.breaches_layer = None
        self.tv_model = QStandardItemModel()
        self.models_tv.setModel(self.tv_model)
        self.log_in_widget.hide()
        self.wait_widget.hide()
        self.action_widget.hide()
        self.load_widget.hide()
        self.organisation_widget.hide()
        self.pb_load_web.clicked.connect(self.show_log_widget)
        self.pb_log_in.clicked.connect(self.log_in_threedi)
        self.pb_prev_page.clicked.connect(self.move_backward)
        self.pb_next_page.clicked.connect(self.move_forward)
        self.page_sbox.valueChanged.connect(self.fetch_3di_models)
        self.pb_next.clicked.connect(self.show_load_widget)
        self.pb_load.clicked.connect(self.load_model)
        self.pb_organisation.clicked.connect(self.set_organisation)
        self.pb_cancel.clicked.connect(self.reject)
        self.pb_cancel_action.clicked.connect(self.reject)
        self.pb_cancel_load.clicked.connect(self.reject)
        self.search_le.returnPressed.connect(self.search_model)
        self.models_tv.selectionModel().selectionChanged.connect(self.toggle_load_model)
        self.resize(500, 250)

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

    def show_log_widget(self):
        """Showing logging form widget."""
        self.choose_widget.hide()
        self.log_in_widget.show()
        self.setWindowTitle("Log in")

    def show_wait_widget(self):
        """Showing widget with logging progress."""
        self.log_in_widget.hide()
        self.wait_widget.show()

    def show_action_widget(self):
        """Showing widget with actions choice."""
        self.wait_widget.hide()
        self.organisation_widget.hide()
        self.action_widget.show()
        self.setWindowTitle("Choose actions - web")
        self.toggle_load_model()

    def show_organisation_widget(self):
        """Showing widget with organisation choice"""
        self.wait_widget.hide()
        self.organisation_widget.show()
        self.setWindowTitle("Choose organisation")
        for org in self.organisations.values():
            self.organisations_box.addItem(org.name, org)

    def show_load_widget(self):
        """Showing widget with 3Di models available to load."""
        if self.sim_radio.isChecked():
            self.action_widget.hide()
            self.load_widget.show()
            self.setWindowTitle("Choose model - web")

    def fetch_organisations(self):
        """Fetching organisations list."""
        tc = ThreediCalls(self.api_client)
        organisations = tc.fetch_organisations()
        return organisations

    def fetch_repositories(self):
        """Fetching repositories list."""
        tc = ThreediCalls(self.api_client)
        repositories = tc.fetch_repositories()
        return repositories

    def fetch_simulations(self):
        """Fetching simulations list."""
        tc = ThreediCalls(self.api_client)
        running_simulations = tc.fetch_simulations()
        return running_simulations

    def fetch_revisions(self):
        """Fetching revisions list."""
        tc = ThreediCalls(self.api_client)
        revisions = tc.fetch_revisions()
        return revisions

    def fetch_3di_models(self):
        """Fetching 3Di models list."""
        tc = ThreediCalls(self.api_client)
        offset = (self.page_sbox.value() - 1) * self.TABLE_LIMIT
        text = self.search_le.text()
        threedi_models, models_count = tc.fetch_3di_models(limit=self.TABLE_LIMIT, offset=offset, name_contains=text)
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
            self.parent_dock.iface.setActiveLayer(self.cells_layer)
            self.parent_dock.iface.zoomToActiveLayer()

    def unload_cached_layers(self):
        """Removing model related vector layers from map canvas."""
        try:
            if self.breaches_layer is not None:
                QgsProject.instance().removeMapLayer(self.breaches_layer)
                self.breaches_layer = None
            if self.cells_layer is not None:
                QgsProject.instance().removeMapLayer(self.cells_layer)
                self.cells_layer = None
            self.parent_dock.iface.mapCanvas().refresh()
        except AttributeError:
            pass

    def load_model(self):
        """Loading selected model."""
        index = self.models_tv.currentIndex()
        if index.isValid():
            self.unload_cached_layers()
            current_row = index.row()
            name_item = self.tv_model.item(current_row, 0)
            self.current_model = name_item.data(Qt.UserRole)
            self.current_model_cells = self.get_cached_data("cells")
            self.current_model_breaches = self.get_cached_data("breaches")
            self.load_cached_layers()
        self.close()

    def get_cached_data(self, geojson_name):
        """Get model data that should be cached."""
        cached_file_path = None
        try:
            tc = ThreediCalls(self.api_client)
            model_id = self.current_model.id
            if geojson_name == "breaches":
                download = tc.fetch_geojson_breaches_download(model_id)
            elif geojson_name == "cells":
                download = tc.fetch_geojson_cells_download(model_id)
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
            error_msg = f"Error: {e}"
            self.communication.bar_error(error_msg)
        return cached_file_path

    def log_in_threedi(self):
        """Method which runs all logging widgets methods and setting up needed variables."""
        try:
            self.show_wait_widget()
            self.fetch_msg.hide()
            self.done_msg.hide()
            username = self.le_user.text()
            password = self.le_pass.text()
            self.le_user.setText("")
            self.le_pass.setText("")
            self.log_pbar.setValue(20)
            self.api_client = get_api_client(username, password)
            self.user = username
            self.fetch_msg.show()
            self.wait_widget.update()
            self.log_pbar.setValue(20)
            self.organisations = {org.unique_id: org for org in self.fetch_organisations()}
            self.log_pbar.setValue(40)
            self.repositories = {rep.slug: rep for rep in self.fetch_repositories()}
            self.log_pbar.setValue(50)
            self.simulations = self.fetch_simulations()
            self.log_pbar.setValue(60)
            self.revisions = {rev.hash: rev for rev in self.fetch_revisions()}
            self.log_pbar.setValue(80)
            self.fetch_3di_models()
            self.done_msg.show()
            self.wait_widget.update()
            self.log_pbar.setValue(100)
            sleep(1.5)
            if len(self.organisations) > 1:
                self.show_organisation_widget()
            else:
                self.organisation = next(iter(self.organisations.values()))
                self.show_action_widget()
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

    def set_organisation(self):
        """Set picked organisation."""
        self.organisation = self.organisations_box.currentData()
        self.show_action_widget()
