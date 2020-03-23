# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from .widgets.log_in import LogInDialog
from .widgets.simulation_overview import SimulationOverview
from .utils import set_icon
from .communication import UICommunication

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'threedi_api_qgis_client_dockwidget_base.ui'))


class ThreediQgisClientDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(ThreediQgisClientDockWidget, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.communication = UICommunication(self.iface, "3Di MI", self.lv_log)
        self.api_client = None
        self.threedi_models = None
        self.current_model = None
        self.organisation = None
        self.log_in_dlg = None
        self._simulate_overview_dlg = None
        self.simulate_overview_dlg = None
        self.widget_authorized.hide()
        self.btn_start.clicked.connect(self.log_in)
        self.btn_log_out.clicked.connect(self.log_out)
        self.btn_change_repo.clicked.connect(self.change_repository)
        self.btn_simulate.clicked.connect(self.show_simulate_overview)
        self.btn_clear_log.clicked.connect(self.clear_log)
        set_icon(self.btn_build, 'build.svg')
        set_icon(self.btn_check, 'check.svg')
        set_icon(self.btn_upload, 'upload.svg')
        set_icon(self.btn_simulate, 'api.svg')
        set_icon(self.btn_results, 'results.svg')

    def closeEvent(self, event):
        self.log_out()
        self.closingPlugin.emit()
        event.accept()

    def log_in(self):
        """Method for logging in 3Di API."""
        self.log_in_dlg = LogInDialog(self)
        self.log_in_dlg.exec_()
        self.api_client = self.log_in_dlg.api_client
        self.threedi_models = self.log_in_dlg.threedi_models
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
        """Logging out."""
        if self._simulate_overview_dlg is not None:
            self._simulate_overview_dlg.terminate_background_thread()
        if self.simulate_overview_dlg is not None:
            self.simulate_overview_dlg.stop_fetching_progress()
            self._simulate_overview_dlg = self.simulate_overview_dlg
            self.simulate_overview_dlg = None
        self.log_in_dlg = None
        self.api_client = None
        self.current_model = None
        self.widget_unauthorized.show()
        self.widget_authorized.hide()
        self.btn_simulate.setDisabled(True)

    def change_repository(self):
        """Changing current repository."""
        if self.log_in_dlg is None:
            self.log_in()
        else:
            self.log_in_dlg.show()
            self.current_model = self.log_in_dlg.current_model
            self.label_repo.setText(self.current_model.repository_slug)
            revision = self.log_in_dlg.revisions[self.current_model.revision_hash]
            self.label_rev.setText(f"{revision.number}")
            self.label_db.setText(self.current_model.model_ini)

    def show_simulate_overview(self):
        """Showing Simulation Overview with running simulations progresses."""
        if self.simulate_overview_dlg is None:
            self.simulate_overview_dlg = SimulationOverview(self)
            self.simulate_overview_dlg.label_user.setText(self.log_in_dlg.user)
            repo_slug = self.current_model.repository_slug
            repository = self.log_in_dlg.repositories[repo_slug]
            self.organisation = self.log_in_dlg.organisations[repository.organisation]
            self.simulate_overview_dlg.label_organisation.setText(self.organisation.name)
            self.simulate_overview_dlg.exec_()
        else:
            self.simulate_overview_dlg.show()

    def clear_log(self):
        """Clearing message log box."""
        self.lv_log.model().clear()
