import os
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem
from threedi_api_client.files import upload_file
from .upload_wizard import UploadWizard
from ..ui_utils import get_filepath
from ..api_calls.threedi_calls import ThreediCalls

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_log, basecls_log = uic.loadUiType(os.path.join(base_dir, "ui", "upload_status.ui"))


class UploadDialog(uicls_log, basecls_log):
    """Upload dialog."""

    def __init__(self, parent_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.parent_dock = parent_dock
        self.threedi_api = self.parent_dock.threedi_api
        self.tc = ThreediCalls(self.parent_dock.threedi_api)
        self.communication = self.parent_dock.communication
        self.upload_wizard = None
        self.schematization_id = 4
        self.schematisation_model = None
        self.pb_new_upload.clicked.connect(self.upload_new_model)
        self.tv_model = None
        self.setup_view_model()
        self.adjustSize()

    def setup_view_model(self):
        """Setting up model and columns for TreeView."""
        self.tv_model = QStandardItemModel(0, 3)
        self.tv_model.setHorizontalHeaderLabels(["Schematisation name", "Commit message"])
        self.tv_uploads.setModel(self.tv_model)

    def add_upload_to_model(self, new_upload):
        schema_name_item = QStandardItem(f"{new_upload['schematisation']}")
        commit_msg_item = QStandardItem(f"{new_upload['commit_message']}")
        self.tv_model.appendRow([schema_name_item, commit_msg_item])

    def upload_new_model(self):
        self.schematisation_model = get_filepath(None, extension_filter="Spatialite Files (*.sqlite *.SQLITE)")
        if not self.schematisation_model:
            return

        schematisation_name = self.tc.fetch_schematisation(self.schematization_id).name
        latest_rev = self.tc.fetch_schematisation_latest_revision(self.schematization_id).number
        self.upload_wizard = UploadWizard(self.parent_dock, schematisation_name, latest_rev)
        self.upload_wizard.exec_()
        new_upload = self.upload_wizard.new_upload
        if new_upload is None:
            return
        self.add_upload_to_model(new_upload)
        self.pbar_create_revision.setValue(0)
        self.pbar_upload_spatialite.setValue(0)
        self.pbar_upload_raster.setValue(0)
        self.pbar_commit.setValue(0)
        self.pbar_revision_validity.setValue(0)
        self.pbar_compute_grid.setValue(0)
        self.pbar_make_model.setValue(0)
        self.pbar_create_template.setValue(0)
        new_rev = self.tc.create_schematisation_revision(self.schematization_id)
        self.pbar_create_revision.setValue(100)
        new_rev_id = new_rev.id
        self.tc.delete_schematisation_revision_sqlite(self.schematization_id, new_rev_id)
        sqlite_file = os.path.basename(self.schematisation_model)
        upload = self.tc.upload_schematisation_revision_sqlite(self.schematization_id, new_rev_id, sqlite_file)
        upload_file(upload.put_url, self.schematisation_model, 1024 ** 2, callback_func=self.monitor_upload_progress)
        self.pbar_upload_spatialite.setValue(100)
        self.pbar_upload_raster.setValue(100)
        self.tc.commit_schematisation_revision(self.schematization_id, new_rev_id, commit_message=new_upload["commit_message"])
        self.pbar_commit.setValue(100)
        self.pbar_revision_validity.setValue(100)
        self.pbar_compute_grid.setValue(100)
        self.tc.create_schematisation_revision_3di_model(self.schematization_id, new_rev_id)
        self.pbar_make_model.setValue(100)
        self.pbar_create_template.setValue(100)

    def monitor_upload_progress(self, size, total_size):
        self.pbar_upload_spatialite.setValue(size / total_size * 100)
