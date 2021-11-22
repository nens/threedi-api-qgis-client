# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import logging
import os
from time import sleep
from qgis.PyQt import uic
from threedi_api_client.openapi import ApiException
from ..api_calls.threedi_calls import get_api_client, ThreediCalls

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_log, basecls_log = uic.loadUiType(os.path.join(base_dir, "ui", "log_in.ui"))

logger = logging.getLogger(__name__)


class LogInDialog(uicls_log, basecls_log):
    """Dialog with widgets and methods used in logging process."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.plugin = plugin
        self.communication = self.plugin.communication
        self.user = None
        self.threedi_api = None
        self.organisations = None
        self.organisation = None
        self.log_in_widget.hide()
        self.wait_widget.hide()
        self.organisation_widget.hide()
        self.pb_organisation.clicked.connect(self.set_organisation)
        self.pb_log_in.clicked.connect(self.log_in_threedi)
        self.pb_cancel.clicked.connect(self.reject)
        self.pb_cancel_organisation.clicked.connect(self.reject)
        self.resize(500, 250)
        self.show_log_widget()

    def show_log_widget(self):
        """Showing logging form widget."""
        self.organisation_widget.hide()
        self.log_in_widget.show()
        self.setWindowTitle("Log in")

    def show_wait_widget(self):
        """Showing widget with logging progress."""
        self.log_in_widget.hide()
        self.wait_widget.show()

    def show_organisation_widget(self):
        """Showing widget with organisation choice"""
        self.wait_widget.hide()
        self.organisation_widget.show()
        self.setWindowTitle("Choose organisation")
        for org in self.organisations.values():
            self.organisations_box.addItem(org.name, org)

    def fetch_organisations(self):
        """Fetching organisations list."""
        tc = ThreediCalls(self.threedi_api)
        organisations = tc.fetch_organisations()
        return organisations

    def log_in_threedi(self):
        """Method which runs all logging widgets methods and setting up needed variables."""
        try:
            self.show_wait_widget()
            self.fetch_msg.hide()
            self.done_msg.hide()
            username = self.le_user.text()
            password = self.le_pass.text()
            self.le_user.setText("")
            self.le_pass.setText("")
            self.log_pbar.setValue(20)
            self.threedi_api = get_api_client(username, password, self.plugin.plugin_settings.api_url)
            self.user = username
            self.fetch_msg.show()
            self.wait_widget.update()
            self.log_pbar.setValue(50)
            self.organisations = {org.unique_id: org for org in self.fetch_organisations()}
            self.log_pbar.setValue(80)
            self.done_msg.show()
            self.wait_widget.update()
            self.log_pbar.setValue(100)
            sleep(1)
            if len(self.organisations) > 1:
                self.show_organisation_widget()
            else:
                organisation = next(iter(self.organisations.values()))
                self.organisations_box.addItem(organisation.name, organisation)
                self.set_organisation()
        except ApiException as e:
            self.close()
            error_body = e.body
            error_details = error_body["details"] if "details" in error_body else error_body
            error_msg = f"Error: {error_details}"
            self.communication.show_error(error_msg)
        except Exception as e:
            self.close()
            error_msg = f"Error: {e}"
            self.communication.show_error(error_msg)

    def set_organisation(self):
        """Set picked organisation."""
        self.organisation = self.organisations_box.currentData()
        super().accept()
