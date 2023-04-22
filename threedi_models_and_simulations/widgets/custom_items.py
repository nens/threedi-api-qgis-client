# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
from qgis.PyQt.QtCore import QSortFilterProxyModel, Qt
from qgis.PyQt.QtGui import QColor, QFont, QPalette
from qgis.PyQt.QtWidgets import (
    QApplication,
    QComboBox,
    QCompleter,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionProgressBar,
)

PROGRESS_ROLE = Qt.UserRole + 1000


class SimulationProgressDelegate(QStyledItemDelegate):
    """Class with definition of the custom simulation progress bar item that can be inserted into the model."""

    def paint(self, painter, option, index):
        status_name, progress_percentage = index.data(PROGRESS_ROLE)
        new_percentage = progress_percentage
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


class FilteredComboBox(QComboBox):
    """Custom QComboBox with filtering option."""

    def __init__(self, parent=None):
        super(FilteredComboBox, self).__init__(parent)

        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLength)
        self.setEditable(True)
        self.filter_proxy_model = QSortFilterProxyModel(self)
        self.filter_proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.filter_proxy_model.setSortCaseSensitivity(Qt.CaseInsensitive)
        self.filter_proxy_model.setSourceModel(self.model())
        self.completer = QCompleter(self.filter_proxy_model, self)
        self.completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.setCompleter(self.completer)
        self.setMinimumSize(150, 25)
        self.setFont(QFont("Segoe UI", 10))
        self.setStyleSheet("QComboBox {background-color: white;}")
        self.setMaxVisibleItems(10)
        self.completer.activated.connect(self.on_completer_activated)
        self.lineEdit().textEdited.connect(self.filter_proxy_model.setFilterFixedString)

    def on_completer_activated(self, text):
        """Set active combobox item when a completer item is picked."""
        if not text:
            return
        idx = self.findText(text)
        self.setCurrentIndex(idx)
        self.activated[str].emit(self.itemText(idx))

    def setModel(self, model):
        """Set completer model after the combobox model."""
        super(FilteredComboBox, self).setModel(model)
        self.filter_proxy_model.setSourceModel(model)
        self.completer.setModel(self.filter_proxy_model)

    def setModelColumn(self, column_idx):
        """Set the correct column for completer and combobox model using column index."""
        self.completer.setCompletionColumn(column_idx)
        self.filter_proxy_model.setFilterKeyColumn(column_idx)
        super(FilteredComboBox, self).setModelColumn(column_idx)
