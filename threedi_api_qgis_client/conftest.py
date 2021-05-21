from typing_extensions import ParamSpecKwargs


try:
    # Code that needs to be executed before running the pytest tests within docker.
    from threedi_api_qgis_client.deps import custom_imports

    custom_imports.patch_wheel_imports()
    print("Loaded wheels included in the deps/ folder")
except:
    # The travis tests have their own qt-less setup, which fails when trying
    # to install pyqtgraph.
    pass
