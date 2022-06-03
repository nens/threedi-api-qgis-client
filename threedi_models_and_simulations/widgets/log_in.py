# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2022 by Lutra Consulting for 3Di Water Management
import logging
import os
from functools import wraps
from time import sleep
from qgis.PyQt import uic
from threedi_api_client.openapi import ApiException
from ..api_calls.threedi_calls import get_api_client, ThreediCalls
from ..utils import extract_error_message


base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "log_in.ui"))

logger = logging.getLogger(__name__)


def api_client_required(fn):
    """Decorator for limiting functionality access to logged-in user (with option to log in)."""

    @wraps(fn)
    def wrapper(self):
        if hasattr(self, "plugin_dock"):
            plugin_dock = getattr(self, "plugin_dock")
        else:
            plugin_dock = self
        threedi_api = getattr(plugin_dock, "threedi_api", None)
        if threedi_api is None:
            plugin_dock.communication.bar_info("Action reserved for logged in users. Please log-in before proceeding.")
            log_in_dialog = LogInDialog(plugin_dock)
            accepted = log_in_dialog.exec_()
            if accepted:
                plugin_dock.threedi_api = log_in_dialog.threedi_api
                plugin_dock.current_user = log_in_dialog.user
                plugin_dock.current_user_full_name = log_in_dialog.user_full_name
                plugin_dock.organisations = log_in_dialog.organisations
                plugin_dock.initialize_authorized_view()
            else:
                plugin_dock.communication.bar_warn("Logging-in canceled. Action aborted!")
                return

        return fn(self)

    return wrapper


class AuthorizationException(Exception):
    pass


class LogInDialog(uicls, basecls):
    """Dialog with widgets and methods used in logging process."""

    def __init__(self, plugin_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.plugin_dock = plugin_dock
        self.communication = self.plugin_dock.communication
        self.user = None
        self.user_full_name = None
        self.threedi_api = None
        self.api_url = self.plugin_dock.plugin_settings.api_url
        self.client_id = None
        self.scope = None
        self.organisations = {}
        self.log_in_widget.hide()
        self.wait_widget.hide()
        self.pb_log_in.clicked.connect(self.log_in_threedi)
        self.pb_cancel.clicked.connect(self.reject)
        self.resize(500, 250)
        self.show_log_widget()

    def show_log_widget(self):
        """Showing logging form widget."""
        self.log_in_widget.show()
        self.setWindowTitle("Log in")

    def show_wait_widget(self):
        """Showing widget with logging progress."""
        self.log_in_widget.hide()
        self.wait_widget.show()

    def log_in_threedi(self):
        """Method which runs all logging widgets methods and setting up needed variables."""
        api_url_error_message = (
            f"Error: Invalid Base API URL '{self.api_url}'. "
            f"The 3Di API expects that the version is not included. "
            f"Please change the Base API URL in the 3Di Models and Simulations plugin settings."
        )
        missing_personal_api_key_message = (
            "Personal API Key is not set. " "Please set it in the plugin settings before trying to log in."
        )
        try:
            self.show_wait_widget()
            self.fetch_msg.hide()
            self.done_msg.hide()
            self.log_pbar.setValue(25)
            username, password = self.plugin_dock.plugin_settings.get_3di_auth()
            if not username or not password:
                raise AuthorizationException(missing_personal_api_key_message)
            self.threedi_api = get_api_client(username, password, self.api_url)
            tc = ThreediCalls(self.threedi_api)
            user_profile = tc.fetch_current_user()
            self.user = user_profile.username
            self.user_full_name = f"{user_profile.first_name} {user_profile.last_name}"
            self.wait_widget.update()
            self.log_pbar.setValue(75)
            self.fetch_msg.show()
            self.organisations = {org.unique_id: org for org in tc.fetch_organisations()}
            self.done_msg.show()
            self.wait_widget.update()
            self.log_pbar.setValue(100)
            sleep(1)
            super().accept()
        except ApiException as e:
            self.close()
            if e.status == 404:
                error_msg = api_url_error_message
            else:
                error_msg = extract_error_message(e)
            self.communication.show_error(error_msg)
        except Exception as e:
            if "THREEDI_API_HOST" in str(e):
                error_msg = api_url_error_message
            else:
                error_msg = f"Error: {e}"
            self.close()
            self.communication.show_error(error_msg)

    def reject(self):
        super().reject()
