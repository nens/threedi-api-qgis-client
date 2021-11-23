# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import os

from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem, QColor
from qgis.PyQt.QtWidgets import QMessageBox
from threedi_api_client.openapi import ApiException, Progress

from threedi_api_qgis_client.widgets.simulation_init import SimulationInit
from .simulation_wizard import SimulationWizard
from .model_selection import ThreediModelSelection
from .custom_items import SimulationProgressDelegate, PROGRESS_ROLE
from ..api_calls.threedi_calls import ThreediCalls
from ..utils import load_saved_templates
from ..ui_utils import set_widgets_parameters

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "sim_overview.ui"))


class SimulationOverview(uicls, basecls):
    """Dialog with methods for handling running simulations."""

    PROGRESS_COLUMN_IDX = 2

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.plugin = plugin
        self.threedi_api = self.plugin.threedi_api
        self.user = self.plugin.label_user.text()
        self.model_selection_dlg = ThreediModelSelection(self.plugin, parent=self)
        self.simulation_init_wizard = None
        self.simulation_wizard = None
        self.simulations_keys = {}
        self.last_progresses = {}
        self.simulations_without_progress = set()
        self.tv_model = None
        self.setup_view_model()
        self.plugin.simulations_progresses_sentinel.progresses_fetched.connect(self.update_progress)
        self.pb_new_sim.clicked.connect(self.new_wizard_init)
        self.pb_load_template.clicked.connect(self.new_wizard_from_template)
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
                self.plugin.communication.bar_info(msg, log_text_color=QColor(Qt.darkGreen))

    def new_wizard_init(self):
        """Open new simulation initiation options dialog."""
        self.model_selection_dlg.exec_()
        if self.model_selection_dlg.model_is_loaded:
            self.simulation_init_wizard = SimulationInit(parent=self)
            self.simulation_init_wizard.exec_()
            if self.simulation_init_wizard.open_wizard:
                self.new_simulation()

    def new_wizard_from_template(self):
        """Start new simulation wizard from template."""
        template_items = load_saved_templates()
        items_keys = list(template_items.keys())
        if not items_keys:
            self.plugin.communication.show_warn("There are no any templates available!")
            return
        template = self.plugin.communication.pick_item("Load template", "Pick template to load", None, *items_keys)
        if template:
            simulation_template = template_items[template]
            self.simulation_init_wizard = SimulationInit(self)
            set_widgets_parameters(self.simulation_init_wizard, **simulation_template["options"])
            self.simulation_init_wizard.start_wizard()
            self.new_simulation(simulation_template)

    def new_simulation(self, simulation_template=None):
        """Opening a wizard which allows defining and running new simulations."""
        self.simulation_wizard = SimulationWizard(self.plugin, self.model_selection_dlg, self.simulation_init_wizard)
        if simulation_template:
            self.simulation_wizard.load_template_parameters(simulation_template)
        self.close()
        self.simulation_wizard.exec_()
        new_simulations = self.simulation_wizard.new_simulations
        if new_simulations is not None:
            for sim in new_simulations:
                initial_status = self.simulation_wizard.new_simulation_statuses.get(sim.id)
                initial_progress = Progress(percentage=0, time=sim.duration)
                self.add_simulation_to_model(sim, initial_status, initial_progress)

    def stop_simulation(self):
        """Sending request to shutdown currently selected simulation."""
        index = self.tv_sim_tree.currentIndex()
        if not index.isValid():
            return
        title = "Warning"
        question = "This simulation is now running.\nAre you sure you want to stop it?"
        answer = self.plugin.communication.ask(self, title, question, QMessageBox.Warning)
        if answer is True:
            try:
                name_item = self.tv_model.item(index.row(), 0)
                sim_id = name_item.data(Qt.UserRole)
                tc = ThreediCalls(self.plugin.threedi_api)
                tc.create_simulation_action(sim_id, name="shutdown")
                msg = f"Simulation {name_item.text()} stopped!"
                self.plugin.communication.bar_info(msg)
            except ApiException as e:
                error_body = e.body
                error_details = error_body["details"] if "details" in error_body else error_body
                error_msg = f"Error: {error_details}"
                self.plugin.communication.show_error(error_msg)
            except Exception as e:
                error_msg = f"Error: {e}"
                self.plugin.communication.show_error(error_msg)
