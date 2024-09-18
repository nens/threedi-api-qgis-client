# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import logging
import os
from functools import wraps
from time import sleep

from qgis.PyQt import uic
from qgis.PyQt.QtCore import QTimer
from threedi_api_client.openapi import ApiException

from ..api_calls.threedi_calls import ThreediCalls, get_api_client_with_personal_api_token
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
            plugin_dock.communication.bar_info("Action reserved for logged in users. Logging-in...")
            log_in_dialog = LogInDialog(plugin_dock)
            log_in_dialog.show()
            QTimer.singleShot(10, log_in_dialog.log_in_threedi)
            log_in_dialog.exec_()
            if log_in_dialog.LOGGED_IN:
                plugin_dock.threedi_api = log_in_dialog.threedi_api
                plugin_dock.current_user = log_in_dialog.user
                plugin_dock.current_user_first_name = log_in_dialog.user_first_name
                plugin_dock.current_user_last_name = log_in_dialog.user_last_name
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

    LOGGED_IN = False

    def __init__(self, plugin_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.plugin_dock = plugin_dock
        self.communication = self.plugin_dock.communication
        self.user = None
        self.user_first_name = None
        self.user_last_name = None
        self.user_full_name = None
        self.threedi_api = None
        self.api_url = self.plugin_dock.plugin_settings.api_url
        self.client_id = None
        self.scope = None
        self.organisations = {}

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
        ssl_error_message = (
            "An error occurred. This specific error is probably caused by issues with an expired SSL "
            "certificate that has not properly been removed by your operating system. Please ask your system "
            "administrator to remove this expired SSL certificate manually. Instructions can be found here: "
            "https://docs.3di.live/f_problem_solving.html#connecting-to-the-3di-api"
        )
        try:
            self.fetch_msg.hide()
            self.done_msg.hide()
            self.log_pbar.setValue(25)
            username, personal_api_token = self.plugin_dock.plugin_settings.get_3di_auth()
            if not username or not personal_api_token:
                raise AuthorizationException(missing_personal_api_key_message)
            self.threedi_api = get_api_client_with_personal_api_token(personal_api_token, self.api_url)
            tc = ThreediCalls(self.threedi_api)
            user_profile = tc.fetch_current_user()
            self.user = user_profile.username
            self.user_first_name = user_profile.first_name
            self.user_last_name = user_profile.last_name
            self.user_full_name = f"{self.user_first_name} {self.user_last_name}"
            self.wait_widget.update()
            self.log_pbar.setValue(75)
            self.fetch_msg.show()
            self.organisations = {org.unique_id: org for org in tc.fetch_organisations()}
            self.done_msg.show()
            self.wait_widget.update()
            self.log_pbar.setValue(100)
            self.LOGGED_IN = True
            sleep(1)
            super().accept()
        except ApiException as e:
            self.close()
            if e.status == 404:
                error_msg = api_url_error_message
            else:
                error_msg = extract_error_message(e)
            if "SSLError" in error_msg:
                error_msg = f"{ssl_error_message}\n\n{error_msg}"
            self.communication.show_error(error_msg)
        except AuthorizationException:
            self.close()
            self.communication.show_warn("Personal API Key is not filled. Please set it in the Settings Dialog.")
            self.plugin_dock.plugin_settings.exec_()
        except Exception as e:
            if "THREEDI_API_HOST" in str(e):
                error_msg = api_url_error_message
            else:
                error_msg = f"Error: {e}"
            self.close()
            self.communication.show_error(error_msg)
