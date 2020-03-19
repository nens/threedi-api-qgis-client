# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management

from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import QgsMessageLog, Qgis


class UICommunication(object):

    def __init__(self, iface, context):
        self.iface = iface
        self.context = context
        self.message_bar = self.iface.messageBar()

    def show_info(self, msg, parent=None, context=None):
        if self.iface is not None:
            parent = parent if parent is not None else self.iface.mainWindow()
            context = self.context if context is None else context
            QMessageBox.information(parent, context, msg)
        else:
            print(msg)

    def show_warn(self, msg, parent=None, context=None):
        if self.iface is not None:
            parent = parent if parent is not None else self.iface.mainWindow()
            context = self.context if context is None else context
            QMessageBox.warning(parent, context, msg)
        else:
            print(msg)

    def show_error(self, msg, parent=None, context=None):
        if self.iface is not None:
            parent = parent if parent is not None else self.iface.mainWindow()
            context = self.context if context is None else context
            QMessageBox.critical(parent, context, msg)
        else:
            print(msg)

    def bar_info(self, msg, dur=5):
        if self.iface is not None:
            self.message_bar.pushMessage(self.context, msg, level=Qgis.Info, duration=dur)
        else:
            print(msg)

    def bar_warn(self, msg, dur=5):
        if self.iface is not None:
            self.message_bar.pushMessage(self.context, msg, level=Qgis.Warning, duration=dur)
        else:
            print(msg)

    def bar_error(self, msg, dur=5):
        if self.iface is not None:
            self.message_bar.pushMessage(self.context, msg, level=Qgis.Critical, duration=dur)
        else:
            print(msg)
