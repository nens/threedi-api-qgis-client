# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import os
import shutil
from operator import attrgetter
from collections import OrderedDict, defaultdict
from functools import partial
from qgis.PyQt.QtSvg import QSvgWidget
from qgis.utils import plugins
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
from sqlalchemy.exc import OperationalError
from threedi_modelchecker.threedi_database import ThreediDatabase
from threedi_modelchecker.model_checks import ThreediModelChecker
from threedi_modelchecker import errors
from ..utils import is_file_checksum_equal, sqlite_layer, UploadFileType, UploadFileStatus
from ..ui_utils import get_filepath
from ..communication import CheckerCommunication


base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_start_page, basecls_start_page = uic.loadUiType(os.path.join(base_dir, "ui", "upload_wizard", "page_start.ui"))
uicls_check_page, basecls_check_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "upload_wizard", "page_check_model.ui")
)
uicls_files_page, basecls_files_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "upload_wizard", "page_select_files.ui")
)


class StartWidget(uicls_start_page, basecls_start_page):
    """Widget for the Start page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.schematisation_sqlite = self.parent_page.parent_wizard.schematisation_sqlite
        self.latest_revision = self.parent_page.parent_wizard.latest_revision
        self.lbl_online_commit_date.setText(str(self.latest_revision.commit_date or "") or "")
        self.lbl_online_commit_by.setText(self.latest_revision.commit_user or "")
        self.lbl_online_commit_msg.setText(self.latest_revision.commit_message or "")
        self.lbl_model_dir.setText(os.path.dirname(self.schematisation_sqlite))
        # set_widget_background_color(self)


class CheckModelWidget(uicls_check_page, basecls_check_page):
    """Widget for the Check Model page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.schematisation_sqlite = self.parent_page.parent_wizard.schematisation_sqlite
        self.checker_logger = CheckerCommunication(self.lv_check_result)
        self.pb_check_model.clicked.connect(self.check_schematisation)
        # set_widget_background_color(self)

    def check_schematisation(self):
        db_type = "spatialite"
        db_settings = {"db_path": self.schematisation_sqlite}
        threedi_db = ThreediDatabase(db_settings, db_type=db_type)
        try:
            model_checker = ThreediModelChecker(threedi_db)
            model_checker.db.check_connection()
        except OperationalError as exc:
            self.checker_logger.log_error("Failed to start a connection with the database.")
            self.checker_logger.log_error(
                "Something went wrong trying to connect to the database, please check"
                " the connection settings: %s" % exc.args[0]
            )
            return
        except errors.MigrationMissingError:
            self.checker_logger.log_error("The selected 3Di model does not have the latest migration")
            self.checker_logger.log_error(
                "The selected 3Di model does not have the latest migration, please "
                "migrate your model to the latest version. Download the latest "
                "version of the model here: <a href='https://3di.lizard.net/models/'>https://3di.lizard.net/models/</a>"
                # noqa
            )
            return
        except errors.MigrationTooHighError:
            self.checker_logger.log_error("The selected 3Di model has a higher migration than expected.")
            self.checker_logger.log_error(
                "The 3Di model has a higher migration than expected, do you have "
                "the latest version of ThreediToolbox?"
            )
            return
        except errors.MigrationNameError:
            self.checker_logger.log_error(
                "Unexpected migration name, but migration id is matching. "
                "We are gonna continue for now and hope for the best."
            )
            return
        session = model_checker.db.get_session()
        total_checks = len(model_checker.config.checks)
        self.pbar_check_spatialite.setMaximum(total_checks)
        self.pbar_check_spatialite.setValue(0)
        check_header = ["id", "table", "column", "value", "description", "type of check"]
        for i, check in enumerate(model_checker.checks(), start=1):
            model_errors = check.get_invalid(session)
            if model_errors:
                self.checker_logger.log_error(repr(check_header))
            for error_row in model_errors:
                self.checker_logger.log_error(
                    repr(
                        [
                            error_row.id,
                            check.table.name,
                            check.column.name,
                            getattr(error_row, check.column.name),
                            check.description(),
                            check,
                        ]
                    )
                )
            self.pbar_check_spatialite.setValue(i)
        self.checker_logger.log_info("Successfully finished running threedi-modelchecker")


class SelectFilesWidget(uicls_files_page, basecls_files_page):
    """Widget for the Select Files page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.latest_revision = self.parent_page.parent_wizard.latest_revision
        self.schematisation = self.parent_page.parent_wizard.schematisation
        self.schematisation_sqlite = self.parent_page.parent_wizard.schematisation_sqlite
        self.tc = self.parent_page.parent_wizard.tc
        self.detected_files = self.check_files_states()
        self.widgets_per_file = {}
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

    @property
    def file_table_mapping(self):
        table_mapping = {}
        for table_name, raster_files_references in self.files_reference_tables.items():
            for raster_type in raster_files_references.keys():
                table_mapping[raster_type] = table_name
        return table_mapping

    def check_files_states(self):
        """Check raster (and spatialite) files presence and compare local and remote data."""
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
            status = UploadFileStatus.NO_CHANGES_DETECTED if files_matching else UploadFileStatus.CHANGES_DETECTED
        else:
            status = UploadFileStatus.NEW
        files_states["spatialite"] = {
            "status": status,
            "filepath": self.schematisation_sqlite,
            "type": UploadFileType.DB,
            "remote_raster": None,
            "make_action": True,
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
                if filepath:
                    if os.path.exists(filepath):
                        if remote_raster and remote_raster.file:
                            files_matching = is_file_checksum_equal(filepath, remote_raster.file.etag)
                            status = (
                                UploadFileStatus.NO_CHANGES_DETECTED
                                if files_matching
                                else UploadFileStatus.CHANGES_DETECTED
                            )
                        else:
                            status = UploadFileStatus.NEW
                    else:
                        status = UploadFileStatus.INVALID_REFERENCE
                else:
                    status = UploadFileStatus.DELETED_LOCALLY
                files_states[file_field] = {
                    "status": status,
                    "filepath": filepath,
                    "type": UploadFileType.RASTER,
                    "remote_raster": remote_raster,
                    "make_action": True,
                }
        return files_states

    def initialize_widgets(self):
        """Dynamically set up widgets based on detected files."""
        self.widgets_per_file.clear()
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

        current_main_layout_row = 1
        for widget, files_info in zip(files_widgets, files_info_collection):
            widget_layout = widget.layout()
            for field_name, name in files_info.items():
                try:
                    file_state = self.detected_files[field_name]
                except KeyError:
                    continue
                status = file_state["status"]
                widget.show()
                name_label = QLabel(name)
                name_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
                widget_layout.addWidget(name_label, current_main_layout_row, 0)

                status_label = QLabel(status.value)
                status_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
                widget_layout.addWidget(status_label, current_main_layout_row, 1)

                empty_label = QLabel()
                widget_layout.addWidget(empty_label, current_main_layout_row, 2)

                no_action_pb_name = "Ignore"
                if status == UploadFileStatus.DELETED_LOCALLY:
                    action_pb_name = "Delete online"
                else:
                    action_pb_name = "Upload"
                # Add valid reference widgets
                all_actions_widget = QWidget()
                actions_sublayout = QGridLayout()
                all_actions_widget.setLayout(actions_sublayout)

                valid_ref_widget = QWidget()
                valid_ref_sublayout = QGridLayout()
                valid_ref_widget.setLayout(valid_ref_sublayout)
                no_action_pb = QPushButton(no_action_pb_name)
                no_action_pb.setCheckable(True)
                no_action_pb.setAutoExclusive(True)
                no_action_pb.clicked.connect(partial(self.toggle_action, field_name, False))

                action_pb = QPushButton(action_pb_name)
                action_pb.setCheckable(True)
                action_pb.setAutoExclusive(True)
                action_pb.setChecked(True)
                action_pb.clicked.connect(partial(self.toggle_action, field_name, True))

                valid_ref_sublayout.addWidget(no_action_pb, 0, 0)
                valid_ref_sublayout.addWidget(action_pb, 0, 1)

                # Add invalid reference widgets
                invalid_ref_widget = QWidget()
                invalid_ref_sublayout = QGridLayout()
                invalid_ref_widget.setLayout(invalid_ref_sublayout)

                filepath_sublayout = QGridLayout()
                filepath_line_edit = QLineEdit()
                filepath_line_edit.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
                browse_pb = QPushButton("...")
                browse_pb.clicked.connect(partial(self.browse_for_raster, field_name))
                filepath_sublayout.addWidget(filepath_line_edit, 0, 0)
                filepath_sublayout.addWidget(browse_pb, 0, 1)
                invalid_ref_sublayout.addLayout(filepath_sublayout, 0, 0)

                update_ref_pb = QPushButton("Update reference")
                update_ref_pb.clicked.connect(partial(self.update_raster_reference, field_name))
                invalid_ref_sublayout.addWidget(update_ref_pb, 0, 1)

                actions_sublayout.addWidget(valid_ref_widget, 0, 0)
                actions_sublayout.addWidget(invalid_ref_widget, 1, 0)
                # Add all actions widget into the main widget layout
                widget_layout.addWidget(all_actions_widget, current_main_layout_row, 2)
                # Hide some of the widgets based on files states
                if status == UploadFileStatus.NO_CHANGES_DETECTED:
                    all_actions_widget.hide()
                elif status == UploadFileStatus.INVALID_REFERENCE:
                    valid_ref_widget.hide()
                else:
                    invalid_ref_widget.hide()
                self.widgets_per_file[field_name] = (
                    name_label,
                    status_label,
                    valid_ref_widget,
                    action_pb,
                    invalid_ref_widget,
                    filepath_line_edit,
                )
                current_main_layout_row += 1

    def toggle_action(self, raster_type, make_action):
        files_refs = self.detected_files[raster_type]
        files_refs["make_action"] = make_action

    def browse_for_raster(self, raster_type):
        """Browse for raster file for a given raster type."""
        name_filter = "GeoTIFF (*.tif *.TIF *.tiff *.TIFF)"
        title = "Select reference raster file"
        raster_file = get_filepath(None, extension_filter=name_filter, dialog_title=title)
        if raster_file:
            filepath_line_edit = self.widgets_per_file[raster_type][-1]
            filepath_line_edit.setText(raster_file)

    def update_raster_reference(self, raster_type):
        """
        Update raster reference and copy file to the raster subdirectory if it lays outside of it.
        """
        (
            name_label,
            status_label,
            valid_ref_widget,
            action_pb,
            invalid_ref_widget,
            filepath_line_edit,
        ) = self.widgets_per_file[raster_type]
        new_filepath = filepath_line_edit.text()
        if new_filepath:
            new_file = os.path.basename(new_filepath)
            main_dir = os.path.dirname(self.schematisation_sqlite)
            relative_filepath = f"rasters/{new_file}"
            target_filepath = os.path.join(main_dir, "rasters", new_file)
            filepath_exists = os.path.exists(new_filepath)
            if filepath_exists:
                if not os.path.exists(target_filepath):
                    shutil.copyfile(new_filepath, target_filepath)
        else:
            relative_filepath = None
            target_filepath = None
            filepath_exists = False
        reference_table = self.file_table_mapping[raster_type]
        table_lyr = sqlite_layer(self.schematisation_sqlite, reference_table, geom_column=None)
        first_feat = next(table_lyr.getFeatures())
        field_idx = table_lyr.fields().lookupField(raster_type)
        fid = first_feat.id()
        table_lyr.startEditing()
        table_lyr.changeAttributeValue(fid, field_idx, relative_filepath)
        table_lyr.commitChanges()
        (
            spatialite_name_label,
            spatialite_status_label,
            spatialite_valid_ref_widget,
            spatialite_action_pb,
            spatialite_invalid_ref_widget,
            spatialite_filepath_line_edit,
        ) = self.widgets_per_file["spatialite"]
        spatialite_files_refs = self.detected_files["spatialite"]
        spatialite_files_refs["status"] = UploadFileStatus.CHANGES_DETECTED
        spatialite_status_label.setText(UploadFileStatus.CHANGES_DETECTED.value)
        spatialite_valid_ref_widget.show()
        files_refs = self.detected_files[raster_type]
        remote_raster = files_refs["remote_raster"]
        files_refs["filepath"] = target_filepath
        if not relative_filepath:
            if not remote_raster:
                files_refs["status"] = UploadFileStatus.NO_CHANGES_DETECTED
                status_label.setText(UploadFileStatus.NO_CHANGES_DETECTED.value)
                invalid_ref_widget.hide()
            else:
                files_refs["status"] = UploadFileStatus.DELETED_LOCALLY
                status_label.setText(UploadFileStatus.DELETED_LOCALLY.value)
                action_pb.setText("Delete online")
                invalid_ref_widget.hide()
                valid_ref_widget.show()
        else:
            if filepath_exists:
                if not remote_raster:
                    files_refs["status"] = UploadFileStatus.NEW
                    status_label.setText(UploadFileStatus.NEW.value)
                    invalid_ref_widget.hide()
                    valid_ref_widget.show()
                else:
                    if is_file_checksum_equal(new_filepath, remote_raster.file.etag):
                        files_refs["status"] = UploadFileStatus.NO_CHANGES_DETECTED
                        status_label.setText(UploadFileStatus.NO_CHANGES_DETECTED.value)
                        invalid_ref_widget.hide()
                    else:
                        files_refs["status"] = UploadFileStatus.CHANGES_DETECTED
                        status_label.setText(UploadFileStatus.CHANGES_DETECTED.value)
                        invalid_ref_widget.hide()
                        valid_ref_widget.show()


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
        self.schematisation = self.upload_dialog.schematisation
        self.schematisation_sqlite = self.upload_dialog.schematisation_sqlite
        self.tc = self.upload_dialog.tc
        available_revisions = self.tc.fetch_schematisation_revisions(self.schematisation.id)
        if available_revisions:
            self.latest_revision = max(available_revisions, key=attrgetter("id"))
        else:
            self.latest_revision = self.tc.create_schematisation_revision(self.schematisation.id, empty=True)
        self.start_page = StartPage(self)
        self.start_page.main_widget.lbl_schematisation.setText(self.schematisation.name)
        self.start_page.main_widget.lbl_online_revision.setText(str(self.latest_revision.number))
        if self.latest_revision.is_valid is True:
            self.start_page.main_widget.pb_use_revision.setDisabled(True)
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
        self.new_upload["schematisation"] = self.schematisation
        self.new_upload["latest_revision"] = self.latest_revision
        self.new_upload["selected_files"] = self.select_files_page.main_widget.detected_files
        self.new_upload["commit_message"] = self.select_files_page.main_widget.te_upload_description.toPlainText()
        self.new_upload["create_revision"] = self.start_page.main_widget.pb_create_revision.isChecked()
        self.new_upload["upload_only"] = self.select_files_page.main_widget.pb_upload_only.isChecked()

    def cancel_wizard(self):
        """Handling canceling wizard action."""
        self.settings.setValue("threedi/upload_wizard_size", self.size())
        self.reject()
