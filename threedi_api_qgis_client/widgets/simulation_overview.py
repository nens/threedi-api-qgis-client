# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
from time import sleep
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem, QPalette, QColor
from qgis.PyQt.QtWidgets import QApplication, QStyledItemDelegate, QStyleOptionProgressBar, QStyle, QMessageBox
from openapi_client import ApiException, Progress
from ..api_calls.threedi_calls import ThreediCalls
from ..widgets.wizard import SimulationWizard

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, 'ui', 'sim_overview.ui'))

PROGRESS_ROLE = Qt.UserRole + 1000


class SimulationOverview(uicls, basecls):
    """Dialog with methods for handling running simulations."""
    def __init__(self, parent_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.parent_dock = parent_dock
        self.api_client = self.parent_dock.api_client
        self.threedi_models = self.parent_dock.threedi_models if self.parent_dock.threedi_models is not None else []
        self.user = self.parent_dock.label_user.text()
        self.simulation_wizard = None
        self.simulations_keys = {}
        self.last_progresses = {}
        self.simulations_without_progress = set()
        self.tv_model = None
        self.setup_view_model()
        self.thread = QThread()
        self.progress_sentinel = ProgressSentinel(self.api_client)
        self.progress_sentinel.moveToThread(self.thread)
        self.progress_sentinel.progresses_fetched.connect(self.update_progress)
        self.progress_sentinel.thread_finished.connect(self.on_finished)
        self.thread.started.connect(self.progress_sentinel.run)
        self.pb_new_sim.clicked.connect(self.new_simulation)
        self.pb_stop_sim.clicked.connect(self.stop_simulation)
        self.thread.start()

    def setup_view_model(self):
        """Setting up model and columns for TreeView."""
        delegate = ProgressDelegate(self.tv_sim_tree)
        self.tv_sim_tree.setItemDelegateForColumn(2, delegate)
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

    def update_progress(self, progresses):
        """Updating progress bars in the running simulations list."""
        for sim_id, (sim, status, progress) in progresses.items():
            if status.name != "initialized":
                continue
            if sim_id not in self.simulations_keys:
                self.add_simulation_to_model(sim, status, progress)
        row_count = self.tv_model.rowCount()
        for row_idx in range(row_count):
            name_item = self.tv_model.item(row_idx, 0)
            sim_id = name_item.data(Qt.UserRole)
            if sim_id in self.simulations_without_progress or sim_id not in progresses:
                continue
            progress_item = self.tv_model.item(row_idx, 2)
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
                self.parent_dock.communication.bar_info(f"Simulation {sim.name} finished!")

    def new_simulation(self):
        """Opening a wizard which allows defining and running new simulations."""
        self.simulation_wizard = SimulationWizard(self.parent_dock)
        models = [(m.name, m.id) for m in self.threedi_models]
        for model in models:
            self.simulation_wizard.p1.main_widget.cbo_db.addItem(*model)
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
                self.parent_dock.communication.bar_info(f"Simulation {name_item.text()} stopped!")
            except ApiException as e:
                self.parent_dock.communication.show_error(e.body)

    def stop_fetching_progress(self):
        """Changing 'thread_active' flag inside background task that is fetching simulations progresses."""
        self.progress_sentinel.stop()

    def on_finished(self, msg):
        """Method for cleaning up background thread after it sends 'thread_finished'."""
        self.parent_dock.communication.bar_info(msg)
        self.thread.quit()
        self.thread.wait()

    def terminate_background_thread(self):
        """Forcing termination of background thread if it's still running."""
        if self.thread.isRunning():
            self.parent_dock.communication.bar_info('Terminating thread.')
            self.thread.terminate()
            self.parent_dock.communication.bar_info('Waiting for thread termination.')
            self.thread.wait()
            self.parent_dock.communication.bar_info('Worker terminated.')


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
            stop_message = e.body
        self.thread_finished.emit(stop_message)

    def stop(self):
        """Changing 'thread_active' flag to False."""
        self.thread_active = False


class ProgressDelegate(QStyledItemDelegate):
    """Class with definition of custom progress bar item that can be inserted into the model."""

    def paint(self, painter, option, index):
        status, progress = index.data(PROGRESS_ROLE)
        status_name = status.name
        pbar = QStyleOptionProgressBar()
        pbar.rect = option.rect
        pbar.minimum = 0
        pbar.maximum = 100
        default_color = QColor(0, 140, 255)
        new_percentage = progress.percentage
        if status_name == "created" or status_name == "starting":
            pbar_color = default_color
            ptext = "starting up simulation .."
        elif status_name == "initialized" or status_name == "postprocessing":
            pbar_color = default_color
            ptext = f"{new_percentage}%"
        elif status_name == "finished":
            pbar_color = QColor(10, 180, 40)
            ptext = f"{new_percentage}%"
        elif status_name == "ended":
            pbar_color = Qt.gray
            ptext = f"{new_percentage}% (stopped)"
        elif status_name == "crashed":
            pbar_color = Qt.red
            ptext = f"{new_percentage}% (crashed)"
        else:
            pbar_color = Qt.lightGray
            ptext = f"{status_name}"

        pbar.progress = new_percentage
        pbar.text = ptext
        pbar.textVisible = True
        palette = pbar.palette
        palette.setColor(QPalette.Highlight, pbar_color)
        pbar.palette = palette
        QApplication.style().drawControl(QStyle.CE_ProgressBar, pbar, painter)
