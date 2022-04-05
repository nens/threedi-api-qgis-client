# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2022 by Lutra Consulting for 3Di Water Management
import logging
import os
import re
import base64
import hashlib
import requests
from mechanize import Browser
from functools import wraps
from time import sleep
from qgis.PyQt import uic
from threedi_api_client.openapi import ApiException
from ..api_calls.threedi_calls import get_api_client, get_api_client_with_tokens, ThreediCalls
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


class AuthorizationHandler:
    """Class for handling OAuth2 + PKCE authorization."""

    AUTHORIZATION_ENDPOINT = "https://auth.lizard.net/oauth2/authorize"
    TOKEN_ENDPOINT = "https://auth.lizard.net/oauth2/token"
    REDIRECT_URI = "https://api.staging.3di.live/static/drf-yasg/swagger-ui-dist/oauth2-redirect.html"
    CLIENT_ID = "73d21iv9pu333mjqpbguipa7pi"
    SCOPE = "staging.3di.live/*:readwrite"
    STATE = "fooobarbaz"
    RESPONSE_TYPE = "code"
    CODE_CHALLENGE_METHOD = "S256"
    GRANT_TYPE = "authorization_code"

    def authorize(self, username, password):
        """Authorize user with OAuth2 + PKCE method to obtain an access and refresh tokens."""
        code_verifier, code_challenge = self._generate_pkce()
        authorization_code = self._get_authorization_code(username, password, code_challenge)
        access_token, refresh_token = self._get_tokens(authorization_code, code_verifier)
        return access_token, refresh_token

    @staticmethod
    def _generate_pkce():
        """Generate Proof Key for Code Exchange (PKCE)."""
        code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8")
        code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)
        code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8")
        code_challenge = code_challenge.replace("=", "")
        code_verifier = code_verifier
        code_challenge = code_challenge
        return code_verifier, code_challenge

    def _get_authorization_code(self, username, password, code_challenge):
        """Get an authorization code required to fetch the tokens."""
        authorization_response = requests.get(
            url=self.AUTHORIZATION_ENDPOINT,
            params={
                "response_type": self.RESPONSE_TYPE,
                "client_id": self.CLIENT_ID,
                "scope": self.SCOPE,
                "redirect_uri": self.REDIRECT_URI,
                "state": self.STATE,
                "code_challenge": code_challenge,
                "code_challenge_method": self.CODE_CHALLENGE_METHOD,
            },
            allow_redirects=False,
        )
        authorization_response.raise_for_status()
        log_in_url = authorization_response.headers["Location"]
        browser = Browser()
        browser.set_handle_robots(False)
        browser.open(log_in_url)
        browser.select_form(nr=1)
        browser.form["username"] = username
        browser.form["password"] = password
        log_in_response = browser.submit()
        redirect_url = log_in_response.geturl()
        params_search_results = re.search(r"code=(?P<code>[^&]+)&state=(?P<state>[^&]+)", redirect_url)
        params = params_search_results.groupdict()
        authorization_code = params["code"]
        state = params["state"]
        assert state == self.STATE
        return authorization_code

    def _get_tokens(self, authorization_code, code_verifier):
        """Get an access and refresh tokens from the dedicated endpoint."""
        tokens_response = requests.post(
            url=self.TOKEN_ENDPOINT,
            data={
                "grant_type": self.GRANT_TYPE,
                "client_id": self.CLIENT_ID,
                "redirect_uri": self.REDIRECT_URI,
                "code": authorization_code,
                "code_verifier": code_verifier,
            },
            allow_redirects=False,
        )
        tokens_response.raise_for_status()
        result = tokens_response.json()
        access_token, refresh_token = result["access_token"], result["refresh_token"]
        return access_token, refresh_token


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
        username = self.le_user.text()
        password = self.le_pass.text()
        api_url = self.plugin_dock.plugin_settings.api_url
        api_url_error_message = (
            f"Error: Invalid Base API URL '{api_url}'. "
            f"The 3Di API expects that the version is not included. "
            f"Please change the Base API URL in the 3Di Models and Simulations plugin settings."
        )
        try:
            self.show_wait_widget()
            self.fetch_msg.hide()
            self.done_msg.hide()
            self.le_user.setText("")
            self.le_pass.setText("")
            self.log_pbar.setValue(25)
            authorization_handler = AuthorizationHandler()
            access_token, refresh_token = authorization_handler.authorize(username, password)
            self.threedi_api = get_api_client_with_tokens(username, access_token, refresh_token, api_url)
            tc = ThreediCalls(self.threedi_api)
            user_profile = tc.fetch_current_user()
            self.user = username
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
