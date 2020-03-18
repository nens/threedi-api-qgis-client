# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
from time import sleep
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from .widgets.log_in import LogInDialog
from .widgets.simulation_overview import SimulationOverview
from .utils import set_icon

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'threedi_api_qgis_client_dockwidget_base.ui'))


class ThreediQgisClientDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(ThreediQgisClientDockWidget, self).__init__(parent)
        self.setupUi(self)
        self.api_client = None
        self.current_model = None
        self.log_in_dlg = None
        self.simulate_overview_dlg = None
        self.widget_authorized.hide()
        self.btn_start.clicked.connect(self.log_in)
        self.btn_log_out.clicked.connect(self.log_out)
        self.btn_simulate.clicked.connect(self.show_simulate_overview)
        set_icon(self.btn_build, 'build.svg')
        set_icon(self.btn_check, 'check.svg')
        set_icon(self.btn_upload, 'upload.svg')
        set_icon(self.btn_simulate, 'api.svg')
        set_icon(self.btn_results, 'results.svg')

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def log_in(self):
        self.log_in_dlg = LogInDialog()
        self.log_in_dlg.exec_()
        self.api_client = self.log_in_dlg.api_client
        self.current_model = self.log_in_dlg.current_model
        if self.current_model is None:
            return

        self.widget_unauthorized.hide()
        self.widget_authorized.show()
        self.btn_simulate.setEnabled(True)

        self.label_user.setText(self.log_in_dlg.user)
        self.label_repo.setText(self.current_model.repository_slug)
        revision = self.log_in_dlg.revisions[self.current_model.revision_hash]
        self.label_rev.setText(f"{revision.number}")
        self.label_db.setText(self.current_model.model_ini)

    def log_out(self):
        if self.simulate_overview_dlg is not None:
            self.simulate_overview_dlg.stop_fetching_progress()
            sleep(2.55)
            self.simulate_overview_dlg = None
        self.log_in_dlg = None
        self.api_client = None
        self.current_model = None
        self.widget_unauthorized.show()
        self.widget_authorized.hide()
        self.btn_simulate.setDisabled(True)

    def show_simulate_overview(self):
        if self.simulate_overview_dlg is None:
            self.simulate_overview_dlg = SimulationOverview(self.api_client)
            self.simulate_overview_dlg.label_user.setText(self.log_in_dlg.user)
            repo_slug = self.current_model.repository_slug
            repository = self.log_in_dlg.repositories[repo_slug]
            organisation = self.log_in_dlg.organisations[repository.organisation]
            self.simulate_overview_dlg.label_organisation.setText(organisation.name)
            self.simulate_overview_dlg.exec_()
        else:
            self.simulate_overview_dlg.show()
