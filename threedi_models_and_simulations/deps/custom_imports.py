# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import os
import sys
from collections import OrderedDict
from subprocess import CalledProcessError, check_call

from ..utils import parse_version_number

REQUIRED_API_CLIENT_VERSION = "4.1.8"
REQUIRED_3DI_SCHEMA_VERSION = "0.300.21"
REQUIRED_3DI_MI_UTILS_VERSION = "0.1.8"
REQUIRED_GEOALCHEMY2_VERSION = "0.15.2"
REQUIRED_SQLALCHEMY_VERSION = "2.0.6"
REQUIRED_ALEMBIC_VERSION = "1.14.1"
REQUIRED_MAKO_VERSION = "1.3.9"


MAIN_DIR = os.path.dirname(os.path.abspath(__file__))
API_CLIENT_WHEEL = os.path.join(MAIN_DIR, f"threedi_api_client-{REQUIRED_API_CLIENT_VERSION}-py2.py3-none-any.whl")
MI_UTILS_WHEEL = os.path.join(MAIN_DIR, f"threedi_mi_utils-{REQUIRED_3DI_MI_UTILS_VERSION}-py3-none-any.whl")
GEOALCHEMY2_WHEEL = os.path.join(MAIN_DIR, f"GeoAlchemy2-{REQUIRED_GEOALCHEMY2_VERSION}-py3-none-any.whl")
SQLALCHEMY_WHEEL = os.path.join(MAIN_DIR, f"SQLAlchemy-{REQUIRED_SQLALCHEMY_VERSION}-py3-none-any.whl")
ALEMBIC_WHEEL = os.path.join(MAIN_DIR, f"alembic-{REQUIRED_ALEMBIC_VERSION}-py3-none-any.whl")
MAKO_WHEEL = os.path.join(MAIN_DIR, f"Mako-{REQUIRED_MAKO_VERSION}-py3-none-any.whl")


def patch_wheel_imports():
    """
    Function that tests if extra modules are installed.
    If modules are not available then it will add missing modules wheels to the Python path.
    """
    try:
        import pyqtgraph
    except ImportError:
        deps_path = os.path.join(MAIN_DIR, "pyqtgraph-0.13.7-py3-none-any.whl")
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
        import sqlalchemy
    except ImportError:
        deps_path = SQLALCHEMY_WHEEL
        sys.path.append(deps_path)

    try:
        import geoalchemy2
    except ImportError:
        deps_path = GEOALCHEMY2_WHEEL
        sys.path.append(deps_path)

    try:
        import alembic
    except ImportError:
        deps_path = ALEMBIC_WHEEL
        sys.path.append(deps_path)

    try:
        import threedi_schema
    except ImportError:
        # We no longer directly use the wheels as this caused issues with Alembic and temp files. That's
        # why we add the deps folder (containing threedi_schema) to the path.
        sys.path.append(MAIN_DIR)

    try:
        import openapi_client
        import threedi_api_client
    except ImportError:
        deps_path = API_CLIENT_WHEEL
        sys.path.append(deps_path)

    try:
        import threedi_mi_utils
    except ImportError:
        deps_path = MI_UTILS_WHEEL
        sys.path.append(deps_path)

    try:
        import mako
    except ImportError:
        deps_path = MAKO_WHEEL
        sys.path.append(deps_path)


def api_client_version_matches(exact_match=False):
    """Check if installed threedi_api_client version matches minimum required version."""
    import openapi_client
    import threedi_api_client

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


def schema_version_matches(exact_match=False):
    """Check if installed threedi_schema version matches minimum required version."""
    import threedi_schema

    available_threedi_schema_version = parse_version_number(threedi_schema.__version__)
    minimum_required_version = parse_version_number(REQUIRED_3DI_SCHEMA_VERSION)
    if exact_match:
        versions_matches = available_threedi_schema_version == minimum_required_version
    else:
        versions_matches = available_threedi_schema_version >= minimum_required_version
    return versions_matches, available_threedi_schema_version


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
