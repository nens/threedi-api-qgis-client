# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
from enum import Enum
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QMessageBox, QInputDialog, QPushButton, QProgressBar
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem, QBrush, QColor
from qgis.core import Qgis


class UICommunication(object):
    """Class with methods for handling messages using QGIS interface and logging list view."""

    def __init__(self, iface, context, list_view=None):
        self.iface = iface
        self.context = context
        self.message_bar = self.iface.messageBar()
        self.list_view = list_view
        if self.list_view:
            self.model = QStandardItemModel()
            self.list_view.setModel(self.model)

    def show_info(self, msg, parent=None, context=None):
        """Showing info dialog."""
        if self.iface is not None:
            parent = parent if parent is not None else self.iface.mainWindow()
            context = self.context if context is None else context
            QMessageBox.information(parent, context, msg)
        else:
            print(msg)

    def show_warn(self, msg, parent=None, context=None):
        """Showing warning dialog."""
        if self.iface is not None:
            parent = parent if parent is not None else self.iface.mainWindow()
            context = self.context if context is None else context
            QMessageBox.warning(parent, context, msg)
        else:
            print(msg)

    def show_error(self, msg, parent=None, context=None):
        """Showing error dialog."""
        if self.iface is not None:
            parent = parent if parent is not None else self.iface.mainWindow()
            context = self.context if context is None else context
            QMessageBox.critical(parent, context, msg)
        else:
            print(msg)

    def bar_info(self, msg, dur=5, log_text_color=QColor(Qt.black)):
        """Showing info message bar."""
        if self.iface is not None:
            self.message_bar.pushMessage(self.context, msg, level=Qgis.Info, duration=dur)
            if self.list_view:
                item = QStandardItem(msg)
                item.setForeground(QBrush(log_text_color))
                self.model.appendRow([item])
        else:
            print(msg)

    def bar_warn(self, msg, dur=5, log_text_color=QColor(Qt.black)):
        """Showing warning message bar."""
        if self.iface is not None:
            self.message_bar.pushMessage(self.context, msg, level=Qgis.Warning, duration=dur)
            if self.list_view:
                item = QStandardItem(msg)
                item.setForeground(QBrush(log_text_color))
                self.model.appendRow([item])
        else:
            print(msg)

    def bar_error(self, msg, dur=5, log_text_color=QColor(Qt.black)):
        """Showing error message bar."""
        if self.iface is not None:
            self.message_bar.pushMessage(self.context, msg, level=Qgis.Critical, duration=dur)
            if self.list_view:
                item = QStandardItem(msg)
                item.setForeground(QBrush(log_text_color))
                self.model.appendRow([item])
        else:
            print(msg)

    @staticmethod
    def ask(parent, title, question, box_icon=QMessageBox.Question):
        """Ask for operation confirmation."""
        msg_box = QMessageBox(parent)
        msg_box.setIcon(box_icon)
        msg_box.setWindowTitle(title)
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setText(question)
        msg_box.setStandardButtons(QMessageBox.No | QMessageBox.Yes)
        msg_box.setDefaultButton(QMessageBox.No)
        res = msg_box.exec_()
        if res == QMessageBox.No:
            return False
        else:
            return True

    @staticmethod
    def custom_ask(parent, title, question, *buttons_labels):
        """Ask for custom operation confirmation."""
        msg_box = QMessageBox(parent)
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle(title)
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setText(question)
        for button_txt in buttons_labels:
            msg_box.addButton(QPushButton(button_txt), QMessageBox.YesRole)
        msg_box.exec_()
        clicked_button = msg_box.clickedButton()
        clicked_button_text = clicked_button.text()
        return clicked_button_text

    def pick_item(self, title, message, parent=None, *items):
        """Getting item from list of items."""
        parent = parent if parent is not None else self.iface.mainWindow()
        item, accept = QInputDialog.getItem(parent, title, message, items, editable=False)
        if accept is False:
            return None
        return item

    def progress_bar(self, msg, minimum=0, maximum=0, init_value=0, clear_msg_bar=False):
        """Setting progress bar."""
        if self.iface is None:
            return None
        if clear_msg_bar:
            self.iface.messageBar().clearWidgets()
        pmb = self.iface.messageBar().createMessage(msg)
        pb = QProgressBar()
        pb.setMinimum(minimum)
        pb.setMaximum(maximum)
        pb.setValue(init_value)
        pb.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        pmb.layout().addWidget(pb)
        self.iface.messageBar().pushWidget(pmb, Qgis.Info)
        return pb

    def clear_message_bar(self):
        """Clearing message bar."""
        if self.iface is None:
            return None
        self.iface.messageBar().clearWidgets()


class ListViewLogger(object):
    """Class with methods for handling messages using list view."""

    def __init__(self, list_view=None):
        self.list_view = list_view
        self.model = QStandardItemModel()
        self.list_view.setModel(self.model)

    def clear(self):
        """Clear list view model."""
        self.list_view.model().clear()

    def log_info(self, msg, log_text_color=QColor(Qt.darkGreen)):
        """Showing info message bar."""
        if self.list_view is not None:
            item = QStandardItem(msg)
            item.setForeground(QBrush(log_text_color))
            self.model.appendRow([item])
        else:
            print(msg)

    def log_warn(self, msg, log_text_color=QColor(Qt.darkYellow)):
        """Showing warning message bar."""
        if self.list_view is not None:
            item = QStandardItem(msg)
            item.setForeground(QBrush(log_text_color))
            self.model.appendRow([item])
        else:
            print(msg)

    def log_error(self, msg, log_text_color=QColor(Qt.red)):
        """Showing error message bar."""
        if self.list_view is not None:
            item = QStandardItem(msg)
            item.setForeground(QBrush(log_text_color))
            self.model.appendRow([item])
        else:
            print(msg)


class TreeViewLogger(object):
    """Class with methods for handling messages using list view."""

    def __init__(self, tree_view=None, header=None):
        self.tree_view = tree_view
        self.header = header
        self.model = QStandardItemModel()
        self.tree_view.setModel(self.model)
        self.levels_colors = {
            LogLevels.INFO.value: QColor(Qt.black),
            LogLevels.WARNING.value: QColor(229, 144, 80),
            LogLevels.ERROR.value: QColor(Qt.red),
        }
        self.initialize_view()

    def clear(self):
        """Clear list view model."""
        self.tree_view.model().clear()

    def initialize_view(self):
        """Clear list view model and set header columns if available."""
        self.tree_view.model().clear()
        if self.header:
            self.tree_view.model().setHorizontalHeaderLabels(self.header)

    def log_result_row(self, row, log_level):
        """Show row data with proper log level styling."""
        text_color = self.levels_colors[log_level]
        if self.tree_view is not None:
            items = []
            for value in row:
                item = QStandardItem(str(value))
                item.setForeground(QBrush(text_color))
                items.append(item)
            self.model.appendRow(items)
            for i in range(len(self.header)):
                self.tree_view.resizeColumnToContents(i)
        else:
            print(row)


class LogLevels(Enum):
    """Model Checker log levels."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
