# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
from time import sleep
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QObject, Qt, QThread, pyqtSignal
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

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.api_client = api_client
        self.simulation_wizard = None
        self.insert_data(
            [('Sim1', 'ldebek', 0), ('Sim2', 'ldebek', 10), ('Sim3', 'ldebek', 20), ('Sim4', 'ldebek', 24)])
        self.pb_new_sim.clicked.connect(self.new_simulation)
        self.thread = QThread()
        self.progress_sentinel = ProgressSentinel(self.api_client)
        self.progress_sentinel.moveToThread(self.thread)
        self.progress_sentinel.progresses_fetched.connect(self.update_progress)
        self.progress_sentinel.finished.connect(self.on_finished)
        self.thread.started.connect(self.progress_sentinel.run)
        self.thread.start()

    def new_simulation(self):
        self.simulation_wizard = SimulationWizard()
        self.simulation_wizard.exec_()

    def stop_fetching_progress(self):
        self.progress_sentinel.stop()

    def update_progress(self, progresses):
        model = self.tv_sim_tree.model()
        row_count = model.rowCount()
        for row_idx in range(row_count):
            progress_item = model.item(row_idx, 2)
            progress_value = progress_item.data(Qt.UserRole+1000)
            if progress_value >= 100:
                self.progress_sentinel.break_loop = True
            progress_item.setData(progress_value+2, Qt.UserRole+1000)

    def insert_data(self, data):
        delegate = ProgressDelegate(self.tv_sim_tree)
        self.tv_sim_tree.setItemDelegateForColumn(2, delegate)
        model = QStandardItemModel(0, 3)
        model.setHorizontalHeaderLabels(["Simulation name", "User", "Progress"])
        for sim_name, user, progress_value in data:
            sim_name_item = QStandardItem(sim_name)
            user_item = QStandardItem(user)
            progress_item = QStandardItem()
            progress_item.setData(progress_value, Qt.UserRole+1000)
            model.appendRow([sim_name_item, user_item, progress_item])
        self.tv_sim_tree.setModel(model)

    def on_finished(self, msg):
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()


class ProgressSentinel(QThread):
    """Worker object that will be moved to a separate thread and will check progresses of the running simulations."""
    finished = pyqtSignal(str)
    progresses_fetched = pyqtSignal(dict)

    def __init__(self, api_client):
        super(QObject, self).__init__()
        self.api_client = api_client
        self.progresses = None
        self.thread_active = True

    def run(self):
        error = ''
        try:
            tc = ThreediCalls(self.api_client)
            while self.thread_active is True:
                self.progresses = tc.all_simulations_progress()
                self.progresses_fetched.emit(self.progresses)
                sleep(2.5)
            self.finished.emit("Simulations finished!")
        except ApiException as e:
            error = str(e)
        self.finished.emit(error)

    def stop(self):
        self.thread_active = False
        self.wait()
