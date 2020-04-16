# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPalette, QColor
from qgis.PyQt.QtWidgets import QApplication, QStyledItemDelegate, QStyleOptionProgressBar, QStyle

PROGRESS_ROLE = Qt.UserRole + 1000


class SimulationProgressDelegate(QStyledItemDelegate):
    """Class with definition of the custom simulation progress bar item that can be inserted into the model."""

    def paint(self, painter, option, index):
        status, progress = index.data(PROGRESS_ROLE)
        status_name = status.name
        new_percentage = progress.percentage
        pbar = QStyleOptionProgressBar()
        pbar.rect = option.rect
        pbar.minimum = 0
        pbar.maximum = 100
        default_color = QColor(0, 140, 255)

        if status_name == "created" or status_name == "starting":
            pbar_color = default_color
            ptext = "Starting up simulation .."
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


class DownloadProgressDelegate(QStyledItemDelegate):
    """Class with definition of the custom downloading results progress bar item that can be inserted into the model."""

    def paint(self, painter, option, index):
        new_percentage = int(index.data(Qt.UserRole))
        pbar = QStyleOptionProgressBar()
        pbar.rect = option.rect
        pbar.minimum = 0
        pbar.maximum = 100
        default_color = QColor(0, 140, 255)

        if new_percentage < 0:
            new_percentage = 0
            pbar_color = Qt.lightGray
            ptext = f"Ready to download"
        elif 0 <= new_percentage < 100:
            pbar_color = default_color
            ptext = f"Downloading ({new_percentage}%) .."
        elif new_percentage == 100:
            pbar_color = QColor(10, 180, 40)
            ptext = f"Download finished"
        else:
            new_percentage = 100
            pbar_color = Qt.red
            ptext = f"Download failed"

        pbar.progress = new_percentage
        pbar.text = ptext
        pbar.textVisible = True
        palette = pbar.palette
        palette.setColor(QPalette.Highlight, pbar_color)
        pbar.palette = palette
        QApplication.style().drawControl(QStyle.CE_ProgressBar, pbar, painter)
