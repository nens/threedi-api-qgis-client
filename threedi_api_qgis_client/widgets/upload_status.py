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

    UPLOAD_STEPS = (
        "CREATE NEW REVISION",
        "UPLOAD SPATIALITE",
        "UPLOAD INFILTRATION CAPACITY",
        "COMMIT REVISION",
        "CHECK REVISION VALIDITY",
        "CREATE COMPUTATIONAL GRID",
        "MAKE MODEL READY FOR SIMULATION",
        "CREATE SIMULATION TEMPLATE",
    )

    def __init__(self, parent_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.parent_dock = parent_dock
        self.threedi_api = self.parent_dock.threedi_api
        self.tc = ThreediCalls(self.parent_dock.threedi_api)
        self.communication = self.parent_dock.communication
        self.upload_wizard = None
        self.schematisation_sqlite = None
        self.schematisation = None
        try:
            schematisation_id = int(self.parent_dock.label_schematisation_id.text())
            self.schematisation = self.tc.fetch_schematisation(schematisation_id)
        except ValueError:
            schematisation_name = self.parent_dock.label_db.text().rsplit(".ini")[0]
            self.schematisation = self.tc.fetch_schematisations(name=schematisation_name)[0]
        self.pb_new_upload.clicked.connect(self.upload_new_model)
        self.tv_model = None
        self.setup_view_model()
        self.adjustSize()

    def setup_view_model(self):
        """Setting up model and columns for TreeView."""
        self.tv_model = QStandardItemModel(0, 3)
        self.tv_model.setHorizontalHeaderLabels(["Schematisation name", "Owner", "Revision", "Commit message"])
        self.tv_uploads.setModel(self.tv_model)

    def add_upload_to_model(self, new_upload):
        schema_name_item = QStandardItem(f"{new_upload['schematisation']}")
        owner_item = QStandardItem(f"{new_upload['owner']}")
        revision_id = new_upload['latest_revision'] or 1
        revision_item = QStandardItem(f"{revision_id}")
        commit_msg_item = QStandardItem(f"{new_upload['commit_message']}")
        self.tv_model.appendRow([schema_name_item, owner_item, revision_item, commit_msg_item])

    def upload_new_model(self):
        self.schematisation_sqlite = get_filepath(None, extension_filter="Spatialite Files (*.sqlite *.SQLITE)")
        if not self.schematisation_sqlite:
            return

        self.upload_wizard = UploadWizard(self.parent_dock, self)
        self.upload_wizard.exec_()
        new_upload = self.upload_wizard.new_upload
        if new_upload is None:
            return
        self.add_upload_to_model(new_upload)
        self.update_upload_progress(0, task_max=0)
        self.lbl_current_task.setText("CREATE REVISION")
        revision = self.tc.create_schematisation_revision(self.schematisation.id)
        new_rev_id = revision.id
        commit_message = new_upload["commit_message"]
        self.update_upload_progress(10)
        self.lbl_current_task.setText("DELETE REVISION SQLITE IF EXIST")
        self.tc.delete_schematisation_revision_sqlite(self.schematisation.id, new_rev_id)
        self.update_upload_progress(20, task_max=100)
        self.lbl_current_task.setText("UPLOAD SPATIALITE")
        sqlite_file = os.path.basename(self.schematisation_sqlite)
        upload = self.tc.upload_schematisation_revision_sqlite(self.schematisation.id, new_rev_id, sqlite_file)
        upload_file(upload.put_url, self.schematisation_sqlite, 1024 ** 2, callback_func=self.monitor_upload_progress)
        self.update_upload_progress(80, task_max=0)
        self.lbl_current_task.setText("COMMIT REVISION")
        self.tc.commit_schematisation_revision(self.schematisation.id, new_rev_id, commit_message=commit_message)
        self.update_upload_progress(100, task_max=100)
        self.lbl_current_task.setText("DONE")

    def monitor_upload_progress(self, size, total_size):
        self.pbar_current_task.setValue(size / total_size * 100)

    def update_upload_progress(self, total_progress, task_max=None):
        if task_max is not None:
            self.pbar_current_task.setMaximum(task_max)
        self.pbar_total_upload.setValue(total_progress)
        self.pbar_current_task.setValue(0 if total_progress != 100 else 100)
