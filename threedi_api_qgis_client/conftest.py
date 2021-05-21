# Code that needs to be executed before running the pytest tests.
from threedi_api_qgis_client.deps import custom_imports

custom_imports.patch_wheel_imports()
