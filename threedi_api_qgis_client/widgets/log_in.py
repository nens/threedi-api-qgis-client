# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
from time import sleep
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem
from openapi_client import ApiException

from threedi_api_qgis_client.api_calls.ws_qt import ClientWS
from ..api_calls.threedi_calls import get_api_client, ThreediCalls, all_simulations_progress_web_socket

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_log, basecls_log = uic.loadUiType(os.path.join(base_dir, 'ui', 'sim_log_in.ui'))


class LogInDialog(uicls_log, basecls_log):
    """Dialog with widgets and methods used in logging process."""
    API_HOST = "https://api.3di.live/v3.0"

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
        self.lv_model = QStandardItemModel()
        self.models_lv.setModel(self.lv_model)
        self.log_in_widget.hide()
        self.wait_widget.hide()
        self.action_widget.hide()
        self.load_widget.hide()
        self.organisation_widget.hide()
        self.pb_load_web.clicked.connect(self.show_log_widget)
        self.pb_log_in.clicked.connect(self.log_in_threedi)
        self.pb_next.clicked.connect(self.show_load_widget)
        self.pb_load.clicked.connect(self.load_model)
        self.pb_organisation.clicked.connect(self.set_organisation)
        self.pb_cancel.clicked.connect(self.reject)
        self.pb_cancel_action.clicked.connect(self.reject)
        self.pb_cancel_load.clicked.connect(self.reject)
        self.search_le.textChanged.connect(self.search_model)
        self.models_lv.selectionModel().selectionChanged.connect(self.toggle_load_model)
        self.resize(500, 250)

    def toggle_load_model(self):
        """Toggle load button if any model is selected."""
        selection_model = self.models_lv.selectionModel()
        if selection_model.hasSelection():
            self.pb_load.setEnabled(True)
        else:
            self.pb_load.setDisabled(True)

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
        for sim_model in self.threedi_models:
            item = QStandardItem(sim_model.name)
            item.setData(sim_model, role=Qt.UserRole)
            self.lv_model.appendRow([item])
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
        threedi_models = []
        tc = ThreediCalls(self.api_client)
        for revision in self.revisions.values():
            threedi_models += tc.fetch_revision_3di_models(revision.id)
        return threedi_models

    def search_model(self, search_string=None):
        """Method used for searching models with text typed withing search bar."""
        row_count = self.lv_model.rowCount()
        if not search_string:
            for i in range(row_count):
                row = self.lv_model.item(i).index().row()
                self.models_lv.setRowHidden(row, False)
        else:
            items = self.lv_model.findItems(search_string, Qt.MatchContains)
            rows = {i.index().row() for i in items}
            for i in range(row_count):
                row = self.lv_model.item(i).index().row()
                if row not in rows:
                    self.models_lv.setRowHidden(row, True)
                else:
                    self.models_lv.setRowHidden(row, False)

    def load_model(self):
        """Loading selected model."""
        index = self.models_lv.currentIndex()
        if index.isValid():
            self.current_model = self.lv_model.data(index, Qt.UserRole)
        self.close()

    def log_in_threedi(self):
        """Method which runs all logging widgets methods and setting up needed variables."""
        try:
            self.show_wait_widget()
            self.fetch_msg.hide()
            self.done_msg.hide()
            self.le_user.setText('')
            self.le_pass.setText('')
            username = self.le_user.text()
            password = self.le_pass.text()
            self.le_user.setText('')
            self.le_pass.setText('')
            self.log_pbar.setValue(20)
            self.api_client = get_api_client(self.API_HOST, username, password)
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
            self.threedi_models = self.fetch_3di_models()
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
