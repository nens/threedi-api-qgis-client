import os
import sys
try:
    import pyqtgraph as pg
except ImportError:
    main_dir = os.path.dirname(os.path.abspath(__file__))
    deps_path = os.path.join(main_dir, pyqtgraph-0.10.0-py3-none-any.whl")
    sys.path.append(deps_path)
    import pyqtgraph as pg

try:
    from dateutil.relativedelta import relativedelta
except ImportError:
    main_dir = os.path.dirname(os.path.abspath(__file__))
    deps_path = os.path.join(main_dir, "python_dateutil-2.8.1-py2.py3-none-any.whl")
    sys.path.append(deps_path)
    from dateutil.relativedelta import relativedelta
