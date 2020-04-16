# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
from dateutil.relativedelta import relativedelta
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, QSettings, QThread
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem
from qgis.PyQt.QtWidgets import QFileDialog
from openapi_client import ApiException
from .custom_items import DownloadProgressDelegate
from ..api_calls.threedi_calls import ThreediCalls
from ..workers import DownloadProgressWorker

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, 'ui', 'sim_results.ui'))


class SimulationResults(uicls, basecls):
    """Dialog with methods for handling simulations results."""
    PROGRESS_COLUMN_IDX = 3

    def __init__(self, parent_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.parent_dock = parent_dock
        self.api_client = self.parent_dock.api_client
        self.download_results_thread = None
        self.download_worker = None
        self.finished_simulations = {}
        self.tv_model = None
        self.setup_view_model()
        self.parent_dock.simulations_progresses_sentinel.progresses_fetched.connect(self.update_finished_list)
        self.pb_cancel.clicked.connect(self.close)
        self.pb_download.clicked.connect(self.download_results)
        self.tv_finished_sim_tree.selectionModel().selectionChanged.connect(self.toggle_download_results)
        self.resize(500, 500)

    def setup_view_model(self):
        """Setting up model and columns for TreeView."""
        self.tv_model = QStandardItemModel(0, 4)
        delegate = DownloadProgressDelegate(self.tv_finished_sim_tree)
        self.tv_finished_sim_tree.setItemDelegateForColumn(self.PROGRESS_COLUMN_IDX, delegate)
        self.tv_model.setHorizontalHeaderLabels(["Simulation name", "User", "Expires", "Download progress"])
        self.tv_finished_sim_tree.setModel(self.tv_model)

    def toggle_download_results(self):
        """Toggle download if any simulation is selected."""
        if self.download_results_thread is None:
            selection_model = self.tv_finished_sim_tree.selectionModel()
            if selection_model.hasSelection():
                self.pb_download.setEnabled(True)
            else:
                self.pb_download.setDisabled(True)

    def add_finished_simulation_to_model(self, simulation, status):
        """Method for adding simulation to the model."""
        sim_id = simulation.id
        sim_name_item = QStandardItem(f"{simulation.name} ({sim_id})")
        sim_name_item.setData(sim_id, Qt.UserRole)
        user_item = QStandardItem(simulation.user)
        delta = relativedelta(status.created, ThreediCalls.EXPIRATION_TIME)
        expires_item = QStandardItem(f"{delta.days} day(s)")
        progress_item = QStandardItem()
        progress_item.setData(-1,  Qt.UserRole)
        self.tv_model.appendRow([sim_name_item, user_item, expires_item, progress_item])
        self.finished_simulations[sim_id] = simulation

    def update_finished_list(self, progresses):
        """Update finished simulations list."""
        for sim_id, (sim, status, progress) in progresses.items():
            status_name = status.name
            if status_name != "finished":
                continue
            if sim_id not in self.finished_simulations:
                self.add_finished_simulation_to_model(sim, status)

    def on_download_progress_update(self, percentage):
        """Update download progress bar."""
        index = self.tv_finished_sim_tree.currentIndex()
        row_index = index.row()
        progress_item = self.tv_model.item(row_index, self.PROGRESS_COLUMN_IDX)
        progress_item.setData(percentage, Qt.UserRole)

    def on_download_finished(self, msg):
        """Reporting status and closing download thread."""
        self.parent_dock.communication.bar_info(msg, log_text_color=Qt.darkGreen)
        self.download_results_thread.quit()
        self.download_results_thread.wait()
        self.download_results_thread = None
        self.download_worker = None
        self.toggle_download_results()

    def download_results(self):
        """Download simulation results files."""
        index = self.tv_finished_sim_tree.currentIndex()
        if not index.isValid():
            return
        last_folder = QSettings().value("threedi/last_results_folder", os.path.expanduser("~"), type=str)
        directory = QFileDialog.getExistingDirectory(self, "Select Results Directory", last_folder)
        if len(directory) == 0:
            return
        QSettings().setValue("threedi/last_results_folder", directory)

        try:
            name_item = self.tv_model.item(index.row(), 0)
            sim_id = name_item.data(Qt.UserRole)
            tc = ThreediCalls(self.parent_dock.api_client)
            downloads = tc.fetch_simulation_downloads(sim_id)
        except ApiException as e:
            error_body = e.body
            error_details = error_body["details"] if "details" in error_body else error_body
            error_msg = f"Error: {error_details}"
            self.parent_dock.communication.show_error(error_msg)
            return

        self.pb_download.setDisabled(True)
        self.download_results_thread = QThread()
        self.download_worker = DownloadProgressWorker(sim_id, downloads, directory)
        self.download_worker.moveToThread(self.download_results_thread)
        self.download_worker.thread_finished.connect(self.on_download_finished)
        self.download_worker.download_progress.connect(self.on_download_progress_update)
        self.download_results_thread.started.connect(self.download_worker.run)
        self.download_results_thread.start()
