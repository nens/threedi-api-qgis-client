# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import os
import webbrowser
from uuid import uuid4
from tempfile import gettempdir
from qgis.core import QgsApplication, QgsAuthMethodConfig
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QInputDialog
from qgis.PyQt.QtCore import QSettings, pyqtSignal
from qgis.PyQt import uic
from .communication import UICommunication


class SettingsDialog(QDialog):
    """Dialog with plugin settings."""

    PRODUCTION_API_URL = "https://api.3di.live"
    STAGING_API_URL = "https://api.staging.3di.live"
    DEFAULT_UPLOAD_TIMEOUT = 900

    settings_changed = pyqtSignal()

    def __init__(self, iface, parent=None):
        QDialog.__init__(self, parent)
        plugin_dir = os.path.dirname(os.path.realpath(__file__))
        ui_filepath = os.path.join(plugin_dir, "ui", "settings.ui")
        self.ui = uic.loadUi(ui_filepath, self)
        self.iface = iface
        self.settings_communication = UICommunication(self.iface, "3Di Models and Simulations Settings")
        self.api_url = None
        self.wss_url = None
        self.upload_timeout = None
        self.working_dir = None
        self.browse_pb.clicked.connect(self.set_working_directory)
        self.set_pak_pb.clicked.connect(self.set_personal_api_key)
        self.obtain_pak_pb.clicked.connect(self.obtain_personal_api_key)
        self.ui.defaults_pb.clicked.connect(self.restore_defaults)
        self.ui.cancel_pb.clicked.connect(self.reject)
        self.ui.save_pb.clicked.connect(self.accept)
        self.load_settings()

    @staticmethod
    def get_3di_auth():
        """Getting 3Di credentials from the QGIS Authorization Manager."""
        settings = QSettings()
        authcfg = settings.value("threedi/authcfg", None)
        auth_manager = QgsApplication.authManager()
        cfg = QgsAuthMethodConfig()
        auth_manager.loadAuthenticationConfig(authcfg, cfg, True)
        username = cfg.config("username")
        password = cfg.config("password")
        return username, password

    @staticmethod
    def set_3di_auth(personal_api_key, username="__key__"):
        """Setting 3Di credentials in the QGIS Authorization Manager."""
        settings = QSettings()
        authcfg = settings.value("threedi/authcfg", None)
        cfg = QgsAuthMethodConfig()
        auth_manager = QgsApplication.authManager()
        auth_manager.setMasterPassword()
        auth_manager.loadAuthenticationConfig(authcfg, cfg, True)

        if cfg.id():
            cfg.setConfig("username", username)
            cfg.setConfig("password", personal_api_key)
            auth_manager.updateAuthenticationConfig(cfg)
        else:
            cfg.setMethod("Basic")
            cfg.setName("3Di Personal Api Key")
            cfg.setConfig("username", username)
            cfg.setConfig("password", personal_api_key)
            auth_manager.storeAuthenticationConfig(cfg)
            settings.setValue("threedi/authcfg", cfg.id())

    def set_personal_api_key(self):
        """Setting active Personal API Key."""
        pak, accept = QInputDialog.getText(self, "Personal API Key", "Paste your Personal API Key:")
        if accept is False:
            return
        self.set_3di_auth(pak)
        self.set_personal_api_key_label(True)

    @staticmethod
    def obtain_personal_api_key():
        """Open website where user can get his Personal API Key."""
        webbrowser.open("https://management.3di.live/personal_api_keys/")

    def set_personal_api_key_label(self, personal_api_key_available):
        """Setting Personal API Key label text."""
        if personal_api_key_available:
            label_txt = """<html><head/><body><p><span style=" color:#00aa00;">
            ✓ Available</span></p></body></html>"""
        else:
            label_txt = """<html><head/><body><p><span style=" color:#ff0000;">
            ✕ Not found</span></p></body></html>"""
        self.pak_label.setText(label_txt)

    def set_working_directory(self):
        """Set working directory path widget."""
        work_dir = QFileDialog.getExistingDirectory(self, "Select Working Directory", self.working_dir)
        if work_dir:
            try:
                self.try_to_write(work_dir)
            except (PermissionError, OSError):
                self.settings_communication.bar_warn(
                    "Can't write to the selected location. Please select a folder to which you have write permission."
                )
                return
            self.working_dir_le.setText(work_dir)

    def load_settings(self):
        """Loading plugin settings from QSettings."""
        self.api_url = QSettings().value("threedi/api_url", self.PRODUCTION_API_URL, type=str)
        self.wss_url = self.api_url.replace("https:", "wss:").replace("http:", "ws:")
        self.api_url_le.setText(self.api_url)
        self.working_dir = QSettings().value("threedi/working_dir", "", type=str)
        self.working_dir_le.setText(self.working_dir)
        self.upload_timeout = QSettings().value("threedi/upload_timeout", self.DEFAULT_UPLOAD_TIMEOUT, type=int)
        username, password = self.get_3di_auth()
        if password:
            self.set_personal_api_key_label(True)
        else:
            self.set_personal_api_key_label(False)

    def save_settings(self):
        """Saving plugin settings in QSettings."""
        self.api_url = self.api_url_le.text()
        self.working_dir = self.working_dir_le.text()
        self.upload_timeout = self.upload_timeout_sb.value()
        QSettings().setValue("threedi/api_url", self.api_url)
        QSettings().setValue("threedi/working_dir", self.working_dir)
        QSettings().setValue("threedi/upload_timeout", self.upload_timeout)

    def settings_are_valid(self):
        """Check validity of the settings."""
        if not self.working_dir or not os.path.exists(self.working_dir):
            working_dir_txt = self.working_dir_le.text()
            if not working_dir_txt or not os.path.exists(working_dir_txt):
                self.settings_communication.bar_warn(
                    "Missing or invalid working directory. Please set it up before running the plugin."
                )
                return False
            else:
                return True
        else:
            return True

    @staticmethod
    def try_to_write(working_dir):
        """Try to write and remove an empty text file into given location."""
        test_filename = f"{uuid4()}.txt"
        test_file_path = os.path.join(working_dir, test_filename)
        with open(test_file_path, "w") as test_file:
            test_file.write("")
        os.remove(test_file_path)

    def default_working_dir(self):
        """Return default working directory location."""
        user_dir = os.path.expanduser("~")
        try:
            threedi_working_dir = os.path.join(user_dir, "Documents", "3Di")
            os.makedirs(threedi_working_dir, exist_ok=True)
            self.try_to_write(threedi_working_dir)
        except (PermissionError, OSError):
            threedi_working_dir = gettempdir()
        return threedi_working_dir

    def restore_defaults(self):
        """Restoring default settings values."""
        self.api_url_le.setText(self.PRODUCTION_API_URL)
        self.working_dir_le.setText(self.default_working_dir() or "")
        self.upload_timeout_sb.setValue(self.DEFAULT_UPLOAD_TIMEOUT)

    def accept(self):
        """Accepting changes and closing dialog."""
        if self.settings_are_valid():
            self.save_settings()
            self.load_settings()
            self.settings_changed.emit()
            super().accept()

    def reject(self):
        """Rejecting changes and closing dialog."""
        self.load_settings()
        if self.settings_are_valid():
            super().reject()

    def exec_(self):
        """Opening settings dialog."""
        self.load_settings()
        super().exec_()
