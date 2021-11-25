# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import os
from uuid import uuid4
from tempfile import gettempdir
from qgis.PyQt.QtWidgets import QDialog, QFileDialog
from qgis.PyQt.QtCore import QSettings, pyqtSignal
from qgis.PyQt import uic
from .communication import UICommunication


class SettingsDialog(QDialog):
    """Dialog with plugin settings."""

    DEFAULT_API_URL = "https://api.3di.live"
    DEFAULT_LATERALS_TIMEOUT = 45

    settings_saved = pyqtSignal()

    def __init__(self, iface, parent=None):
        QDialog.__init__(self, parent)
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        ui_filepath = os.path.join(plugin_dir, "ui", "settings.ui")
        self.ui = uic.loadUi(ui_filepath, self)
        self.iface = iface
        self.settings_communication = UICommunication(self.iface, "3Di MI Settings")
        self.api_url = None
        self.wss_url = None
        self.laterals_timeout = None
        self.working_dir = None
        self.browse_pb.clicked.connect(self.set_working_directory)
        self.ui.defaults_pb.clicked.connect(self.restore_defaults)
        self.ui.cancel_pb.clicked.connect(self.reject)
        self.ui.save_pb.clicked.connect(self.accept)
        self.load_settings()

    def set_working_directory(self):
        """Set working directory path widget."""
        work_dir = QFileDialog.getExistingDirectory(self, "Select Working Directory", self.working_dir)
        if work_dir:
            try:
                test_filename = f"{uuid4()}.txt"
                test_file_path = os.path.join(work_dir, test_filename)
                with open(test_file_path, "w") as test_file:
                    test_file.write("")
                os.remove(test_file_path)
            except (PermissionError, OSError):
                self.settings_communication.bar_warn(
                    "Can't write to the selected location. Please select a folder to which you have write permission."
                )
                return
            self.working_dir_le.setText(work_dir)

    def load_settings(self):
        """Loading plugin settings from QSettings."""
        self.api_url = QSettings().value("threedi/api_url", self.DEFAULT_API_URL, type=str)
        self.wss_url = self.api_url.replace("https:", "wss:").replace("http:", "ws:")
        self.api_url_le.setText(self.api_url)
        self.working_dir = QSettings().value("threedi/working_dir", "", type=str)
        self.working_dir_le.setText(self.working_dir)
        self.laterals_timeout = QSettings().value("threedi/laterals_timeout", self.DEFAULT_LATERALS_TIMEOUT, type=int)

    def save_settings(self):
        """Saving plugin settings in QSettings."""
        self.api_url = self.api_url_le.text()
        self.working_dir = self.working_dir_le.text()
        self.laterals_timeout = self.laterals_timeout_sb.value()
        QSettings().setValue("threedi/api_url", self.api_url)
        QSettings().setValue("threedi/working_dir", self.working_dir)
        QSettings().setValue("threedi/laterals_timeout", self.laterals_timeout)
        self.settings_saved.emit()

    def settings_are_valid(self):
        """Check validity of the settings."""
        if not self.working_dir or not os.path.exists(self.working_dir):
            self.settings_communication.bar_warn(
                "Missing or invalid working directory. Please set it up before running the plugin."
            )
            return False
        else:
            return True

    def restore_defaults(self):
        """Restoring default settings values."""
        self.api_url_le.setText(self.DEFAULT_API_URL)
        self.working_dir_le.setText(gettempdir() or "")
        self.laterals_timeout_sb.setValue(self.DEFAULT_LATERALS_TIMEOUT)
        self.save_settings()
        self.load_settings()

    def accept(self):
        """Accepting changes and closing dialog."""
        if self.settings_are_valid():
            self.save_settings()
            self.load_settings()
            super().accept()

    def reject(self):
        """Rejecting changes and closing dialog."""
        self.load_settings()
        if self.settings_are_valid():
            super().reject()
