# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
from dateutil.relativedelta import relativedelta
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem, QPalette, QColor
from qgis.PyQt.QtWidgets import QApplication, QStyledItemDelegate, QStyleOptionProgressBar, QStyle
from ..api_calls.threedi_calls import ThreediCalls

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, 'ui', 'sim_results.ui'))

PROGRESS_ROLE = Qt.UserRole + 1000


class SimulationResults(uicls, basecls):
    """Dialog with methods for handling simulations results."""
    def __init__(self, parent_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.parent_dock = parent_dock
        self.api_client = self.parent_dock.api_client
        self.finished_simulations = {}
        self.tv_model = None
        self.setup_view_model()
        self.parent_dock.progress_sentinel.progresses_fetched.connect(self.update_finished_list)
        self.pb_cancel.clicked.connect(self.close)
        self.pb_download.clicked.connect(self.download_results)

    def setup_view_model(self):
        """Setting up model and columns for TreeView."""
        self.tv_model = QStandardItemModel(0, 3)
        self.tv_model.setHorizontalHeaderLabels(["Simulation name", "User", "Expires"])
        self.tv_finished_sim_tree.setModel(self.tv_model)

    def add_finished_simulation_to_model(self, simulation, status):
        """Method for adding simulation to the model."""
        sim_id = simulation.id
        sim_name_item = QStandardItem(f"{simulation.name} ({sim_id})")
        sim_name_item.setData(sim_id, Qt.UserRole)
        user_item = QStandardItem(simulation.user)
        delta = relativedelta(status.created, ThreediCalls.TIME_FRAME)
        expires_item = QStandardItem(f"{delta.days} day(s)")
        self.tv_model.appendRow([sim_name_item, user_item, expires_item])
        self.finished_simulations[sim_id] = simulation

    def update_finished_list(self, progresses):
        """Update finished simulations list."""
        for sim_id, (sim, status, progress) in progresses.items():
            status_name = status.name
            if status_name != "finished":
                continue
            if sim_id not in self.finished_simulations:
                self.add_finished_simulation_to_model(sim, status)

    def download_results(self):
        index = self.tv_finished_sim_tree.currentIndex()
        if not index.isValid():
            return
