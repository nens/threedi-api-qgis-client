# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2022 by Lutra Consulting for 3Di Water Management
import os
import webbrowser
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal
from threedi_models_and_simulations.widgets.upload_overview import UploadOverview
from .log_in import LogInDialog, api_client_required
from .build_options import BuildOptions
from .simulation_overview import SimulationOverview
from .simulation_results import SimulationResults
from ..utils_ui import set_icon
from ..communication import UICommunication
from ..workers import AuthorizationHandler, WSProgressesSentinel

base_dir = os.path.dirname(os.path.dirname(__file__))
FORM_CLASS, _ = uic.loadUiType(os.path.join(base_dir, "ui", "threedi_dockwidget.ui"))


class ThreediDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, iface, plugin_settings, parent=None):
        """Constructor."""
        super().__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.plugin_settings = plugin_settings
        self.communication = UICommunication(self.iface, "3Di Models and Simulations", self.lv_log)
        self.simulations_progresses_thread = None
        self.simulations_progresses_sentinel = None
        self.threedi_api = None
        self.current_user = None
        self.current_user_full_name = None
        self.organisations = {}
        self.current_local_schematisation = None
        self.build_options = BuildOptions(self)
        self.simulation_overview_dlg = None
        self.simulation_results_dlg = None
        self.upload_dlg = None
        self.authorization_handler = AuthorizationHandler()
        self.pb_lmi.clicked.connect(self.authorization_handler.authorize)
        self.btn_log_in_out.clicked.connect(self.on_log_in_log_out)
        self.btn_load_schematisation.clicked.connect(self.build_options.load_local_schematisation)
        self.btn_load_revision.clicked.connect(self.build_options.load_local_schematisation)
        self.btn_new.clicked.connect(self.build_options.new_schematisation)
        self.btn_download.clicked.connect(self.build_options.download_schematisation)
        self.btn_upload.clicked.connect(self.show_upload_dialog)
        self.btn_simulate.clicked.connect(self.show_simulation_overview)
        self.btn_results.clicked.connect(self.show_simulation_results)
        self.btn_manage.clicked.connect(self.on_manage)
        self.plugin_settings.settings_changed.connect(self.on_log_out)
        set_icon(self.btn_new, "new.svg")
        set_icon(self.btn_download, "download.svg")
        set_icon(self.btn_upload, "upload.svg")
        set_icon(self.btn_simulate, "api.svg")
        set_icon(self.btn_results, "results.svg")
        set_icon(self.btn_manage, "manage.svg")
        set_icon(self.btn_log_in_out, "arrow.svg")
        set_icon(self.btn_load_schematisation, "arrow.svg")
        set_icon(self.btn_load_revision, "arrow.svg")

    def closeEvent(self, event):
        if self.threedi_api is not None:
            self.on_log_out()
        self.current_local_schematisation = None
        self.update_schematisation_view()
        self.closingPlugin.emit()
        event.accept()

    def on_log_in_log_out(self):
        """Trigger log-in or log-out action."""
        if self.threedi_api is None:
            self.on_log_in()
        else:
            self.on_log_out()

    def on_log_in(self):
        """Handle logging-in."""
        log_in_dialog = LogInDialog(self)
        accepted = log_in_dialog.exec_()
        if accepted:
            self.threedi_api = log_in_dialog.threedi_api
            self.current_user = log_in_dialog.user
            self.current_user_full_name = log_in_dialog.user_full_name
            self.organisations = log_in_dialog.organisations
            self.initialize_authorized_view()

    def on_log_out(self):
        """Handle logging-out."""
        if self.simulations_progresses_thread is not None:
            self.stop_fetching_simulations_progresses()
            self.simulation_overview_dlg.model_selection_dlg.unload_cached_layers()
            self.simulation_overview_dlg = None
        if self.simulation_results_dlg is not None:
            self.simulation_results_dlg.terminate_download_thread()
            self.simulation_results_dlg = None
        if self.upload_dlg:
            self.upload_dlg.hide()
            self.upload_dlg = None
        self.threedi_api = None
        self.current_user = None
        self.current_user_full_name = None
        self.organisations.clear()
        self.label_user.setText("-")
        set_icon(self.btn_log_in_out, "arrow.svg")
        self.btn_log_in_out.setToolTip("Log in")

    def update_schematisation_view(self):
        """Method for updating loaded schematisation labels."""
        if self.current_local_schematisation:
            schema_name = self.current_local_schematisation.name
            schema_dir = self.current_local_schematisation.main_dir
            schema_label_text = f'<a href="file:///{schema_dir}">{schema_name}</a>'
            schema_tooltip = f"{schema_name}\n{schema_dir}"
            self.label_schematisation.setText(schema_label_text)
            self.label_schematisation.setOpenExternalLinks(True)
            self.label_schematisation.setToolTip(schema_tooltip)
            if self.current_local_schematisation.wip_revision:
                self.label_revision.setText(str(self.current_local_schematisation.wip_revision.number) or "")
            else:
                self.label_revision.setText("")
        else:
            self.label_schematisation.setText("")
            self.label_schematisation.setToolTip("")
            self.label_revision.setText("")

    def initialize_authorized_view(self):
        """Method for initializing processes after logging in 3Di API."""
        set_icon(self.btn_log_in_out, "x.svg")
        self.btn_log_in_out.setToolTip("Log out")
        self.label_user.setText(self.current_user_full_name)
        self.initialize_simulations_progresses_thread()
        self.initialize_simulation_overview()
        self.initialize_simulation_results()

    def initialize_simulations_progresses_thread(self):
        """Initializing of the background thread."""
        if self.simulations_progresses_thread is not None:
            self.terminate_fetching_simulations_progresses_thread()
        self.simulations_progresses_thread = QThread()
        self.simulations_progresses_sentinel = WSProgressesSentinel(self.threedi_api, self.plugin_settings.wss_url)
        self.simulations_progresses_sentinel.moveToThread(self.simulations_progresses_thread)
        self.simulations_progresses_sentinel.thread_finished.connect(self.on_fetching_simulations_progresses_finished)
        self.simulations_progresses_sentinel.thread_failed.connect(self.on_fetching_simulations_progresses_failed)
        self.simulations_progresses_thread.started.connect(self.simulations_progresses_sentinel.run)
        self.simulations_progresses_thread.start()

    def stop_fetching_simulations_progresses(self):
        """Changing 'thread_active' flag inside background task that is fetching simulations progresses."""
        if self.simulations_progresses_sentinel is not None:
            self.simulations_progresses_sentinel.stop_listening()

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
            self.communication.bar_info("Terminating fetching simulations progresses thread.")
            self.simulations_progresses_thread.terminate()
            self.communication.bar_info("Waiting for fetching simulations progresses thread termination.")
            self.simulations_progresses_thread.wait()
            self.communication.bar_info("Fetching simulations progresses worker terminated.")
            self.simulations_progresses_thread = None
            self.simulations_progresses_sentinel = None

    def initialize_simulation_overview(self):
        """Initialization of the Simulation Overview window."""
        self.simulation_overview_dlg = SimulationOverview(self)
        self.simulation_overview_dlg.label_user.setText(self.current_user_full_name)

    @api_client_required
    def show_simulation_overview(self):
        """Showing Simulation Overview with running simulations progresses."""
        if self.simulation_overview_dlg is None:
            self.initialize_simulation_overview()
        self.simulation_overview_dlg.show()
        self.simulation_overview_dlg.raise_()
        self.simulation_overview_dlg.activateWindow()

    def initialize_simulation_results(self):
        """Initialization of the Simulations Results window."""
        self.simulation_results_dlg = SimulationResults(self)

    @api_client_required
    def show_simulation_results(self):
        """Showing finished simulations."""
        if self.simulation_results_dlg is None:
            self.initialize_simulation_results()
        self.simulation_results_dlg.show()
        self.simulation_results_dlg.raise_()
        self.simulation_results_dlg.activateWindow()

    def initialize_upload_status(self):
        """Initialization of the Upload Status dialog."""
        self.upload_dlg = UploadOverview(self)

    @api_client_required
    def show_upload_dialog(self):
        """Show upload status dialog."""
        if self.upload_dlg is None:
            self.initialize_upload_status()
        self.upload_dlg.show()
        self.upload_dlg.raise_()
        self.upload_dlg.activateWindow()

    @staticmethod
    def on_manage():
        """Open 3Di management webpage."""
        webbrowser.open("https://management.3di.live/")
