# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2022 by Lutra Consulting for 3Di Water Management
import os
import sys
from collections import OrderedDict
from subprocess import check_call, CalledProcessError
from ..utils import parse_version_number

REQUIRED_API_CLIENT_VERSION = "4.0.1.dev0"
REQUIRED_MODEL_CHECKER_VERSION = "0.27.1"
MAIN_DIR = os.path.dirname(os.path.abspath(__file__))
API_CLIENT_WHEEL = os.path.join(MAIN_DIR, f"threedi_api_client-{REQUIRED_API_CLIENT_VERSION}-py2.py3-none-any.whl")
MODEL_CHECKER_WHEEL = os.path.join(
    MAIN_DIR, f"threedi_modelchecker-{REQUIRED_MODEL_CHECKER_VERSION}-py2.py3-none-any.whl"
)


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
        import threedi_modelchecker
    except ImportError:
        deps_path = MODEL_CHECKER_WHEEL
        sys.path.append(deps_path)

    try:
        import threedi_api_client
        import openapi_client
    except ImportError:
        deps_path = API_CLIENT_WHEEL
        sys.path.append(deps_path)


def api_client_version_matches(exact_match=False):
    """Check if installed threedi_api_client version matches minimum required version."""
    import threedi_api_client
    import openapi_client

    try:
        available_api_client_version = parse_version_number(threedi_api_client.__version__)
    except AttributeError:
        available_api_client_version = parse_version_number(openapi_client.__version__)
    minimum_required_version = parse_version_number(REQUIRED_API_CLIENT_VERSION)
    if exact_match:
        versions_matches = available_api_client_version == minimum_required_version
    else:
        versions_matches = available_api_client_version >= minimum_required_version
    return versions_matches, available_api_client_version


def model_checker_version_matches(exact_match=False):
    """Check if installed threedi_modelchecker version matches minimum required version."""
    import threedi_modelchecker

    available_threedi_modelchecker_version = parse_version_number(threedi_modelchecker.__version__)
    minimum_required_version = parse_version_number(REQUIRED_MODEL_CHECKER_VERSION)
    if exact_match:
        versions_matches = available_threedi_modelchecker_version == minimum_required_version
    else:
        versions_matches = available_threedi_modelchecker_version >= minimum_required_version
    return versions_matches, available_threedi_modelchecker_version


def reinstall_packages_from_wheels(*wheel_filepaths):
    """Reinstall wheel packages."""
    flags = ["--upgrade", "--no-deps", "--force-reinstall"]
    reinstall_results = OrderedDict()
    for package in wheel_filepaths:
        try:
            check_call(["python", "-m", "pip", "install", *flags, package], shell=True)
            reinstall_results[package] = {"success": True, "error": ""}
        except CalledProcessError as e:
            feedback_message = e.output
            reinstall_results[package] = {"success": False, "error": feedback_message}
    return reinstall_results
