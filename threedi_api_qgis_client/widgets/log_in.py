# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
from time import sleep
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem
from ..api_calls.threedi_calls import get_api_client, ThreediCalls, ApiException

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_log, basecls_log = uic.loadUiType(os.path.join(base_dir, 'ui', 'sim_log_in.ui'))


class LogInDialog(uicls_log, basecls_log):
    def __init__(self, parent_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.parent_dock = parent_dock
        self.communication = self.parent_dock.communication
        self.host = "https://api.3di.live/v3.0"
        self.user = ""
        self.api_client = None
        self.repositories = None
        self.organisations = None
        self.simulations = None
        self.revisions = None
        self.threedi_models = None
        self.model = None
        self.current_model = None
        self.log_in_widget.hide()
        self.wait_widget.hide()
        self.action_widget.hide()
        self.load_widget.hide()
        self.pb_load_web.clicked.connect(self.show_log_widget)
        self.pb_log_in.clicked.connect(self.log_in_threedi)
        self.pb_next.clicked.connect(self.show_load_widget)
        #self.models_lv.currentIndexChanged.connect()
        self.pb_load.clicked.connect(self.load_model)
        self.pb_cancel.clicked.connect(self.reject)
        self.pb_cancel_action.clicked.connect(self.reject)
        self.pb_cancel_load.clicked.connect(self.reject)
        self.search_le.textChanged.connect(self.search_model)
        self.resize(500, 250)

    def show_log_widget(self):
        self.choose_widget.hide()
        self.log_in_widget.show()
        self.setWindowTitle("Log in")

    def show_wait_widget(self):
        self.log_in_widget.hide()
        self.wait_widget.show()

    def show_action_widget(self):
        self.wait_widget.hide()
        self.action_widget.show()
        self.setWindowTitle("Choose actions - web")
        self.model = QStandardItemModel()
        self.models_lv.setModel(self.model)
        for sim_model in self.threedi_models:
            item = QStandardItem(sim_model.name)
            item.setData(sim_model, role=Qt.UserRole)
            self.model.appendRow([item])

    def show_load_widget(self):
        if self.sim_radio.isChecked():
            self.action_widget.hide()
            self.load_widget.show()
            self.setWindowTitle("Choose model - web")

    def fetch_organisations(self):
        tc = ThreediCalls(self.api_client)
        organisations = tc.fetch_organisations()
        return organisations

    def fetch_repositories(self):
        tc = ThreediCalls(self.api_client)
        repositories = tc.fetch_repositories()
        return repositories

    def fetch_simulations(self):
        tc = ThreediCalls(self.api_client)
        running_simulations = tc.fetch_simulations()
        return running_simulations

    def fetch_revisions(self):
        tc = ThreediCalls(self.api_client)
        revisions = tc.fetch_revisions()
        return revisions

    def fetch_3di_models(self):
        threedi_models = []
        tc = ThreediCalls(self.api_client)
        for revision in self.revisions.values():
            threedi_models += tc.fetch_revision_3di_models(revision.id)
        return threedi_models

    def search_model(self, search_string=None):
        row_count = self.model.rowCount()
        if not search_string:
            for i in range(row_count):
                row = self.model.item(i).index().row()
                self.models_lv.setRowHidden(row, False)
        else:
            items = self.model.findItems(search_string, Qt.MatchContains)
            rows = {i.index().row() for i in items}
            for i in range(row_count):
                row = self.model.item(i).index().row()
                if row not in rows:
                    self.models_lv.setRowHidden(row, True)
                else:
                    self.models_lv.setRowHidden(row, False)

    def load_model(self):
        index = self.models_lv.currentIndex()
        if index.isValid():
            self.current_model = self.model.data(index, Qt.UserRole)
        self.close()

    def log_in_threedi(self):
        try:
            self.show_wait_widget()
            self.fetch_msg.hide()
            self.done_msg.hide()
            username = self.le_user.text()
            password = self.le_pass.text()
            self.log_pbar.setValue(20)
            self.api_client = get_api_client(self.host, username, password)
            self.user = username
            self.fetch_msg.show()
            self.wait_widget.update()
            self.log_pbar.setValue(40)
            self.repositories = {rep.slug: rep for rep in self.fetch_repositories()}
            self.organisations = {org.unique_id: org for org in self.fetch_organisations()}
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
            self.show_action_widget()
        except ApiException as e:
            self.close()
            self.communication.show_error(e.reason)
        except ValueError as e:
            self.close()
            self.communication.show_error(str(e))
