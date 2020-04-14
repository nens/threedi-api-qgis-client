# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
import sys


def patch_wheel_imports():
    """
    Function that tests if extra modules are installed.
    If modules are not available then it will add missing modules wheels to the Python path.
    """
    main_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        import pyqtgraph
    except ImportError:
        deps_path = os.path.join(main_dir, "pyqtgraph-0.10.0-py3-none-any.whl")
        sys.path.append(deps_path)

    try:
        import dateutil
    except ImportError:
        deps_path = os.path.join(main_dir, "python_dateutil-2.8.1-py2.py3-none-any.whl")
        sys.path.append(deps_path)

    try:
        import urllib3
    except ImportError:
        deps_path = os.path.join(main_dir, "urllib3-1.25.8-py2.py3-none-any.whl")
        sys.path.append(deps_path)

    try:
        import six
    except ImportError:
        deps_path = os.path.join(main_dir, "six-1.14.0-py2.py3-none-any.whl")
        sys.path.append(deps_path)

    try:
        import certifi
    except ImportError:
        deps_path = os.path.join(main_dir, "certifi-2019.11.28-py2.py3-none-any.whl")
        sys.path.append(deps_path)

    try:
        import jwt
    except ImportError:
        deps_path = os.path.join(main_dir, "PyJWT-1.7.1-py2.py3-none-any.whl")
        sys.path.append(deps_path)

    try:
        import threedi_api_client
        import openapi_client
    except ImportError:
        deps_path = os.path.join(main_dir, "threedi_api_client-3.0b16-py2.py3-none-any.whl")
        sys.path.append(deps_path)

    try:
        import requests
    except ImportError:
        deps_path = os.path.join(main_dir, "trequests-2.23.0-py2.py3-none-any.whl")
        sys.path.append(deps_path)
