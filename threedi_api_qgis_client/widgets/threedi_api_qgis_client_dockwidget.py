# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal

from threedi_api_qgis_client.widgets.upload import UploadDialog
from .log_in import LogInDialog
from .simulation_overview import SimulationOverview
from .simulation_results import SimulationResults
from ..ui_utils import set_icon
from ..communication import UICommunication
from ..workers import SimulationsProgressesSentinel

base_dir = os.path.dirname(os.path.dirname(__file__))
FORM_CLASS, _ = uic.loadUiType(os.path.join(base_dir, 'ui', 'threedi_api_qgis_client_dockwidget_base.ui'))


class ThreediQgisClientDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, iface, parent=None):
        """Constructor."""
        super().__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.communication = UICommunication(self.iface, "3Di MI", self.lv_log)
        self.simulations_progresses_thread = None
        self.simulations_progresses_sentinel = None
        self.api_client = None
        self.threedi_models = None
        self.current_model = None
        self.organisation = None
        self.log_in_dlg = None
        self.simulation_overview_dlg = None
        self.simulation_results_dlg = None
        self.upload_dlg = None
        self.widget_authorized.hide()
        self.btn_start.clicked.connect(self.log_in)
        self.btn_log_out.clicked.connect(self.log_out)
        self.btn_change_repo.clicked.connect(self.change_repository)
        self.btn_simulate.clicked.connect(self.show_simulation_overview)
        self.btn_results.clicked.connect(self.show_simulation_results)
        self.btn_clear_log.clicked.connect(self.clear_log)
        self.btn_upload.clicked.connect(self.show_upload_dialog)
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
        self.btn_results.setEnabled(True)
        self.btn_upload.setEnabled(True)
        self.label_user.setText(self.log_in_dlg.user)
        self.label_repo.setText(self.current_model.repository_slug)
        revision = self.log_in_dlg.revisions[self.current_model.revision_hash]
        self.label_rev.setText(f"{revision.number}")
        self.label_db.setText(self.current_model.model_ini)
        self.initialize_simulations_progresses_thread()
        self.initialize_simulation_overview()
        self.initialize_simulation_results()

    def log_out(self):
        """Logging out."""
        if self.simulations_progresses_thread is not None:
            self.stop_fetching_simulations_progresses()
            self.simulation_overview_dlg = None
        if self.simulation_results_dlg is not None:
            self.simulation_results_dlg.terminate_download_thread()
            self.simulation_results_dlg = None
        self.log_in_dlg = None
        self.api_client = None
        self.current_model = None
        self.widget_unauthorized.show()
        self.widget_authorized.hide()
        self.btn_simulate.setDisabled(True)
        self.btn_results.setDisabled(True)
        self.btn_upload.setDisabled(True)

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

    def clear_log(self):
        """Clearing message log box."""
        self.lv_log.model().clear()

    def initialize_simulations_progresses_thread(self):
        """Initializing of the background thread."""
        if self.simulations_progresses_thread is not None:
            self.terminate_fetching_simulations_progresses_thread()
        self.simulations_progresses_thread = QThread()
        self.simulations_progresses_sentinel = SimulationsProgressesSentinel(self.api_client)
        self.simulations_progresses_sentinel.moveToThread(self.simulations_progresses_thread)
        self.simulations_progresses_sentinel.thread_finished.connect(self.on_fetching_simulations_progresses_finished)
        self.simulations_progresses_sentinel.thread_failed.connect(self.on_fetching_simulations_progresses_failed)
        self.simulations_progresses_thread.started.connect(self.simulations_progresses_sentinel.run)
        self.simulations_progresses_thread.start()

    def stop_fetching_simulations_progresses(self):
        """Changing 'thread_active' flag inside background task that is fetching simulations progresses."""
        if self.simulations_progresses_sentinel is not None:
            self.simulations_progresses_sentinel.stop()

    def on_fetching_simulations_progresses_finished(self, msg):
        """Method for cleaning up background thread after it sends 'thread_finished'."""
        self.communication.bar_info(msg)
        self.simulations_progresses_thread.quit()
        self.simulations_progresses_thread.wait()
        self.simulations_progresses_thread = None
        self.simulations_progresses_sentinel = None

    def on_fetching_simulations_progresses_failed(self, msg):
        """Reporting fetching progresses failure."""
        self.communication.bar_error(msg, log_text_color=Qt.red)

    def terminate_fetching_simulations_progresses_thread(self):
        """Forcing termination of background thread if it's still running."""
        if self.simulations_progresses_thread is not None and self.simulations_progresses_thread.isRunning():
            self.communication.bar_info('Terminating fetching simulations progresses thread.')
            self.simulations_progresses_thread.terminate()
            self.communication.bar_info('Waiting for fetching simulations progresses thread termination.')
            self.simulations_progresses_thread.wait()
            self.communication.bar_info('Fetching simulations progresses worker terminated.')
            self.simulations_progresses_thread = None
            self.simulations_progresses_sentinel = None

    def initialize_simulation_overview(self):
        """Initialization of the Simulation Overview window."""
        self.simulation_overview_dlg = SimulationOverview(self)
        self.simulation_overview_dlg.label_user.setText(self.log_in_dlg.user)
        self.organisation = self.log_in_dlg.organisation
        self.simulation_overview_dlg.label_organisation.setText(self.organisation.name)

    def show_simulation_overview(self):
        """Showing Simulation Overview with running simulations progresses."""
        if self.simulation_overview_dlg is None:
            self.initialize_simulation_overview()
        self.simulation_overview_dlg.show()

    def initialize_simulation_results(self):
        """Initialization of the Simulations Results window."""
        self.simulation_results_dlg = SimulationResults(self)
        self.organisation = self.log_in_dlg.organisation
        self.simulation_results_dlg.label_organisation.setText(self.organisation.name)

    def show_simulation_results(self):
        """Showing finished simulations."""
        if self.simulation_results_dlg is None:
            self.initialize_simulation_results()
        self.simulation_results_dlg.show()

    def show_upload_dialog(self):
        self.upload_dlg = UploadDialog(self)
        self.upload_dlg.exec_()
