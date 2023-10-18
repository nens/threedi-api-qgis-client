# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import os
import shutil
from datetime import datetime

from dateutil.relativedelta import relativedelta
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QSettings, Qt, QThreadPool
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import QFileDialog
from threedi_api_client.openapi import ApiException
from threedi_mi_utils import LocalRevision, LocalSchematisation, bypass_max_path_limit, list_local_schematisations

from ..api_calls.threedi_calls import ThreediCalls
from ..utils import API_DATETIME_FORMAT, extract_error_message
from ..workers import DownloadProgressWorker
from .custom_items import DownloadProgressDelegate

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "simulation_results.ui"))


class SimulationResults(uicls, basecls):
    """Dialog with methods for handling simulations results."""

    PROGRESS_COLUMN_IDX = 2
    MAX_THREAD_COUNT = 1

    def __init__(self, plugin_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.plugin_dock = plugin_dock
        self.api_client = self.plugin_dock.threedi_api
        self.download_results_pool = QThreadPool()
        self.download_results_pool.setMaxThreadCount(self.MAX_THREAD_COUNT)
        self.finished_simulations = {}
        self.tv_model = None
        self.last_progress_item = None
        self.setup_view_model()
        self.plugin_dock.simulations_progresses_sentinel.simulation_finished.connect(self.update_finished_list)
        self.pb_cancel.clicked.connect(self.close)
        self.pb_download.clicked.connect(self.download_results)
        self.tv_finished_sim_tree.selectionModel().selectionChanged.connect(self.toggle_download_results)

    def setup_view_model(self):
        """Setting up model and columns for TreeView."""
        self.tv_model = QStandardItemModel(0, 3)
        delegate = DownloadProgressDelegate(self.tv_finished_sim_tree)
        self.tv_finished_sim_tree.setItemDelegateForColumn(self.PROGRESS_COLUMN_IDX, delegate)
        self.tv_model.setHorizontalHeaderLabels(["Simulation name", "Expires", "Download progress"])
        self.tv_finished_sim_tree.setModel(self.tv_model)

    def toggle_download_results(self):
        """Toggle download if any simulation is selected."""
        if self.download_results_pool.activeThreadCount() == 0:
            selection_model = self.tv_finished_sim_tree.selectionModel()
            if selection_model.hasSelection():
                self.pb_download.setEnabled(True)
            else:
                self.pb_download.setDisabled(True)

    def add_finished_simulation_to_model(self, sim_id, sim_data):
        """Method for adding information about finished simulation to the model."""
        sim_name = sim_data["name"]
        sim_name_item = QStandardItem(f"{sim_name} ({sim_id})")
        sim_name_item.setData(sim_id, Qt.UserRole)
        create_str = sim_data["date_created"]
        create_datetime = datetime.strptime(create_str, API_DATETIME_FORMAT)
        delta = relativedelta(create_datetime, ThreediCalls.EXPIRATION_TIME)
        expires_item = QStandardItem(f"{delta.days} day(s)")
        progress_item = QStandardItem()
        progress_item.setData(-1, Qt.UserRole)
        self.tv_model.insertRow(0, [sim_name_item, expires_item, progress_item])
        self.finished_simulations[sim_id] = sim_data

    def update_finished_list(self, finished_simulations_data):
        """Update finished simulations list."""
        for sim_id, sim_data in sorted(finished_simulations_data.items()):
            if sim_id not in self.finished_simulations:
                self.add_finished_simulation_to_model(sim_id, sim_data)

    def on_download_progress_update(self, percentage):
        """Update download progress bar."""
        self.last_progress_item.setData(percentage, Qt.UserRole)
        if percentage == 0:
            row = self.last_progress_item.index().row()
            name_text = self.tv_model.item(row, 0).text()
            msg = f"Downloading results of {name_text} started!"
            self.plugin_dock.communication.bar_info(msg)

    def on_download_finished_success(self, msg, results_dir):
        """Reporting finish successfully status and closing download thread."""
        self.plugin_dock.communication.bar_info(msg, log_text_color=Qt.darkGreen)
        grid_file_names = ["gridadmin.h5", "gridadmin.gpkg"]
        grid_dir = os.path.join(os.path.dirname(os.path.dirname(results_dir)), "grid")
        if os.path.exists(grid_dir):
            for grid_file_name in grid_file_names:
                grid_file = os.path.join(results_dir, grid_file_name)
                if os.path.exists(grid_file):
                    grid_file_copy = os.path.join(grid_dir, grid_file_name)
                    shutil.copyfile(grid_file, bypass_max_path_limit(grid_file_copy, is_file=True))
        self.toggle_download_results()

    def on_download_finished_failed(self, msg):
        """Reporting failure and closing download thread."""
        self.plugin_dock.communication.bar_error(msg, log_text_color=Qt.red)
        self.toggle_download_results()

    def pick_results_destination_dir(self):
        """Pick folder where results will be written to."""
        working_dir = self.plugin_dock.plugin_settings.working_dir
        last_folder = QSettings().value("threedi/last_results_folder", working_dir, type=str)
        directory = QFileDialog.getExistingDirectory(self, "Select Results Directory", last_folder)
        if len(directory) == 0:
            return None
        QSettings().setValue("threedi/last_results_folder", directory)
        return directory

    def download_results(self):
        """Download simulation results files."""
        current_index = self.tv_finished_sim_tree.currentIndex()
        if not current_index.isValid():
            return
        working_dir = self.plugin_dock.plugin_settings.working_dir
        local_schematisations = list_local_schematisations(working_dir)
        try:
            tc = ThreediCalls(self.plugin_dock.threedi_api)
            current_row = current_index.row()
            name_item = self.tv_model.item(current_row, 0)
            sim_id = name_item.data(Qt.UserRole)
            simulation = tc.fetch_simulation(sim_id)
            simulation_name = simulation.name.replace(" ", "_")
            simulation_model_id = int(simulation.threedimodel_id)
            results_dir, gridadmin_downloads, gridadmin_downloads_gpkg = None, None, None
            try:
                model_3di = tc.fetch_3di_model(simulation_model_id)
                gridadmin_downloads = tc.fetch_3di_model_gridadmin_download(simulation_model_id)
                if model_3di.schematisation_id:
                    model_schematisation_id = model_3di.schematisation_id
                    model_schematisation_name = model_3di.schematisation_name
                    model_revision_number = model_3di.revision_number
                    try:
                        local_schematisation = local_schematisations[model_schematisation_id]
                    except KeyError:
                        local_schematisation = LocalSchematisation(
                            working_dir, model_schematisation_id, model_schematisation_name, create=True
                        )
                    try:
                        local_revision = local_schematisation.revisions[model_revision_number]
                    except KeyError:
                        local_revision = LocalRevision(local_schematisation, model_revision_number)
                        local_revision.make_revision_structure()
                    results_dir = local_revision.results_dir
                else:
                    warn_msg = (
                        "The 3Di model to which these results belong was uploaded with Tortoise and does not "
                        "belong to any schematisation. Therefore, it cannot be determined to which "
                        "schematisation the results should be downloaded.\n\nPlease select a directory to save "
                        "the result files to."
                    )
                    self.plugin_dock.communication.show_warn(warn_msg)
                    results_dir = self.pick_results_destination_dir()
                    if not results_dir:
                        self.plugin_dock.communication.show_warn(warn_msg)
                        return
                gridadmin_downloads_gpkg = tc.fetch_3di_model_geopackage_download(simulation_model_id)
            except ApiException as e:
                error_msg = extract_error_message(e)
                if e.status == 404:
                    warn_msg = (
                        "The 3Di model to which these results belong is owned by an organisation for which "
                        "you do not have sufficient rights. Therefore, you cannot download the computational "
                        "grid (gridadmin.h5) and it cannot be determined to which schematisation the results "
                        "should be downloaded.\n\nContact the servicedesk to obtain access rights to the "
                        "organisation that owns the 3Di model.\n\nPlease select a directory to save the result"
                        " files to."
                    )
                    self.plugin_dock.communication.show_warn(warn_msg)
                    results_dir = self.pick_results_destination_dir()
                elif "Geopackage file not found" in error_msg:
                    pass
                else:
                    raise e
            if not results_dir:
                return
            simulation_subdirectory = os.path.join(results_dir, f"sim_{sim_id}_{simulation_name}")
            downloads = tc.fetch_simulation_downloads(sim_id)
            if gridadmin_downloads is not None:
                downloads.append(gridadmin_downloads)
            if gridadmin_downloads_gpkg is not None:
                downloads.append(gridadmin_downloads_gpkg)
            downloads.sort(key=lambda x: x[-1].size)
            self.last_progress_item = self.tv_model.item(current_row, self.PROGRESS_COLUMN_IDX)
        except ApiException as e:
            error_msg = extract_error_message(e)
            self.plugin_dock.communication.show_error(error_msg)
            return
        except Exception as e:
            error_msg = f"Error: {e}"
            self.plugin_dock.communication.show_error(error_msg)
            return
        self.pb_download.setDisabled(True)
        download_worker = DownloadProgressWorker(simulation, downloads, simulation_subdirectory)
        download_worker.signals.thread_finished.connect(self.on_download_finished_success)
        download_worker.signals.download_failed.connect(self.on_download_finished_failed)
        download_worker.signals.download_progress.connect(self.on_download_progress_update)
        self.download_results_pool.start(download_worker)
