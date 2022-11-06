# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2022 by Lutra Consulting for 3Di Water Management
import os
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, QSettings, QThreadPool
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem, QColor
from qgis.PyQt.QtWidgets import QMessageBox
from threedi_api_client.openapi import ApiException, Progress
from threedi_models_and_simulations.widgets.simulation_init import SimulationInit
from threedi_models_and_simulations.workers import SimulationsRunner
from .simulation_wizard import SimulationWizard
from .model_selection import ModelSelectionDialog
from .custom_items import SimulationProgressDelegate, PROGRESS_ROLE
from ..api_calls.threedi_calls import ThreediCalls
from ..utils import extract_error_message

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "sim_overview.ui"))


class SimulationOverview(uicls, basecls):
    """Dialog with methods for handling running simulations."""

    PROGRESS_COLUMN_IDX = 2

    def __init__(self, plugin_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.plugin_dock = plugin_dock
        self.threedi_api = self.plugin_dock.threedi_api
        self.user = self.plugin_dock.current_user
        self.model_selection_dlg = ModelSelectionDialog(self.plugin_dock, parent=self)
        self.settings = QSettings()
        self.simulation_runner_pool = QThreadPool()
        self.simulation_runner_pool.setMaxThreadCount(1)
        self.simulation_init_wizard = None
        self.simulation_wizard = None
        self.simulations_keys = {}
        self.last_progresses = {}
        self.simulations_without_progress = set()
        self.tv_model = None
        self.setup_view_model()
        self.plugin_dock.simulations_progresses_sentinel.progresses_fetched.connect(self.update_progress)
        self.pb_new_sim.clicked.connect(self.new_wizard_init)
        self.pb_stop_sim.clicked.connect(self.stop_simulation)

    def setup_view_model(self):
        """Setting up model and columns for TreeView."""
        delegate = SimulationProgressDelegate(self.tv_sim_tree)
        self.tv_sim_tree.setItemDelegateForColumn(self.PROGRESS_COLUMN_IDX, delegate)
        self.tv_model = QStandardItemModel(0, 3)
        self.tv_model.setHorizontalHeaderLabels(["Simulation name", "User", "Progress"])
        self.tv_sim_tree.setModel(self.tv_model)

    def add_simulation_to_model(self, simulation, status, progress):
        """Method for adding simulation to the model."""
        sim_id = simulation.id
        sim_name_item = QStandardItem(f"{simulation.name} ({sim_id})")
        sim_name_item.setData(sim_id, Qt.UserRole)
        user_item = QStandardItem(simulation.user)
        progress_item = QStandardItem()
        progress_item.setData((status, progress), PROGRESS_ROLE)
        self.tv_model.appendRow([sim_name_item, user_item, progress_item])
        self.simulations_keys[sim_id] = simulation
        for i in range(self.PROGRESS_COLUMN_IDX):
            self.tv_sim_tree.resizeColumnToContents(i)

    def update_progress(self, progresses):
        """Updating progress bars in the running simulations list."""
        for sim_id, (sim, status, progress) in progresses.items():
            status_name = status.name
            if status_name not in ["queued", "starting", "initialized", "postprocessing"]:
                continue
            if sim_id not in self.simulations_keys:
                self.add_simulation_to_model(sim, status, progress)
        row_count = self.tv_model.rowCount()
        for row_idx in range(row_count):
            name_item = self.tv_model.item(row_idx, 0)
            sim_id = name_item.data(Qt.UserRole)
            if sim_id in self.simulations_without_progress or sim_id not in progresses:
                continue
            progress_item = self.tv_model.item(row_idx, self.PROGRESS_COLUMN_IDX)
            sim, new_status, new_progress = progresses[sim_id]
            status_name = new_status.name
            if status_name == "stopped" or status_name == "crashed":
                old_status, old_progress = progress_item.data(PROGRESS_ROLE)
                progress_item.setData((new_status, old_progress), PROGRESS_ROLE)
                self.simulations_without_progress.add(sim_id)
            else:
                progress_item.setData((new_status, new_progress), PROGRESS_ROLE)
            if status_name == "finished":
                self.simulations_without_progress.add(sim_id)
                msg = f"Simulation {sim.name} finished!"
                self.plugin_dock.communication.bar_info(msg, log_text_color=QColor(Qt.darkGreen))

    def new_wizard_init(self):
        """Open new simulation initiation options dialog."""
        if self.plugin_dock.current_local_schematisation is not None:
            self.model_selection_dlg.search_le.setText(self.plugin_dock.current_local_schematisation.name)
            self.model_selection_dlg.fetch_3di_models()
            self.model_selection_dlg.refresh_templates_list()
        self.model_selection_dlg.exec_()
        if self.model_selection_dlg.model_is_loaded:
            simulation_template = self.model_selection_dlg.current_simulation_template
            simulation, settings_overview, events = self.get_simulation_data_from_template(simulation_template)
            self.simulation_init_wizard = SimulationInit(simulation_template, settings_overview, events, parent=self)
            self.simulation_init_wizard.exec_()
            if self.simulation_init_wizard.open_wizard:
                self.new_simulation(simulation, settings_overview, events)

    def get_simulation_data_from_template(self, template):
        """Fetching simulation, settings and events data from the simulation template."""
        simulation, settings_overview, events = None, None, None
        try:
            tc = ThreediCalls(self.threedi_api)
            simulation = template.simulation
            settings_overview = tc.fetch_simulation_settings_overview(str(simulation.id))
            events = tc.fetch_simulation_events(simulation.id)
        except ApiException as e:
            error_msg = extract_error_message(e)
            self.plugin_dock.communication.bar_error(error_msg)
        except Exception as e:
            error_msg = f"Error: {e}"
            self.plugin_dock.communication.bar_error(error_msg)
        return simulation, settings_overview, events

    def new_simulation(self, simulation, settings_overview, events):
        """Opening a wizard which allows defining and running new simulations."""
        self.simulation_wizard = SimulationWizard(
            self.plugin_dock, self.model_selection_dlg, self.simulation_init_wizard
        )
        if simulation:
            self.simulation_wizard.load_template_parameters(simulation, settings_overview, events)
        self.close()
        self.simulation_wizard.exec_()
        simulations_to_run = self.simulation_wizard.new_simulations
        if simulations_to_run:
            upload_timeout = self.settings.value("threedi/upload_timeout", 45, type=int)
            simulations_runner = SimulationsRunner(self.threedi_api, simulations_to_run, upload_timeout=upload_timeout)
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
            initial_progress = Progress(percentage=0, time=sim.duration)
            self.add_simulation_to_model(sim, initial_status, initial_progress)
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
