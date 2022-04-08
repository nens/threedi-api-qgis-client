# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2022 by Lutra Consulting for 3Di Water Management
import logging
import os
import re
import base64
import hashlib
import secrets
import requests
from functools import wraps
from time import sleep
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtCore import QObject, QUrl, pyqtSignal
from PyQt5.QtNetwork import QHostAddress, QTcpServer
from threedi_api_client.openapi import ApiException
from ..api_calls.threedi_calls import get_api_client_with_tokens, ThreediCalls
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


class AuthorizationCodeInterceptor(QObject):
    """Authorization code interceptor class."""

    code_intercepted = pyqtSignal(str)
    code_interception_failed = pyqtSignal(Exception)

    def __init__(self, authorization_handler, host, port, state):
        super().__init__()
        self.authorization_handler = authorization_handler
        self.host = QHostAddress(host)
        self.port = port
        self.state = state
        self.tcp_server = None

    @staticmethod
    def is_listening_possible(host: str, port: int) -> bool:
        """Check if it is possible to listen to the given host and port."""
        tcp_server = QTcpServer()
        is_listening = tcp_server.listen(QHostAddress(host), port)
        if is_listening:
            tcp_server.close()
        return is_listening

    def start_listening(self):
        """Start listening for an incoming connections."""
        self.tcp_server = QTcpServer()
        if not self.tcp_server.listen(self.host, self.port):
            raise AuthorizationException(f"Can't listen port: '{self.port}'!")
        self.tcp_server.newConnection.connect(self.intercept_code)

    def stop_listening(self):
        """Stop listening for an incoming connections."""
        if self.tcp_server is not None and self.tcp_server.isListening():
            self.tcp_server.close()

    def intercept_code(self):
        """Intercept an authorization code from the incoming connection."""
        try:
            self.tcp_server.newConnection.disconnect(self.intercept_code)
            tcp_socket = self.tcp_server.nextPendingConnection()
            tcp_socket.waitForReadyRead()
            incoming_data = tcp_socket.readAll().data()
            incoming_data_str = str(incoming_data, "utf-8")
            params_search_results = re.search(r"code=(?P<code>[^&]+)&state=(?P<state>\S+)", incoming_data_str)
            params = params_search_results.groupdict()
            authorization_code = params["code"]
            state = params["state"]
            if self.state:
                assert state == self.state
            tcp_socket.disconnected.connect(tcp_socket.deleteLater)
            tcp_socket.disconnectFromHost()
            self.code_intercepted.emit(authorization_code)
        except Exception as error:
            self.code_interception_failed.emit(error)
        finally:
            self.stop_listening()


class AuthorizationHandler(QObject):
    """Class for handling OAuth2 + PKCE authorization."""

    tokens_acquired = pyqtSignal(str, str)

    ISSUER = "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_vPwXOnNbi"
    RESPONSE_TYPE = "code"
    CODE_CHALLENGE_METHOD = "S256"
    GRANT_TYPE = "authorization_code"

    def __init__(
        self,
        log_in_dialog,
        client_id,
        scope,
        redirect_host="http://localhost",
        redirect_port=62445,
        spare_redirect_port=62271,
    ):
        super().__init__()
        self.log_in_dialog = log_in_dialog
        self.client_id = client_id
        self.scope = scope
        self.redirect_host = redirect_host
        if AuthorizationCodeInterceptor.is_listening_possible(redirect_host, redirect_port):
            self.redirect_port = redirect_port
        else:
            self.redirect_port = spare_redirect_port
        self.redirect_uri = f"{self.redirect_host}:{self.redirect_port}/"
        self.state = secrets.token_urlsafe(22)
        self.authorization_endpoint = None
        self.token_endpoint = None
        self.code_verifier = None
        self.code_challenge = None
        self.authorization_code_interceptor = AuthorizationCodeInterceptor(
            self, self.redirect_host, self.redirect_port, self.state
        )
        self.authorization_code_interceptor.code_intercepted.connect(self._acquire_tokens)
        self.authorization_code_interceptor.code_interception_failed.connect(self._interception_failure)

    def authorize(self):
        """Start authorization with OAuth2 + PKCE method to obtain an access and refresh tokens."""
        self._oauth2_autodiscovery()
        self._generate_pkce()
        self._initialize_authorization()

    def _interception_failure(self, error):
        """Re-raise an exception from the AuthorizationCodeInterceptor instance."""
        error_msg = f"Authorization code interception error: {error}"
        self.log_in_dialog.communication.show_error(error_msg)
        self.log_in_dialog.close()

    def _oauth2_autodiscovery(self):
        """Use autodiscovery to fetch server details."""
        response = requests.get(f"{self.ISSUER}/.well-known/openid-configuration")
        response.raise_for_status()
        server_config = response.json()
        self.authorization_endpoint = server_config["authorization_endpoint"]
        self.token_endpoint = server_config["token_endpoint"]
        return response.json()

    def _generate_pkce(self):
        """Generate Proof Key for Code Exchange (PKCE)."""
        code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8")
        code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)
        code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8")
        code_challenge = code_challenge.replace("=", "")
        code_verifier = code_verifier
        code_challenge = code_challenge
        self.code_verifier, self.code_challenge = code_verifier, code_challenge

    def _initialize_authorization(self):
        """Initialize an authorization process."""
        authorization_response = requests.get(
            url=self.authorization_endpoint,
            params={
                "response_type": self.RESPONSE_TYPE,
                "client_id": self.client_id,
                "scope": self.scope,
                "redirect_uri": self.redirect_uri,
                "state": self.state,
                "code_challenge": self.code_challenge,
                "code_challenge_method": self.CODE_CHALLENGE_METHOD,
            },
            allow_redirects=False,
        )
        authorization_response.raise_for_status()
        log_in_url = authorization_response.headers["Location"]
        self.authorization_code_interceptor.start_listening()
        QDesktopServices.openUrl(QUrl(log_in_url))

    def _acquire_tokens(self, authorization_code):
        """Get an access and refresh tokens from the dedicated endpoint."""
        try:
            tokens_response = requests.post(
                url=self.token_endpoint,
                data={
                    "grant_type": self.GRANT_TYPE,
                    "client_id": self.client_id,
                    "redirect_uri": self.redirect_uri,
                    "code": authorization_code,
                    "code_verifier": self.code_verifier,
                },
                allow_redirects=False,
            )
            tokens_response.raise_for_status()
            result = tokens_response.json()
            access_token, refresh_token = result["access_token"], result["refresh_token"]
            self.tokens_acquired.emit(access_token, refresh_token)
        except Exception as e:
            error_msg = f"Error: {e}"
            self.log_in_dialog.communication.show_error(error_msg)
            self.log_in_dialog.close()


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
        authorization_variables = self.plugin_dock.plugin_settings.authorization_variables_map[self.api_url]
        if authorization_variables:
            self.client_id = authorization_variables["client_id"]
            self.scope = authorization_variables["scope"]
        self.authorization_handler = AuthorizationHandler(self, self.client_id, self.scope)
        self.pb_log_in.clicked.connect(self.start_authorization)
        self.pb_cancel.clicked.connect(self.reject)
        self.authorization_handler.tokens_acquired.connect(self.log_in_threedi)
        self.resize(500, 250)
        self.show_log_widget()

    def start_authorization(self):
        """Disable log-in button and initialize authorization process."""
        self.pb_log_in.setDisabled(True)
        try:
            self.authorization_handler.authorize()
        except Exception as e:
            error_msg = f"Error: {e}"
            self.close()
            self.communication.show_error(error_msg)

    def show_log_widget(self):
        """Showing logging form widget."""
        self.log_in_widget.show()
        self.setWindowTitle("Log in")

    def show_wait_widget(self):
        """Showing widget with logging progress."""
        self.log_in_widget.hide()
        self.wait_widget.show()

    def log_in_threedi(self, access_token, refresh_token):
        """Method which runs all logging widgets methods and setting up needed variables."""
        self.authorization_handler.tokens_acquired.disconnect(self.log_in_threedi)
        api_url_error_message = (
            f"Error: Invalid Base API URL '{self.api_url}'. "
            f"The 3Di API expects that the version is not included. "
            f"Please change the Base API URL in the 3Di Models and Simulations plugin settings."
        )
        try:
            self.show_wait_widget()
            self.fetch_msg.hide()
            self.done_msg.hide()
            self.log_pbar.setValue(25)
            self.threedi_api = get_api_client_with_tokens(self.api_url, access_token, refresh_token)
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
        self.authorization_handler.tokens_acquired.disconnect(self.log_in_threedi)
        self.authorization_handler.authorization_code_interceptor.stop_listening()
        super().reject()
