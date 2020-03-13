# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem
from qgis.PyQt.QtWidgets import QApplication, QStyledItemDelegate, QStyleOptionProgressBar, QStyle

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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.timer = QTimer()
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.update_progress)

    def update_progress(self):
        model = self.tv_sim_tree.model()
        row_count = model.rowCount()
        for row_idx in range(row_count):
            progress_item = model.item(row_idx, 2)
            progress_value = progress_item.data(Qt.UserRole+1000)
            if progress_value >= 100:
                continue
            progress_item.setData(progress_value + 2, Qt.UserRole + 1000)

    def insert_data(self, data):
        delegate = ProgressDelegate(self.tv_sim_tree)
        self.tv_sim_tree.setItemDelegateForColumn(2, delegate)
        model = QStandardItemModel(0, 3)
        model.setHorizontalHeaderLabels(["Simulation name", "User", "Progress"])
        for sim_name, user, progress_value in data:
            sim_name_item = QStandardItem(sim_name)
            user_item = QStandardItem(user)
            progress_item = QStandardItem()
            progress_item.setData(progress_value, Qt.UserRole + 1000)
            model.appendRow([sim_name_item, user_item, progress_item])
        self.tv_sim_tree.setModel(model)
