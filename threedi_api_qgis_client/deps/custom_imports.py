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
        import threedi_api_client
        import openapi_client
    except ImportError:
        deps_path = os.path.join(main_dir, "threedi_api_client-3.0b10-py2.py3-none-any.whl")
        sys.path.append(deps_path)
