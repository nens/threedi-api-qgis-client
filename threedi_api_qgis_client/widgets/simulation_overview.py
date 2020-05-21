# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem, QColor
from qgis.PyQt.QtWidgets import QMessageBox
from openapi_client import ApiException, Progress
from .wizard import SimulationWizard
from .custom_items import SimulationProgressDelegate, PROGRESS_ROLE
from ..api_calls.threedi_calls import ThreediCalls

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, 'ui', 'sim_overview.ui'))


class SimulationOverview(uicls, basecls):
    """Dialog with methods for handling running simulations."""
    PROGRESS_COLUMN_IDX = 2

    def __init__(self, parent_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.parent_dock = parent_dock
        self.api_client = self.parent_dock.api_client
        self.user = self.parent_dock.label_user.text()
        self.simulation_wizard = None
        self.simulations_keys = {}
        self.last_progresses = {}
        self.simulations_without_progress = set()
        self.tv_model = None
        self.setup_view_model()
        self.parent_dock.simulations_progresses_sentinel.progresses_fetched.connect(self.update_progress)
        self.parent_dock.simulations_progresses_ws_sentinel.progresses_fetched.connect(self.update_progress)
        self.pb_new_sim.clicked.connect(self.new_simulation)
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
            if status_name != "initialized":
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
                self.parent_dock.communication.bar_info(msg, log_text_color=QColor(Qt.darkGreen))


    def new_simulation(self):
        """Opening a wizard which allows defining and running new simulations."""
        self.simulation_wizard = SimulationWizard(self.parent_dock)
        self.simulation_wizard.exec_()
        new_simulation = self.simulation_wizard.new_simulation
        if new_simulation is not None:
            initial_status = self.simulation_wizard.new_simulation_status
            initial_progress = Progress(percentage=0, time=new_simulation.duration)
            self.add_simulation_to_model(new_simulation, initial_status, initial_progress)

    def stop_simulation(self):
        """Sending request to shutdown currently selected simulation."""
        index = self.tv_sim_tree.currentIndex()
        if not index.isValid():
            return
        title = "Warning"
        question = "This simulation is now running.\nAre you sure you want to stop it?"
        answer = self.parent_dock.communication.ask(self, title, question, QMessageBox.Warning)
        if answer is True:
            try:
                name_item = self.tv_model.item(index.row(), 0)
                sim_id = name_item.data(Qt.UserRole)
                tc = ThreediCalls(self.parent_dock.api_client)
                tc.make_action_on_simulation(sim_id, name='shutdown')
                msg = f"Simulation {name_item.text()} stopped!"
                self.parent_dock.communication.bar_info(msg)
            except ApiException as e:
                error_body = e.body
                error_details = error_body["details"] if "details" in error_body else error_body
                error_msg = f"Error: {error_details}"
                self.parent_dock.communication.show_error(error_msg)
            except Exception as e:
                error_msg = f"Error: {e}"
                self.parent_dock.communication.show_error(error_msg)
