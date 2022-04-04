# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2022 by Lutra Consulting for 3Di Water Management
import os
import sys
from subprocess import check_call, CalledProcessError


REQUIRED_API_CLIENT_VERSION = "4.0.1.dev0"
MAIN_DIR = os.path.dirname(os.path.abspath(__file__))


def patch_wheel_imports():
    """
    Function that tests if extra modules are installed.
    If modules are not available then it will add missing modules wheels to the Python path.
    """
    try:
        import pyqtgraph
    except ImportError:
        deps_path = os.path.join(MAIN_DIR, "pyqtgraph-0.11.1-py2.py3-none-any.whl")
        sys.path.append(deps_path)

    try:
        import dateutil
    except ImportError:
        deps_path = os.path.join(MAIN_DIR, "python_dateutil-2.8.1-py2.py3-none-any.whl")
        sys.path.append(deps_path)

    try:
        import urllib3
    except ImportError:
        deps_path = os.path.join(MAIN_DIR, "urllib3-1.25.8-py2.py3-none-any.whl")
        sys.path.append(deps_path)

    try:
        import six
    except ImportError:
        deps_path = os.path.join(MAIN_DIR, "six-1.14.0-py2.py3-none-any.whl")
        sys.path.append(deps_path)

    try:
        import certifi
    except ImportError:
        deps_path = os.path.join(MAIN_DIR, "certifi-2019.11.28-py2.py3-none-any.whl")
        sys.path.append(deps_path)

    try:
        import jwt
    except ImportError:
        deps_path = os.path.join(MAIN_DIR, "PyJWT-1.7.1-py2.py3-none-any.whl")
        sys.path.append(deps_path)

    try:
        import requests
    except ImportError:
        deps_path = os.path.join(MAIN_DIR, "requests-2.23.0-py2.py3-none-any.whl")
        sys.path.append(deps_path)

    try:
        import mechanize
    except ImportError:
        deps_path = os.path.join(MAIN_DIR, "mechanize-0.4.7-py2.py3-none-any.whl")
        sys.path.append(deps_path)

    try:
        import threedi_api_client
        import openapi_client
    except ImportError:
        deps_path = os.path.join(MAIN_DIR, f"threedi_api_client-{REQUIRED_API_CLIENT_VERSION}-py2.py3-none-any.whl")
        sys.path.append(deps_path)


def api_client_version_matches():
    """Check if installed threedi_api_client version matches required version."""
    import threedi_api_client
    import openapi_client

    try:
        available_api_client_version = threedi_api_client.__version__
    except AttributeError:
        available_api_client_version = openapi_client.__version__
    versions_matches = available_api_client_version == REQUIRED_API_CLIENT_VERSION
    return versions_matches, available_api_client_version


def reinstall_required_api_client():
    """Reinstall threedi_api_client to version derived within a wheel."""
    flags = ["--upgrade", "--no-deps", "--force-reinstall"]
    package = os.path.join(MAIN_DIR, f"threedi_api_client-{REQUIRED_API_CLIENT_VERSION}-py2.py3-none-any.whl")
    package_reinstalled, feedback_message = False, None
    try:
        check_call(["python", "-m", "pip", "install", *flags, package], shell=True)
        package_reinstalled = True
    except CalledProcessError as e:
        feedback_message = e.output
    return package_reinstalled, feedback_message
