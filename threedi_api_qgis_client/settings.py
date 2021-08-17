# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import os
from qgis.PyQt.QtWidgets import QDialog
from qgis.PyQt.QtCore import QSettings
from qgis.PyQt import uic


class SettingsDialog(QDialog):
    """Dialog with plugin settings."""

    DEFAULT_API_URL = "https://api.3di.live/v3.0"
    DEFAULT_LATERALS_TIMEOUT = 45

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        ui_filepath = os.path.join(plugin_dir, "ui", "settings.ui")
        self.ui = uic.loadUi(ui_filepath, self)
        self.api_url = None
        self.wss_url = None
        self.laterals_timeout = None
        self.ui.defaults_pb.clicked.connect(self.restore_defaults)
        self.ui.cancel_pb.clicked.connect(self.reject)
        self.ui.save_pb.clicked.connect(self.accept)
        self.load_settings()

    def load_settings(self):
        """Loading plugin settings from QSettings."""
        self.api_url = QSettings().value("threedi/api_url", self.DEFAULT_API_URL, type=str)
        self.wss_url = self.api_url.replace("https:", "wss:").replace("http:", "ws:")
        self.api_url_le.setText(self.api_url)
        self.laterals_timeout = QSettings().value("threedi/laterals_timeout", self.DEFAULT_LATERALS_TIMEOUT, type=int)

    def save_settings(self):
        """Saving plugin settings in QSettings."""
        self.api_url = self.api_url_le.text()
        self.laterals_timeout = self.laterals_timeout_sb.value()
        QSettings().setValue("threedi/api_url", self.api_url)
        QSettings().setValue("threedi/laterals_timeout", self.laterals_timeout)

    def restore_defaults(self):
        """Restoring default settings values."""
        self.api_url_le.setText(self.DEFAULT_API_URL)
        self.laterals_timeout_sb.setValue(self.DEFAULT_LATERALS_TIMEOUT)
        self.save_settings()
        self.load_settings()

    def accept(self):
        """Accepting changes and closing dialog."""
        self.save_settings()
        self.load_settings()
        super().accept()

    def reject(self):
        """Rejecting changes and closing dialog."""
        self.load_settings()
        super().reject()
