# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import os
from datetime import datetime

from qgis.PyQt import uic
from qgis.PyQt.QtCore import QSettings, Qt, QThreadPool
from qgis.PyQt.QtGui import QColor, QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import QMessageBox
from threedi_api_client.openapi import ApiException

from threedi_models_and_simulations.widgets.simulation_init import SimulationInit
from threedi_models_and_simulations.workers import SimulationRunner

from ..api_calls.threedi_calls import ThreediCalls
from ..data_models.enumerators import SimulationStatusName
from ..utils import API_DATETIME_FORMAT, USER_DATETIME_FORMAT, extract_error_message
from ..utils_ui import set_icon
from .custom_items import PROGRESS_ROLE, SimulationProgressDelegate
from .model_selection import ModelSelectionDialog
from .simulation_wizard import SimulationWizard

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "simulation_overview.ui"))


class SimulationOverview(uicls, basecls):
    """Dialog with methods for handling running simulations."""

    PROGRESS_COLUMN_IDX = 2
    MAX_THREAD_COUNT = 1

    def __init__(self, plugin_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.plugin_dock = plugin_dock
        self.threedi_api = self.plugin_dock.threedi_api
        self.user = self.plugin_dock.current_user
        self.settings = QSettings()
        self.simulation_runner_pool = QThreadPool()
        self.simulation_runner_pool.setMaxThreadCount(self.MAX_THREAD_COUNT)
        self.model_selection_dlg = None
        self.simulation_init_wizard = None
        self.simulation_wizard = None
        self.running_simulations = {}
        self.last_progresses = {}
        self.simulations_without_progress = set()
        self.tv_model = None
        self.setup_view_model()
        self.plugin_dock.simulations_progresses_sentinel.progresses_fetched.connect(self.update_progress)
        self.pb_new_sim.clicked.connect(self.new_wizard_init)
        self.pb_stop_sim.clicked.connect(self.stop_simulation)
        self.pb_hide.clicked.connect(self.close)
        set_icon(self.refresh_btn, "refresh.svg")
        self.refresh_btn.clicked.connect(self.refresh_running_simulations_list)

    def setup_view_model(self):
        """Setting up model and columns for TreeView."""
        delegate = SimulationProgressDelegate(self.tv_sim_tree)
        self.tv_sim_tree.setItemDelegateForColumn(self.PROGRESS_COLUMN_IDX, delegate)
        self.tv_model = QStandardItemModel(0, 3)
        self.tv_model.setHorizontalHeaderLabels(["Simulation name", "User", "Progress"])
        self.tv_sim_tree.setModel(self.tv_model)

    def refresh_last_updated_label(self):
        """Refresh last update datetime label."""
        self.label_last_updated.setText(f"Last updated: {datetime.now().strftime(USER_DATETIME_FORMAT)}")

    def refresh_running_simulations_list(self):
        """Refresh running simulations list."""
        self.plugin_dock.simulations_progresses_sentinel.progresses_fetched.disconnect(self.update_progress)
        self.plugin_dock.simulations_progresses_sentinel.stop_listening(be_quite=True)
        self.tv_model.clear()
        self.running_simulations.clear()
        self.last_progresses.clear()
        self.simulations_without_progress.clear()
        self.setup_view_model()
        self.plugin_dock.simulations_progresses_sentinel.progresses_fetched.connect(self.update_progress)
        self.plugin_dock.simulations_progresses_sentinel.start_listening()

    def add_simulation_to_model(self, sim_id, sim_data):
        """Method for adding simulation to the model."""
        sim_name = sim_data["name"]
        sim_name_item = QStandardItem(f"{sim_name} ({sim_id})")
        sim_name_item.setData(sim_id, Qt.UserRole)
        user_name = sim_data["user_name"]
        user_item = QStandardItem(user_name)
        status_name = sim_data["status"]
        progress_percentage = sim_data["progress"]
        progress_item = QStandardItem()
        progress_item.setData((status_name, progress_percentage), PROGRESS_ROLE)
        self.tv_model.appendRow([sim_name_item, user_item, progress_item])
        self.running_simulations[sim_id] = sim_data
        for i in range(self.PROGRESS_COLUMN_IDX):
            self.tv_sim_tree.resizeColumnToContents(i)

    def update_progress(self, running_simulations_data):
        """Updating progress bars in the running simulations list."""
        for sim_id, sim_data in sorted(running_simulations_data.items()):
            status_name = sim_data["status"]
            if status_name not in {
                SimulationStatusName.INITIALIZED.value,
                SimulationStatusName.POSTPROCESSING.value,
                SimulationStatusName.QUEUED.value,
                SimulationStatusName.STARTING.value,
            }:
                continue
            if sim_id not in self.running_simulations:
                self.add_simulation_to_model(sim_id, sim_data)
        row_count = self.tv_model.rowCount()
        for row_idx in range(row_count):
            name_item = self.tv_model.item(row_idx, 0)
            sim_id = name_item.data(Qt.UserRole)
            if sim_id in self.simulations_without_progress or sim_id not in running_simulations_data:
                continue
            progress_item = self.tv_model.item(row_idx, self.PROGRESS_COLUMN_IDX)
            sim_data = running_simulations_data[sim_id]
            new_status_name = sim_data["status"]
            new_progress = sim_data["progress"]
            if new_status_name in {SimulationStatusName.CRASHED.value, SimulationStatusName.STOPPED.value}:
                old_status, old_progress = progress_item.data(PROGRESS_ROLE)
                progress_item.setData((new_status_name, old_progress), PROGRESS_ROLE)
                self.simulations_without_progress.add(sim_id)
            else:
                progress_item.setData((new_status_name, new_progress), PROGRESS_ROLE)
            if new_status_name == SimulationStatusName.FINISHED.value:
                self.simulations_without_progress.add(sim_id)
                sim_name = sim_data["name"]
                msg = f"Simulation {sim_name} finished!"
                self.plugin_dock.communication.bar_info(msg, log_text_color=QColor(Qt.darkGreen))
        self.refresh_last_updated_label()

    def new_wizard_init(self):
        """Open new simulation initiation options dialog."""
        self.model_selection_dlg = ModelSelectionDialog(self.plugin_dock, parent=self)
        if self.plugin_dock.current_local_schematisation is not None:
            self.model_selection_dlg.search_le.setText(self.plugin_dock.current_local_schematisation.name)
            self.model_selection_dlg.fetch_3di_models()
            self.model_selection_dlg.refresh_templates_list()
        self.model_selection_dlg.exec_()
        if self.model_selection_dlg.model_is_loaded:
            simulation_template = self.model_selection_dlg.current_simulation_template
            (
                simulation,
                settings_overview,
                events,
                lizard_post_processing_overview,
            ) = self.get_simulation_data_from_template(simulation_template)
            self.simulation_init_wizard = SimulationInit(
                self.model_selection_dlg.current_model,
                simulation_template,
                settings_overview,
                events,
                lizard_post_processing_overview,
                organisation=self.model_selection_dlg.organisation,
                api=ThreediCalls(self.threedi_api),
                parent=self,
            )
            self.simulation_init_wizard.exec_()
            if self.simulation_init_wizard.open_wizard:
                self.new_simulation_wizard(simulation, settings_overview, events, lizard_post_processing_overview)

    def get_simulation_data_from_template(self, template):
        """Fetching simulation, settings and events data from the simulation template."""
        simulation, settings_overview, events, lizard_post_processing_overview = None, None, None, None
        try:
            tc = ThreediCalls(self.threedi_api)
            simulation = template.simulation
            sim_id = simulation.id
            settings_overview = tc.fetch_simulation_settings_overview(str(sim_id))
            events = tc.fetch_simulation_events(sim_id)
            cloned_from_url = simulation.cloned_from
            if cloned_from_url:
                source_sim_id = cloned_from_url.strip("/").split("/")[-1]
                lizard_post_processing_overview = tc.fetch_simulation_lizard_postprocessing_overview(source_sim_id)
        except ApiException as e:
            error_msg = extract_error_message(e)
            if "No basic post-processing resource found" not in error_msg:
                self.plugin_dock.communication.bar_error(error_msg)
        except Exception as e:
            error_msg = f"Error: {e}"
            self.plugin_dock.communication.bar_error(error_msg)
        return simulation, settings_overview, events, lizard_post_processing_overview

    def new_simulation_wizard(self, simulation, settings_overview, events, lizard_post_processing_overview):
        """Opening a wizard which allows defining and running new simulations."""
        self.simulation_wizard = SimulationWizard(
            self.plugin_dock, self.model_selection_dlg, self.simulation_init_wizard
        )
        if simulation:
            self.simulation_wizard.load_template_parameters(
                simulation, settings_overview, events, lizard_post_processing_overview
            )
        self.close()
        self.simulation_wizard.exec_()

    def start_simulations(self, simulations_to_run):
        """Start the simulations."""
        upload_timeout = self.settings.value("threedi/timeout", 900, type=int)
        simulations_runner = SimulationRunner(self.threedi_api, simulations_to_run, upload_timeout=upload_timeout)
        simulations_runner.signals.initializing_simulations_progress.connect(self.on_initializing_progress)
        simulations_runner.signals.initializing_simulations_failed.connect(self.on_initializing_failed)
        simulations_runner.signals.initializing_simulations_finished.connect(self.on_initializing_finished)
        self.simulation_runner_pool.start(simulations_runner)

    def stop_simulation(self):
        """Sending request to shut down currently selected simulation."""
        index = self.tv_sim_tree.currentIndex()
        if not index.isValid():
            return
        title = "Warning"
        question = "This simulation is now running.\nAre you sure you want to stop it?"
        answer = self.plugin_dock.communication.ask(self, title, question, QMessageBox.Warning)
        if answer is True:
            try:
                name_item = self.tv_model.item(index.row(), 0)
                sim_id = name_item.data(Qt.UserRole)
                tc = ThreediCalls(self.plugin_dock.threedi_api)
                tc.create_simulation_action(sim_id, name="shutdown")
                msg = f"Simulation {name_item.text()} stopped!"
                self.plugin_dock.communication.bar_info(msg)
            except ApiException as e:
                error_msg = extract_error_message(e)
                self.plugin_dock.communication.show_error(error_msg)
            except Exception as e:
                error_msg = f"Error: {e}"
                self.plugin_dock.communication.show_error(error_msg)

    def on_initializing_progress(self, new_simulation, new_simulation_initialized, current_progress, total_progress):
        """Feedback on new simulation(s) initialization progress signal."""
        msg = f'Initializing simulation "{new_simulation.name}"...'
        self.plugin_dock.communication.progress_bar(msg, 0, total_progress, current_progress, clear_msg_bar=True)
        if new_simulation_initialized:
            sim = new_simulation.simulation
            initial_status = new_simulation.initial_status
            status_name = initial_status.name
            date_created = initial_status.created.strftime(API_DATETIME_FORMAT)
            sim_data = {
                "date_created": date_created,
                "name": sim.name,
                "progress": 0,
                "status": status_name,
                "user_name": sim.user,
                "simulation_user_first_name": self.plugin_dock.current_user_first_name,
                "simulation_user_last_name": self.plugin_dock.current_user_last_name,
            }
            self.add_simulation_to_model(sim.id, sim_data)
            info_msg = f"Simulation {new_simulation.name} added to queue!"
            self.plugin_dock.communication.bar_info(info_msg)

    def on_initializing_failed(self, error_message):
        """Feedback on new simulation(s) initialization failure signal."""
        self.plugin_dock.communication.clear_message_bar()
        self.plugin_dock.communication.bar_error(error_message, log_text_color=QColor(Qt.red))

    def on_initializing_finished(self, message):
        """Feedback on new simulation(s) initialization finished signal."""
        self.plugin_dock.communication.clear_message_bar()
        self.plugin_dock.communication.bar_info(message)
