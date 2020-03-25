# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
from time import sleep
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem
from qgis.PyQt.QtWidgets import QApplication, QStyledItemDelegate, QStyleOptionProgressBar, QStyle, QMessageBox
from ..api_calls.threedi_calls import ThreediCalls, ApiException
from ..widgets.wizard import SimulationWizard

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, 'ui', 'sim_overview.ui'))


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
        self.simulations_finished = set()
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

    def add_simulation_to_model(self, simulation, progress=None):
        """Method for adding simulation to the model."""
        sim_id = simulation.id
        sim_name_item = QStandardItem(f"{simulation.name} [{sim_id}]")
        sim_name_item.setData(sim_id, Qt.UserRole)
        user_item = QStandardItem(self.user)
        progress_item = QStandardItem()
        new_progress_value = progress.percentage if progress is not None else 0
        progress_item.setData(new_progress_value, Qt.UserRole + 1000)
        self.tv_model.appendRow([sim_name_item, user_item, progress_item])
        self.simulations_keys[sim_id] = simulation

    def update_progress(self, progresses):
        """Updating progress bars in the running simulations list."""
        for sim_id, (sim, progress) in progresses.items():
            if progress.percentage == 0 or progress.percentage == 100:
                continue
            if sim_id not in self.simulations_keys:
                self.add_simulation_to_model(sim, progress)
        row_count = self.tv_model.rowCount()
        for row_idx in range(row_count):
            name_item = self.tv_model.item(row_idx, 0)
            sim_id = name_item.data(Qt.UserRole)
            if sim_id in self.simulations_finished:
                continue
            progress_item = self.tv_model.item(row_idx, 2)
            sim, new_progress = progresses[sim_id]
            new_progress_value = int(new_progress.percentage)
            progress_item.setData(new_progress_value, Qt.UserRole + 1000)
            if new_progress_value == 100:
                self.simulations_finished.add(sim_id)
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
            self.add_simulation_to_model(new_simulation)

    def stop_simulation(self):
        """Sending request to shutdown currently selected simulation."""
        index = self.tv_sim_tree.currentIndex()
        if not index.isValid():
            return
        title = "Warning"
        question = "This simulation is now running.\nAre you sure you want to stop it?"
        answer = self.parent_dock.communication.ask(self, title, question, QMessageBox.Warning)
        if answer is True:
            name_item = self.tv_model.item(index.row(), 0)
            sim_id = name_item.data(Qt.UserRole)
            tc = ThreediCalls(self.parent_dock.api_client)
            tc.make_action_on_simulation(sim_id, name='shutdown')
            self.parent_dock.communication.bar_info(f"Simulation {name_item.text()} stopped!")

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
    DELAY = 2.5

    def __init__(self, api_client):
        super(QObject, self).__init__()
        self.api_client = api_client
        self.progresses = None
        self.thread_active = True

    @pyqtSlot()
    def run(self):
        """Checking running simulations progresses."""
        stop_message = "Checking running simulation stopped."
        try:
            tc = ThreediCalls(self.api_client)
            while self.thread_active:
                self.progresses = tc.all_simulations_progress()
                self.progresses_fetched.emit(self.progresses)
                sleep(self.DELAY)
        except ApiException as e:
            stop_message = e.body
        self.thread_finished.emit(stop_message)

    def stop(self):
        """Changing 'thread_active' flag to False."""
        self.thread_active = False


class ProgressDelegate(QStyledItemDelegate):
    """Class with definition of custom progress bar item that can be inserted into the model."""
    def paint(self, painter, option, index):
        pvalue = index.data(Qt.UserRole + 1000)
        pbar = QStyleOptionProgressBar()
        pbar.rect = option.rect
        pbar.minimum = 0
        pbar.maximum = 100
        pbar.progress = pvalue
        pbar.text = f"{pvalue}%"
        pbar.textVisible = True
        QApplication.style().drawControl(QStyle.CE_ProgressBar, pbar, painter)
