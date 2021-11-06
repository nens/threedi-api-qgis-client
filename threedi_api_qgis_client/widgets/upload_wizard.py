# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import os
from enum import Enum
from collections import OrderedDict, defaultdict
from qgis.PyQt.QtSvg import QSvgWidget
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QSettings, QSize
from qgis.PyQt.QtWidgets import (
    QWizardPage,
    QWizard,
    QWidget,
    QGridLayout,
    QSizePolicy,
    QLabel,
    QPushButton,
    QLineEdit,
)
from ..utils import is_file_checksum_equal, sqlite_layer


base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_start_page, basecls_start_page = uic.loadUiType(os.path.join(base_dir, "ui", "upload_wizard", "page_start.ui"))
uicls_check_page, basecls_check_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "upload_wizard", "page_check_model.ui")
)
uicls_files_page, basecls_files_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "upload_wizard", "page_select_files.ui")
)


class UploadFileState(Enum):
    NO_CHANGES_DETECTED = "NO CHANGES DETECTED"
    CHANGES_DETECTED = "CHANGES DETECTED"
    NEW = "NEW"
    DELETED_LOCALLY = "DELETED LOCALLY"
    INVALID_REFERENCE = "INVALID REFERENCE!"


class UploadFileType(Enum):
    DB = "DB"
    RASTER = "RASTER"


class StartWidget(uicls_start_page, basecls_start_page):
    """Widget for the Start page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        # set_widget_background_color(self)


class CheckModelWidget(uicls_check_page, basecls_check_page):
    """Widget for the Check Model page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        # set_widget_background_color(self)


class SelectFilesWidget(uicls_files_page, basecls_files_page):
    """Widget for the Select Files page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.latest_revision = self.parent_page.parent_wizard.latest_revision
        self.schematisation = self.parent_page.parent_wizard.upload_dialog.schematisation
        self.schematisation_sqlite = self.parent_page.parent_wizard.upload_dialog.schematisation_sqlite
        self.tc = self.parent_page.parent_wizard.tc
        self.detected_files = self.check_files_states()
        self.initialize_widgets()
        # set_widget_background_color(self)

    @property
    def general_files(self):
        files_info = OrderedDict((("spatialite", "Spatialite"),))
        return files_info

    @property
    def terrain_model_files(self):
        files_info = OrderedDict(
            (
                ("dem_file", "Digital Elevation Model"),
                ("frict_coef_file", "Friction coefficient"),
                ("initial_groundwater_level_file", "Initial groundwater level"),
                ("initial_waterlevel_file", "Initial waterlevel"),
                ("interception_file", "Interception"),
            )
        )
        return files_info

    @property
    def simple_infiltration_files(self):
        files_info = OrderedDict(
            (
                ("infiltration_rate_file", "Infiltration rate"),
                ("max_infiltration_capacity_file", "Max infiltration capacity"),
            )
        )
        return files_info

    @property
    def groundwater_files(self):
        files_info = OrderedDict(
            (
                ("equilibrium_infiltration_rate_file", "Equilibrium infiltration rate"),
                ("groundwater_hydro_connectivity_file", "Groundwater hydro connectivity"),
                ("groundwater_impervious_layer_level_file", "Groundwater impervious layer level"),
                ("infiltration_decay_period_file", "Infiltration decay period"),
                ("initial_infiltration_rate_file", "Initial infiltration rate"),
                ("leakage_file", "Leakage"),
                ("phreatic_storage_capacity_file", "Phreatic storage capacity"),
            )
        )
        return files_info

    @property
    def interflow_files(self):
        files_info = OrderedDict(
            (
                ("hydraulic_conductivity_file", "Hydraulic conductivity"),
                ("porosity_file", "Porosity"),
            )
        )
        return files_info

    @property
    def files_reference_tables(self):
        files_ref_tables = OrderedDict(
            (
                ("v2_global_settings", self.terrain_model_files),
                ("v2_simple_infiltration", self.simple_infiltration_files),
                ("v2_groundwater", self.groundwater_files),
                ("v2_interflow", self.interflow_files),
            )
        )
        return files_ref_tables

    def check_files_states(self):
        files_states = OrderedDict()
        remote_rasters = self.tc.fetch_schematisation_revision_rasters(self.schematisation.id, self.latest_revision.id)
        remote_rasters_by_type = {raster.type: raster for raster in remote_rasters}
        if "dem_raw_file" in remote_rasters_by_type:
            remote_rasters_by_type["dem_file"] = remote_rasters_by_type["dem_raw_file"]
            del remote_rasters_by_type["dem_raw_file"]
        sqlite_localisation = os.path.dirname(self.schematisation_sqlite)
        if self.latest_revision.sqlite:
            remote_sqlite = self.tc.download_schematisation_revision_sqlite(
                self.schematisation.id, self.latest_revision.id
            )
            files_matching = is_file_checksum_equal(self.schematisation_sqlite, remote_sqlite.etag)
            status = UploadFileState.NO_CHANGES_DETECTED if files_matching else UploadFileState.CHANGES_DETECTED
        else:
            status = UploadFileState.NEW
        files_states["spatialite"] = {
            "status": status,
            "filepath": self.schematisation_sqlite,
            "type": UploadFileType.DB,
            "remote_id": None,
        }

        for sqlite_table, files_fields in self.files_reference_tables.items():
            sqlite_table_lyr = sqlite_layer(self.schematisation_sqlite, sqlite_table, geom_column=None)
            try:
                first_feat = next(sqlite_table_lyr.getFeatures())
            except StopIteration:
                continue
            for file_field in files_fields:
                file_relative_path = first_feat[file_field]
                remote_raster = remote_rasters_by_type.get(file_field)
                if not file_relative_path and not remote_raster:
                    continue
                filepath = os.path.join(sqlite_localisation, file_relative_path) if file_relative_path else None
                raster_id = remote_raster.id if remote_rasters else None
                if filepath:
                    if os.path.exists(filepath):
                        if remote_raster and remote_raster.file:
                            files_matching = is_file_checksum_equal(filepath, remote_raster.file.etag)
                            status = (
                                UploadFileState.NO_CHANGES_DETECTED
                                if files_matching
                                else UploadFileState.CHANGES_DETECTED
                            )
                        else:
                            status = UploadFileState.NEW
                    else:
                        status = UploadFileState.INVALID_REFERENCE
                else:
                    status = UploadFileState.DELETED_LOCALLY
                files_states[file_field] = {
                    "status": status,
                    "filepath": filepath,
                    "type": UploadFileType.RASTER,
                    "remote_id": raster_id,
                }
        return files_states

    def initialize_widgets(self):
        files_widgets = [
            self.widget_general,
            self.widget_terrain_model,
            self.widget_simple_infiltration,
            self.widget_groundwater,
            self.widget_interflow,
        ]
        files_info_collection = [
            self.general_files,
            self.terrain_model_files,
            self.simple_infiltration_files,
            self.groundwater_files,
            self.interflow_files,
        ]
        for widget in files_widgets:
            widget.hide()

        for widget, files_info in zip(files_widgets, files_info_collection):
            widget_layout = widget.layout()
            for i, (field_name, name) in enumerate(files_info.items(), start=1):
                try:
                    file_state = self.detected_files[field_name]
                except KeyError:
                    continue
                status = file_state["status"]
                widget.show()
                name_normalized = name.lower().replace(" ", "_")
                name_label = QLabel(name)
                name_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
                widget_layout.addWidget(name_label, i, 0)

                status_label = QLabel(status.value)
                status_label.setObjectName(f"{name_normalized}_status")
                status_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
                widget_layout.addWidget(status_label, i, 1)

                if status == UploadFileState.NO_CHANGES_DETECTED:
                    empty_label = QLabel()
                    widget_layout.addWidget(empty_label, i, 2)
                elif status == UploadFileState.INVALID_REFERENCE:
                    filepath_line_edit = QLineEdit()
                    filepath_line_edit.setObjectName(f"{name_normalized}_path")
                    filepath_line_edit.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

                    browse_pb = QPushButton("...")
                    browse_pb.setObjectName(f"{name_normalized}_browse")

                    update_ref_pb = QPushButton("Update reference")
                    update_ref_pb.setObjectName(f"{name_normalized}_update_reference")

                    invalid_ref_sublayout = QGridLayout()
                    filepath_sublayout = QGridLayout()
                    filepath_sublayout.addWidget(filepath_line_edit, 0, 0)
                    filepath_sublayout.addWidget(browse_pb, 0, 1)
                    invalid_ref_sublayout.addLayout(filepath_sublayout, 0, 0)
                    invalid_ref_sublayout.addWidget(update_ref_pb, 0, 1)

                    widget_layout.addLayout(invalid_ref_sublayout, i, 2)
                else:
                    no_action_pb_name = "Ignore"
                    if status == UploadFileState.DELETED_LOCALLY:
                        action_pb_name = "Delete online"
                    else:
                        action_pb_name = "Upload"
                    no_action_pb = QPushButton(no_action_pb_name)
                    no_action_pb.setObjectName(f"{name_normalized}_no_action")
                    no_action_pb.setCheckable(True)
                    no_action_pb.setAutoExclusive(True)

                    action_pb = QPushButton(action_pb_name)
                    action_pb.setObjectName(f"{name_normalized}_action")
                    action_pb.setCheckable(True)
                    action_pb.setAutoExclusive(True)
                    action_pb.setChecked(True)

                    actions_widget = QWidget()
                    actions_sublayout = QGridLayout()
                    actions_widget.setLayout(actions_sublayout)
                    actions_sublayout.addWidget(no_action_pb, 0, 0)
                    actions_sublayout.addWidget(action_pb, 0, 1)

                    widget_layout.addWidget(actions_widget, i, 2)


class StartPage(QWizardPage):
    """Upload start definition page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = StartWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget, 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class CheckModelPage(QWizardPage):
    """Upload Check Model definition page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = CheckModelWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget, 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class SelectFilesPage(QWizardPage):
    """Upload Select Files definition page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = SelectFilesWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget, 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class UploadWizard(QWizard):
    """New upload wizard."""

    def __init__(self, parent_dock, upload_dialog, parent=None):
        super().__init__(parent)
        self.settings = QSettings()
        self.setWizardStyle(QWizard.ClassicStyle)
        self.parent_dock = parent_dock
        self.upload_dialog = upload_dialog
        self.tc = self.upload_dialog.tc
        # TODO: Add handling of the first revision case
        self.latest_revision = self.tc.fetch_schematisation_latest_revision(self.upload_dialog.schematisation.id)
        self.start_page = StartPage(self)
        self.start_page.main_widget.lbl_schematisation.setText(self.upload_dialog.schematisation.name)
        self.start_page.main_widget.lbl_online_revision.setText(str(self.latest_revision.number))
        self.check_model_page = CheckModelPage(self)
        self.select_files_page = SelectFilesPage(self)
        self.addPage(self.start_page)
        self.addPage(self.check_model_page)
        self.addPage(self.select_files_page)

        self.setButtonText(QWizard.FinishButton, "Start upload")
        self.finish_btn = self.button(QWizard.FinishButton)
        self.finish_btn.clicked.connect(self.start_upload)
        self.cancel_btn = self.button(QWizard.CancelButton)
        self.cancel_btn.clicked.connect(self.cancel_wizard)
        self.new_upload = defaultdict(lambda: None)
        self.new_upload_statuses = None
        self.setWindowTitle("New upload")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.resize(self.settings.value("threedi/upload_wizard_size", QSize(800, 600)))

    def start_upload(self):
        self.new_upload.clear()
        self.new_upload["schematisation"] = self.upload_dialog.schematisation
        self.new_upload["commit_message"] = self.select_files_page.main_widget.te_upload_description.toPlainText()
        self.new_upload["latest_revision"] = self.latest_revision.number
        self.new_upload["sqlite_filepath"] = self.upload_dialog.schematisation_sqlite

    def cancel_wizard(self):
        """Handling canceling wizard action."""
        self.settings.setValue("threedi/upload_wizard_size", self.size())
        self.reject()
