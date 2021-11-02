import os
from collections import defaultdict
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, QThreadPool
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem
from .upload_wizard import UploadWizard
from ..workers import UploadProgressWorker
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
        self.upload_thread_pool = QThreadPool()
        self.upload_progresses = defaultdict(lambda: ("NO TASK", 0.0, 0.0))
        self.current_upload_row = 0
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
        self.tv_model = QStandardItemModel(0, 4)
        self.tv_model.setHorizontalHeaderLabels(["Schematisation name", "Owner", "Revision", "Commit message"])
        self.tv_uploads.setModel(self.tv_model)
        self.tv_uploads.selectionModel().selectionChanged.connect(self.change_upload_context)

    def change_upload_context(self):
        selected_indexes = self.tv_uploads.selectedIndexes()
        if selected_indexes:
            current_index = selected_indexes[0]
            current_row = current_index.row()
            self.current_upload_row = current_row + 1
            self.on_update_upload_progress(self.current_upload_row, *self.upload_progresses[self.current_upload_row])

    def add_upload_to_model(self, upload_specification):
        schematisation = upload_specification["schematisation"]
        schema_name_item = QStandardItem(f"{schematisation.name}")
        owner_item = QStandardItem(f"{schematisation.owner}")
        revision_id = upload_specification["latest_revision"] or 1
        revision_item = QStandardItem(f"{revision_id}")
        commit_msg_item = QStandardItem(f"{upload_specification['commit_message']}")
        self.tv_model.appendRow([schema_name_item, owner_item, revision_item, commit_msg_item])
        upload_row_idx = self.tv_model.rowCount()
        worker = UploadProgressWorker(self.threedi_api, upload_specification, upload_row_idx)
        worker.signals.upload_progress.connect(self.on_update_upload_progress)
        worker.signals.thread_finished.connect(self.on_upload_finished_success)
        worker.signals.upload_failed.connect(self.on_upload_failed)
        self.upload_thread_pool.start(worker)

    def upload_new_model(self):
        self.schematisation_sqlite = get_filepath(None, extension_filter="Spatialite Files (*.sqlite *.SQLITE)")
        if not self.schematisation_sqlite:
            return

        self.upload_wizard = UploadWizard(self.parent_dock, self)
        self.upload_wizard.exec_()
        new_upload = self.upload_wizard.new_upload
        if not new_upload:
            return
        self.add_upload_to_model(new_upload)

    def on_update_upload_progress(self, upload_row_index, task_name, task_progress, total_progress):
        self.upload_progresses[upload_row_index] = (task_name, task_progress, total_progress)
        if self.current_upload_row == upload_row_index:
            self.lbl_current_task.setText(task_name)
            self.pbar_current_task.setValue(task_progress)
            self.pbar_total_upload.setValue(total_progress)

    def on_upload_finished_success(self, msg):
        self.parent_dock.communication.bar_info(msg, log_text_color=Qt.darkGreen)

    def on_upload_failed(self, msg):
        self.parent_dock.communication.bar_error(msg, log_text_color=Qt.red)
