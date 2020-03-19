# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
from time import sleep
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem
from qgis.PyQt.QtWidgets import QApplication, QStyledItemDelegate, QStyleOptionProgressBar, QStyle
from ..api_calls.threedi_calls import ThreediCalls, ApiException
from ..widgets.wizard import SimulationWizard

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, 'ui', 'sim_overview.ui'))


class ProgressDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        pvalue = index.data(Qt.UserRole+1000)
        pbar = QStyleOptionProgressBar()
        pbar.rect = option.rect
        pbar.minimum = 0
        pbar.maximum = 100
        pbar.progress = pvalue
        pbar.text = f"{pvalue}%"
        pbar.textVisible = True
        QApplication.style().drawControl(QStyle.CE_ProgressBar, pbar, painter)


class SimulationOverview(uicls, basecls):

    def __init__(self, parent_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.parent_dock = parent_dock
        self.api_client = self.parent_dock.api_client
        self.threedi_models = self.parent_dock.threedi_models if self.parent_dock.threedi_models is not None else []
        self.user = self.parent_dock.label_user.text()
        self.simulation_wizard = None
        self.simulation_keys = {}
        self.tv_model = None
        self.setup_view_model()
        self.thread = QThread()
        self.progress_sentinel = ProgressSentinel(self.api_client)
        self.progress_sentinel.moveToThread(self.thread)
        self.progress_sentinel.progresses_fetched.connect(self.update_progress)
        self.progress_sentinel.thread_finished.connect(self.on_finished)
        self.thread.started.connect(self.progress_sentinel.run)
        self.pb_new_sim.clicked.connect(self.new_simulation)
        self.thread.start()

    def new_simulation(self):
        self.simulation_wizard = SimulationWizard()
        models = [m.name for m in self.threedi_models]
        self.simulation_wizard.p1.main_widget.cbo_db.addItems(models)
        self.simulation_wizard.exec_()

    def setup_view_model(self):
        delegate = ProgressDelegate(self.tv_sim_tree)
        self.tv_sim_tree.setItemDelegateForColumn(2, delegate)
        self.tv_model = QStandardItemModel(0, 3)
        self.tv_model.setHorizontalHeaderLabels(["Simulation name", "User", "Progress"])
        self.tv_sim_tree.setModel(self.tv_model)

    def update_progress(self, progresses):
        for sim_id, (sim, progress) in progresses.items():
            if progress.percentage == 0 and progress.time == 0:
                continue
            if sim_id not in self.simulation_keys:
                sim_name_item = QStandardItem(sim.name)
                sim_name_item.setData(sim_id, Qt.UserRole)
                user_item = QStandardItem(self.user)
                progress_item = QStandardItem()
                new_progress_value = int(progress.percentage)
                progress_item.setData(new_progress_value, Qt.UserRole + 1000)
                self.tv_model.appendRow([sim_name_item, user_item, progress_item])
                self.simulation_keys[sim_id] = sim

        row_count = self.tv_model.rowCount()
        for row_idx in range(row_count):
            name_item = self.tv_model.item(row_idx, 0)
            sim_id = name_item.data(Qt.UserRole)
            progress_item = self.tv_model.item(row_idx, 2)
            sim, new_progress = progresses[sim_id]
            new_progress_value = int(new_progress.percentage)
            progress_item.setData(new_progress_value, Qt.UserRole + 1000)

    def stop_fetching_progress(self):
        self.progress_sentinel.stop()

    def on_finished(self, msg):
        self.thread.quit()
        self.thread.wait()

    def terminate_background_thread(self):
        if self.thread.isRunning():
            print('Terminating thread.')
            self.thread.terminate()
            print('Waiting for thread termination.')
            self.thread.wait()
            print('Worker terminated.')


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
        error = ''
        try:
            tc = ThreediCalls(self.api_client)
            while self.thread_active:
                self.progresses = tc.all_simulations_progress()
                self.progresses_fetched.emit(self.progresses)
                sleep(self.DELAY)
            self.thread_finished.emit("Simulations finished!")
        except ApiException as e:
            error = str(e)
        self.thread_finished.emit(error)

    def stop(self):
        self.thread_active = False
