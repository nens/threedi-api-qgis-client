import os
from qgis.PyQt import uic
from .upload_wizard import UploadWizard
from ..ui_utils import get_filepath

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_log, basecls_log = uic.loadUiType(os.path.join(base_dir, "ui", "upload_status.ui"))


class UploadDialog(uicls_log, basecls_log):
    """Upload dialog."""

    def __init__(self, parent_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.parent_dock = parent_dock
        self.communication = self.parent_dock.communication
        self.upload_wizard = None
        self.schematisation_model = None
        self.pb_new_upload.clicked.connect(self.upload_new_model)
        self.adjustSize()

    def upload_new_model(self):
        self.schematisation_model = get_filepath(None, extension_filter="Spatialite Files (*.sqlite *.SQLITE)")
        if not self.schematisation_model:
            return
        self.upload_wizard = UploadWizard(self.parent_dock)
        self.upload_wizard.exec_()
