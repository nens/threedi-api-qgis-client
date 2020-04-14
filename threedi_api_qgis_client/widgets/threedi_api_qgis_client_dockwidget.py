# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
from time import sleep
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import QThread, QObject, pyqtSignal, pyqtSlot
from openapi_client import ApiException
from ..api_calls.threedi_calls import ThreediCalls
from .log_in import LogInDialog
from .simulation_overview import SimulationOverview
from ..ui_utils import set_icon
from ..communication import UICommunication

base_dir = os.path.dirname(os.path.dirname(__file__))
FORM_CLASS, _ = uic.loadUiType(os.path.join(base_dir, 'ui', 'threedi_api_qgis_client_dockwidget_base.ui'))


class ThreediQgisClientDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(ThreediQgisClientDockWidget, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.communication = UICommunication(self.iface, "3Di MI", self.lv_log)
        self.thread = QThread()
        self.progress_sentinel = None
        self.api_client = None
        self.threedi_models = None
        self.current_model = None
        self.organisation = None
        self.log_in_dlg = None
        self.simulate_overview_dlg = None
        self.widget_authorized.hide()
        self.btn_start.clicked.connect(self.log_in)
        self.btn_log_out.clicked.connect(self.log_out)
        self.btn_change_repo.clicked.connect(self.change_repository)
        self.btn_simulate.clicked.connect(self.show_simulation_overview)
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
        self.initialize_background_thread()
        self.initialize_simulation_overview()

    def log_out(self):
        """Logging out."""
        if self.thread is not None:
            self.stop_fetching_progress()
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

    def clear_log(self):
        """Clearing message log box."""
        self.lv_log.model().clear()

    def initialize_simulation_overview(self):
        """Initialization of the Simulation Overview window."""
        self.simulate_overview_dlg = SimulationOverview(self)
        self.simulate_overview_dlg.label_user.setText(self.log_in_dlg.user)
        repo_slug = self.current_model.repository_slug
        repository = self.log_in_dlg.repositories[repo_slug]
        self.organisation = self.log_in_dlg.organisations[repository.organisation]
        self.simulate_overview_dlg.label_organisation.setText(self.organisation.name)

    def show_simulation_overview(self):
        """Showing Simulation Overview with running simulations progresses."""
        if self.simulate_overview_dlg is None:
            self.initialize_simulation_overview()
        self.simulate_overview_dlg.show()

    def initialize_background_thread(self):
        """Initializing of the background thread."""
        if self.thread is not None:
            self.terminate_background_thread()
        self.thread = QThread()
        self.progress_sentinel = ProgressSentinel(self.api_client)
        self.progress_sentinel.moveToThread(self.thread)
        self.progress_sentinel.thread_finished.connect(self.on_finished)
        self.thread.started.connect(self.progress_sentinel.run)
        self.thread.start()

    def stop_fetching_progress(self):
        """Changing 'thread_active' flag inside background task that is fetching simulations progresses."""
        self.progress_sentinel.stop()

    def on_finished(self, msg):
        """Method for cleaning up background thread after it sends 'thread_finished'."""
        self.communication.bar_info(msg)
        self.thread.quit()
        self.thread.wait()

    def terminate_background_thread(self):
        """Forcing termination of background thread if it's still running."""
        if self.thread.isRunning():
            self.communication.bar_info('Terminating thread.')
            self.thread.terminate()
            self.communication.bar_info('Waiting for thread termination.')
            self.thread.wait()
            self.communication.bar_info('Worker terminated.')


class ProgressSentinel(QObject):
    """Worker object that will be moved to a separate thread and will check progresses of the running simulations."""
    thread_finished = pyqtSignal(str)
    progresses_fetched = pyqtSignal(dict)
    DELAY = 5
    SIMULATIONS_REFRESH_TIME = 300

    def __init__(self, api_client):
        super(QObject, self).__init__()
        self.api_client = api_client
        self.simulations_list = []
        self.refresh_at_step = int(self.SIMULATIONS_REFRESH_TIME / self.DELAY)
        self.progresses = None
        self.thread_active = True

    @pyqtSlot()
    def run(self):
        """Checking running simulations progresses."""
        stop_message = "Checking running simulation stopped."
        try:
            tc = ThreediCalls(self.api_client)
            counter = 0
            while self.thread_active:
                if counter == self.refresh_at_step:
                    del self.simulations_list[:]
                    counter -= self.refresh_at_step
                self.progresses = tc.all_simulations_progress(self.simulations_list)
                self.progresses_fetched.emit(self.progresses)
                sleep(self.DELAY)
                counter += 1
        except ApiException as e:
            error_body = e.body
            error_details = error_body["details"] if "details" in error_body else error_body
            error_msg = f"Error: {error_details}"
            stop_message = error_msg
        self.thread_finished.emit(stop_message)

    def stop(self):
        """Changing 'thread_active' flag to False."""
        self.thread_active = False
