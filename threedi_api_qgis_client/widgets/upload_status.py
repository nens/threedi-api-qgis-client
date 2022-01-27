import os
from collections import defaultdict, OrderedDict
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, QThreadPool, QItemSelectionModel
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem
from .upload_wizard import UploadWizard
from ..workers import UploadProgressWorker
from ..api_calls.threedi_calls import ThreediCalls
from ..communication import ListViewLogger


base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_log, basecls_log = uic.loadUiType(os.path.join(base_dir, "ui", "upload_status.ui"))


class UploadStatus(uicls_log, basecls_log):
    """Upload status dialog."""

    def __init__(self, plugin_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.plugin_dock = plugin_dock
        self.threedi_api = self.plugin_dock.threedi_api
        self.tc = ThreediCalls(self.plugin_dock.threedi_api)
        self.communication = self.plugin_dock.communication
        self.feedback_logger = ListViewLogger(self.lv_upload_feedback)
        self.upload_thread_pool = QThreadPool()
        self.ended_tasks = OrderedDict()
        self.upload_progresses = defaultdict(lambda: ("NO TASK", 0.0, 0.0))
        self.current_upload_row = 0
        self.schematisation = None
        self.schematisation_sqlite = None
        self.schematisation_id = None
        self.schematisation = None
        self.pb_new_upload.clicked.connect(self.upload_new_model)
        self.tv_model = None
        self.setup_view_model()
        self.adjustSize()

    @property
    def current_local_schematisation(self):
        """Return currently loaded local schematisation."""
        return self.plugin_dock.current_local_schematisation

    def setup_view_model(self):
        """Setting up model and columns for TreeView."""
        nr_of_columns = 4
        self.tv_model = QStandardItemModel(0, nr_of_columns - 1)
        self.tv_model.setHorizontalHeaderLabels(["Schematisation name", "Revision", "Commit message", "Status"])
        self.tv_uploads.setModel(self.tv_model)
        self.tv_uploads.selectionModel().selectionChanged.connect(self.change_upload_context)
        for i in range(nr_of_columns):
            self.tv_uploads.resizeColumnToContents(i)

    def change_upload_context(self):
        """Updating progress bars based on upload selection change."""
        selected_indexes = self.tv_uploads.selectedIndexes()
        if selected_indexes:
            current_index = selected_indexes[0]
            current_row = current_index.row()
            self.current_upload_row = current_row + 1
            self.on_update_upload_progress(self.current_upload_row, *self.upload_progresses[self.current_upload_row])
            self.feedback_logger.clear()
            try:
                for msg, success in self.ended_tasks[self.current_upload_row]:
                    if success:
                        self.feedback_logger.log_info(msg)
                    else:
                        self.feedback_logger.log_error(msg)
            except KeyError:
                pass

    def add_upload_to_model(self, upload_specification):
        """Initializing a new upload."""
        create_revision = upload_specification["create_revision"]
        schematisation = upload_specification["schematisation"]
        schema_name_item = QStandardItem(f"{schematisation.name}")
        revision = upload_specification["latest_revision"]
        revision_number = revision.number + 1 if create_revision is True else revision.number
        revision_item = QStandardItem(f"{revision_number}")
        commit_msg_item = QStandardItem(f"{upload_specification['commit_message']}")
        status_item = QStandardItem("In progress")
        self.tv_model.appendRow([schema_name_item, revision_item, commit_msg_item, status_item])
        upload_row_number = self.tv_model.rowCount()
        upload_row_idx = self.tv_model.index(upload_row_number - 1, 0)
        self.tv_uploads.selectionModel().setCurrentIndex(upload_row_idx, QItemSelectionModel.ClearAndSelect)
        worker = UploadProgressWorker(self.threedi_api, upload_specification, upload_row_number)
        worker.signals.upload_progress.connect(self.on_update_upload_progress)
        worker.signals.thread_finished.connect(self.on_upload_finished_success)
        worker.signals.upload_failed.connect(self.on_upload_failed)
        self.upload_thread_pool.start(worker)

    def upload_new_model(self):
        """Initializing new upload wizard."""
        self.schematisation_sqlite = self.current_local_schematisation.sqlite
        self.schematisation_id = self.current_local_schematisation.id
        self.schematisation = self.tc.fetch_schematisation(self.schematisation_id)
        if not self.schematisation_sqlite:
            return
        current_wip_revision = self.current_local_schematisation.wip_revision
        latest_revision = (
            self.tc.fetch_schematisation_latest_revision(self.schematisation_id)
            if current_wip_revision.number > 0
            else None
        )
        latest_revision_number = latest_revision.number if latest_revision else 0
        if latest_revision_number != current_wip_revision.number:
            question = f"WIP revision number different than latest online revision ({latest_revision_number})"
            answer = self.communication.custom_ask(self, "Pick action", question, "Upload anyway?", "Cancel")
            if answer == "Cancel":
                return
        upload_wizard_dialog = UploadWizard(self.plugin_dock, self)
        upload_wizard_dialog.exec_()
        new_upload = upload_wizard_dialog.new_upload
        if not new_upload:
            return
        self.add_upload_to_model(new_upload)
        self.current_local_schematisation.update_wip_revision(latest_revision_number + 1)
        self.plugin_dock.update_schematisation_view()

    def on_update_upload_progress(self, upload_row_number, task_name, task_progress, total_progress):
        """Handling actions on upload progress update."""
        self.upload_progresses[upload_row_number] = (task_name, task_progress, total_progress)
        if self.current_upload_row == upload_row_number:
            self.lbl_current_task.setText(task_name)
            self.pbar_current_task.setValue(task_progress)
            self.pbar_total_upload.setValue(total_progress)
            if task_progress == 100.0 and task_name != "DONE":
                success = True
                enriched_success_message = f"{task_name} ==> done"
                ended_task_row = (enriched_success_message, success)
                if upload_row_number not in self.ended_tasks:
                    self.ended_tasks[upload_row_number] = [ended_task_row]
                else:
                    upload_ended_tasks = self.ended_tasks[upload_row_number]
                    if ended_task_row not in upload_ended_tasks:
                        upload_ended_tasks.append(ended_task_row)
                    else:
                        return
                self.feedback_logger.log_info(enriched_success_message)

    def on_upload_finished_success(self, upload_row_number, msg):
        """Handling action on upload success."""
        item = self.tv_model.item(upload_row_number - 1, 3)
        item.setText("Success")
        self.plugin_dock.communication.bar_info(msg, log_text_color=Qt.darkGreen)

    def on_upload_failed(self, upload_row_number, error_message):
        """Handling action on upload failure."""
        item = self.tv_model.item(upload_row_number - 1, 3)
        item.setText("Failure")
        self.plugin_dock.communication.bar_error(error_message, log_text_color=Qt.red)
        success = False
        failed_task_name = self.upload_progresses[self.current_upload_row][0]
        enriched_error_message = f"{failed_task_name} ==> failed\n{error_message}"
        failed_task_row = (enriched_error_message, success)
        if upload_row_number not in self.ended_tasks:
            self.ended_tasks[upload_row_number] = [failed_task_row]
        else:
            self.ended_tasks[upload_row_number].append(failed_task_row)
        self.feedback_logger.log_error(enriched_error_message)
