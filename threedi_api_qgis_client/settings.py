# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import os
from qgis.PyQt.QtWidgets import QDialog
from qgis.PyQt.QtCore import QSettings
from qgis.PyQt import uic


class SettingsDialog(QDialog):

    DEFAULT_API_URL = "https://api.3di.live/v3.0"

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        ui_filepath = os.path.join(plugin_dir, "ui", "settings.ui")
        self.ui = uic.loadUi(ui_filepath, self)
        self.api_url = None
        self.wss_url = None
        self.ui.defaults_pb.clicked.connect(self.restore_defaults)
        self.ui.cancel_pb.clicked.connect(self.reject)
        self.ui.save_pb.clicked.connect(self.accept)
        self.load_settings()

    def load_settings(self):
        self.api_url = QSettings().value("threedi/api_url", self.DEFAULT_API_URL, type=str)
        self.wss_url = self.api_url.replace("https:", "wss:")
        self.api_url_le.setText(self.api_url)

    def save_settings(self):
        self.api_url = self.api_url_le.text()
        QSettings().setValue("threedi/api_url", self.api_url)

    def restore_defaults(self):
        self.api_url_le.setText(self.DEFAULT_API_URL)
        self.save_settings()
        self.load_settings()

    def accept(self):
        self.save_settings()
        self.load_settings()
        super().accept()

    def reject(self):
        self.load_settings()
        super().reject()
