# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import csv
import os
import shutil
from collections import OrderedDict, defaultdict
from functools import partial
from operator import attrgetter

from qgis.PyQt import uic
from qgis.PyQt.QtCore import QSettings, QSize
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel
from qgis.PyQt.QtWidgets import QGridLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, QWidget, QWizard, QWizardPage
from threedi_api_client.openapi import ApiException, SchematisationRevision

from ..communication import LogLevels, TreeViewLogger
from ..utils import (
    SchematisationRasterReferences,
    UploadFileStatus,
    UploadFileType,
    is_file_checksum_equal,
    zip_into_archive,
)
from ..utils_qgis import geopackage_layer
from ..utils_ui import get_filepath, migrate_schematisation_schema

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
        self.tv_revisions_model = QStandardItemModel()
        self.revisions_tv.setModel(self.tv_revisions_model)
        self.current_local_schematisation = self.parent_page.parent_wizard.current_local_schematisation
        self.schematisation = self.parent_page.parent_wizard.schematisation
        self.schematisation_filepath = self.parent_page.parent_wizard.schematisation_filepath
        self.available_revisions = self.parent_page.parent_wizard.available_revisions
        self.latest_revision = self.parent_page.parent_wizard.latest_revision
        organisation = self.parent_page.parent_wizard.plugin_dock.organisations[self.schematisation.owner]
        wip_revision = self.current_local_schematisation.wip_revision
        self.lbl_schematisation.setText(f"{self.schematisation.name} ({organisation.name})")
        self.lbl_model_dir.setText(wip_revision.schematisation_dir)
        self.lbl_revision_number.setText(str(wip_revision.number))
        self.populate_available_revisions()

    def populate_available_revisions(self):
        self.tv_revisions_model.clear()
        header = ["Revision number", "Committed by", "Commit date", "Commit message"]
        self.tv_revisions_model.setHorizontalHeaderLabels(header)
        for revision in sorted(self.available_revisions, key=attrgetter("number"), reverse=True):
            number_item = QStandardItem(str(revision.number))
            commit_user_item = QStandardItem(revision.commit_user or "")
            commit_date = revision.commit_date.strftime("%d-%m-%Y") if revision.commit_date else ""
            commit_date_item = QStandardItem(commit_date)
            commit_message_item = QStandardItem(revision.commit_message or "")
            self.tv_revisions_model.appendRow([number_item, commit_user_item, commit_date_item, commit_message_item])
        for i in range(len(header)):
            self.revisions_tv.resizeColumnToContents(i)


class CheckModelWidget(uicls_check_page, basecls_check_page):
    """Widget for the Check Model page."""

    SCHEMATISATION_CHECKS_HEADER = ("Level", "Error code", "ID", "Table", "Column", "Value", "Description")
    GRID_CHECKS_HEADER = ("Level", "Description")

    CHECKS_PER_CODE_LIMIT = 100

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.current_local_schematisation = self.parent_page.parent_wizard.current_local_schematisation
        self.schematisation_filepath = self.parent_page.parent_wizard.schematisation_filepath
        self.communication = self.parent_page.parent_wizard.plugin_dock.communication
        self.schematisation_checker_logger = TreeViewLogger(
            self.tv_schema_check_result, self.SCHEMATISATION_CHECKS_HEADER
        )
        self.grid_checker_logger = TreeViewLogger(self.tv_grid_check_result, self.GRID_CHECKS_HEADER)
        self.pb_check_model.clicked.connect(self.run_model_checks)
        self.btn_export_check_schematisation_results.clicked.connect(
            partial(
                self.export_schematisation_checker_results,
                self.schematisation_checker_logger,
                self.SCHEMATISATION_CHECKS_HEADER,
            )
        )
        self.btn_export_check_grid_results.clicked.connect(
            partial(
                self.export_schematisation_checker_results,
                self.grid_checker_logger,
                self.GRID_CHECKS_HEADER,
            )
        )
        self.lbl_check_schematisation.hide()
        self.lbl_check_grid.hide()
        self.lbl_on_limited_display.hide()
        self.test_external_imports()

    def test_external_imports(self):
        """Check availability of an external checkers."""
        try:
            from sqlalchemy.exc import OperationalError
            from threedi_modelchecker import ThreediModelChecker
            from threedi_schema import ThreediDatabase, errors
            from threedigrid_builder import SchematisationError, make_gridadmin

            self.lbl_on_import_error.hide()
            self.pb_check_model.setEnabled(True)
        except ImportError:
            self.lbl_on_import_error.show()
            self.pb_check_model.setDisabled(True)

    def run_model_checks(self):
        """Run all available checks for a schematisation model."""
        self.btn_export_check_schematisation_results.setDisabled(True)
        self.lbl_check_schematisation.hide()
        self.pbar_check_schematisation.show()
        self.schematisation_checker_logger.initialize_view()
        self.pbar_check_schematisation.setValue(0)
        self.check_schematisation()
        self.btn_export_check_schematisation_results.setEnabled(True)
        self.lbl_check_grid.hide()
        self.pbar_check_grid.show()
        self.grid_checker_logger.initialize_view()
        self.pbar_check_grid.setValue(0)
        self.check_computational_grid()
        self.btn_export_check_grid_results.setEnabled(True)
        self.communication.bar_info("Finished schematisation checks.")

    def check_schematisation(self):
        """Run schematisation database checks."""
        from sqlalchemy.exc import OperationalError
        from threedi_modelchecker import ThreediModelChecker
        from threedi_schema import ThreediDatabase, errors

        self.lbl_on_limited_display.hide()
        threedi_db = ThreediDatabase(self.schematisation_filepath)
        schema = threedi_db.schema
        try:
            schema.validate_schema()
        except errors.MigrationMissingError:
            warn_and_ask_msg = (
                "The selected schematisation DB cannot be used, because its database schema version is out of date. "
                "Would you like to migrate your schematisation database to the current schema version?"
            )
            do_migration = self.communication.ask(None, "Missing migration", warn_and_ask_msg)
            if not do_migration:
                self.communication.bar_warn("Schematisation checks skipped!")
                return
            wip_revision = self.current_local_schematisation.wip_revision
            migration_succeed, migration_feedback_msg = migrate_schematisation_schema(wip_revision.geopackage_filepath)
            if not migration_succeed:
                self.communication.show_error(migration_feedback_msg, self)
                return
        except Exception as e:
            error_msg = f"{e}"
            self.communication.show_error(error_msg, self)
            return
        try:
            model_checker = ThreediModelChecker(threedi_db)
            model_checker.db.check_connection()
        except OperationalError as exc:
            error_msg = (
                f"Failed to start a connection with the database.\n"
                f"Something went wrong trying to connect to the database, "
                f"please check the connection settings: {exc.args[0]}"
            )
            self.communication.show_error(error_msg, self)
            return

        session = model_checker.db.get_session()
        session.model_checker_context = model_checker.context
        total_checks = len(model_checker.config.checks)

        results_rows = defaultdict(list)
        for i, check in enumerate(model_checker.checks(level=LogLevels.INFO.value), start=1):
            for result_row in check.get_invalid(session):
                results_rows[check.error_code].append(
                    [
                        check.level.name,
                        check.error_code,
                        result_row.id,
                        check.table.name,
                        check.column.name,
                        getattr(result_row, check.column.name),
                        check.description(),
                    ]
                )
            self.pbar_check_schematisation.setValue(i)
        if results_rows:
            for error_code, results_per_code in results_rows.items():
                if len(results_per_code) > self.CHECKS_PER_CODE_LIMIT:
                    results_per_code = results_per_code[: self.CHECKS_PER_CODE_LIMIT]
                    if self.lbl_on_limited_display.isHidden():
                        self.lbl_on_limited_display.show()
                for result_row in results_per_code:
                    level = result_row[0].upper()
                    self.schematisation_checker_logger.log_result_row(result_row, level)
        self.pbar_check_schematisation.setValue(total_checks)
        self.pbar_check_schematisation.hide()
        self.lbl_check_schematisation.show()

    def check_computational_grid(self):
        """Run computational grid checks."""
        from threedigrid_builder import SchematisationError, make_gridadmin

        def progress_logger(progress, info):
            self.pbar_check_grid.setValue(int(progress * 100))
            self.grid_checker_logger.log_result_row([LogLevels.INFO.value.capitalize(), info], LogLevels.INFO.value)

        self.pbar_check_grid.setMaximum(100)
        self.pbar_check_grid.setValue(0)
        try:
            model_settings_layer = geopackage_layer(self.schematisation_filepath, "model_settings")
            model_settings_feat = next(model_settings_layer.getFeatures())
            dem_file = model_settings_feat["dem_file"]
            if dem_file:
                schematisation_dir = os.path.dirname(self.schematisation_filepath)
                dem_file_name = os.path.basename(dem_file)
                dem_path = os.path.join(schematisation_dir, "rasters", dem_file_name)
            else:
                dem_path = None
            # TODO: threedigrid_builder needs to be updated?
            make_gridadmin(
                sqlite_path=self.schematisation_filepath, dem_path=dem_path, progress_callback=progress_logger
            )
        except SchematisationError as e:
            err = f"Creating grid file failed with the following error: {repr(e)}"
            self.grid_checker_logger.log_result_row([LogLevels.ERROR.value.capitalize(), err], LogLevels.ERROR.value)
        except Exception as e:
            err = f"Checking computational grid failed with the following error: {repr(e)}"
            self.grid_checker_logger.log_result_row([LogLevels.ERROR.value.capitalize(), err], LogLevels.ERROR.value)
        finally:
            self.pbar_check_grid.setValue(100)
        self.pbar_check_grid.hide()
        self.lbl_check_grid.show()

    def export_schematisation_checker_results(self, logger_tree_view, header):
        """Save schematisation checker results into the CSV file."""
        model = logger_tree_view.model
        row_count = model.rowCount()
        column_count = model.columnCount()
        checker_results = []
        for row_idx in range(row_count):
            row_items = [model.item(row_idx, col_idx) for col_idx in range(column_count)]
            row = [it.text() for it in row_items]
            checker_results.append(row)
        if not checker_results:
            self.communication.show_warn("There is nothing to export. Action aborted.")
            return
        csv_filepath = get_filepath(
            self, extension_filter="CSV file (*.csv)", save=True, dialog_title="Export schematisation checker results"
        )
        if not csv_filepath:
            return
        with open(csv_filepath, "w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=",")
            csv_writer.writerow(header)
            csv_writer.writerows(checker_results)
        self.communication.show_info("Schematisation checker results successfully exported!")


class SelectFilesWidget(uicls_files_page, basecls_files_page):
    """Widget for the Select Files page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.latest_revision = self.parent_page.parent_wizard.latest_revision
        self.schematisation = self.parent_page.parent_wizard.schematisation
        self.schematisation_filepath = self.parent_page.parent_wizard.schematisation_filepath
        self.tc = self.parent_page.parent_wizard.tc
        self.cb_make_3di_model.stateChanged.connect(self.toggle_make_3di_model)
        self.detected_files = self.check_files_states()
        self.widgets_per_file = {}
        self.initialize_widgets()

    @property
    def general_files(self):
        """Files mapping for the General group widget."""
        files_info = OrderedDict((("geopackage", "GeoPackage"),))
        return files_info

    @property
    def terrain_model_files(self):
        """Files mapping for the Terrain Model group widget."""
        return SchematisationRasterReferences.model_settings_rasters()

    @property
    def simple_infiltration_files(self):
        """Files mapping for the Infiltration group widget."""
        return SchematisationRasterReferences.simple_infiltration_rasters()

    @property
    def groundwater_files(self):
        """Files mapping for the Groundwater group widget."""
        return SchematisationRasterReferences.groundwater_rasters()

    @property
    def interflow_files(self):
        """Files mapping for the Interflow group widget."""
        return SchematisationRasterReferences.interflow_rasters()

    @property
    def vegetation_drag_files(self):
        """Files mapping for the Vegetation drag settings group widget."""
        return SchematisationRasterReferences.vegetation_drag_rasters()

    @property
    def files_reference_tables(self):
        """GeoPackage tables mapping with references to the files."""
        return SchematisationRasterReferences.raster_reference_tables()

    @property
    def file_table_mapping(self):
        """Files to geopackage tables mapping."""
        return SchematisationRasterReferences.raster_table_mapping()

    def toggle_make_3di_model(self):
        """Handle Make 3Di model checkbox state changes."""
        if self.cb_make_3di_model.isChecked():
            self.cb_inherit_templates.setChecked(True)
            self.cb_inherit_templates.setEnabled(True)
        else:
            self.cb_inherit_templates.setChecked(False)
            self.cb_inherit_templates.setEnabled(False)

    def check_files_states(self):
        """Check raster (and geopackage) files presence and compare local and remote data."""
        files_states = OrderedDict()
        if self.latest_revision.number > 0:
            remote_rasters = self.tc.fetch_schematisation_revision_rasters(
                self.schematisation.id, self.latest_revision.id
            )
        else:
            remote_rasters = []
        remote_rasters_by_type = {raster.type: raster for raster in remote_rasters}
        if "dem_raw_file" in remote_rasters_by_type:
            remote_rasters_by_type["dem_file"] = remote_rasters_by_type["dem_raw_file"]
            del remote_rasters_by_type["dem_raw_file"]
        geopackage_dir = os.path.dirname(self.schematisation_filepath)
        if self.latest_revision.sqlite:
            try:
                zipped_schematisation_db = zip_into_archive(self.schematisation_filepath)
                sqlite_download = self.tc.download_schematisation_revision_sqlite(
                    self.schematisation.id, self.latest_revision.id
                )
                files_matching = is_file_checksum_equal(zipped_schematisation_db, sqlite_download.etag)
                status = UploadFileStatus.NO_CHANGES_DETECTED if files_matching else UploadFileStatus.CHANGES_DETECTED
                os.remove(zipped_schematisation_db)
            except ApiException:
                status = UploadFileStatus.CHANGES_DETECTED
        else:
            status = UploadFileStatus.NEW
        files_states["geopackage"] = {
            "status": status,
            "filepath": self.schematisation_filepath,
            "type": UploadFileType.DB,
            "remote_raster": None,
            "make_action": True,
        }

        for table_name, files_fields in self.files_reference_tables.items():
            table_lyr = geopackage_layer(self.schematisation_filepath, table_name)
            try:
                first_feat = next(table_lyr.getFeatures())
            except StopIteration:
                continue
            for file_field in files_fields:
                try:
                    file_relative_path = first_feat[file_field]
                except KeyError:
                    continue
                remote_raster = remote_rasters_by_type.get(file_field)
                if not file_relative_path and not remote_raster:
                    continue
                filepath = os.path.join(geopackage_dir, "rasters", file_relative_path) if file_relative_path else None
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
            self.widget_vegetation_drag,
        ]
        files_info_collection = [
            self.general_files,
            self.terrain_model_files,
            self.simple_infiltration_files,
            self.groundwater_files,
            self.interflow_files,
            self.vegetation_drag_files,
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
                actions_sublayout.addWidget(invalid_ref_widget, 0, 1)
                # Add all actions widget into the main widget layout
                widget_layout.addWidget(all_actions_widget, current_main_layout_row, 2)
                # Hide some widgets based on files states
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
        """Update detected files info after particular action change."""
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
            new_file_name = os.path.basename(new_filepath)
            main_dir = os.path.dirname(self.schematisation_filepath)
            target_filepath = os.path.join(main_dir, "rasters", new_file_name)
            filepath_exists = os.path.exists(new_filepath)
            if filepath_exists:
                if not os.path.exists(target_filepath):
                    shutil.copyfile(new_filepath, target_filepath)
        else:
            new_file_name = ""
            target_filepath = None
            filepath_exists = False
        reference_table = self.file_table_mapping[raster_type]
        table_lyr = geopackage_layer(self.schematisation_filepath, reference_table)
        first_feat = next(table_lyr.getFeatures())
        field_idx = table_lyr.fields().lookupField(raster_type)
        fid = first_feat.id()
        table_lyr.startEditing()
        table_lyr.changeAttributeValue(fid, field_idx, new_file_name)
        table_lyr.commitChanges()
        (
            geopackage_name_label,
            geopackage_status_label,
            geopackage_valid_ref_widget,
            geopackage_action_pb,
            geopackage_invalid_ref_widget,
            geopackage_filepath_line_edit,
        ) = self.widgets_per_file["geopackage"]
        geopackage_files_refs = self.detected_files["geopackage"]
        if geopackage_files_refs["status"] != UploadFileStatus.NEW:
            geopackage_files_refs["status"] = UploadFileStatus.CHANGES_DETECTED
            geopackage_status_label.setText(UploadFileStatus.CHANGES_DETECTED.value)
            geopackage_valid_ref_widget.show()
        files_refs = self.detected_files[raster_type]
        remote_raster = files_refs["remote_raster"]
        files_refs["filepath"] = target_filepath
        if not new_file_name:
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
        commit_msg_te = self.main_widget.te_upload_description
        self.registerField("commit_msg*", commit_msg_te, property="plainText", changedSignal=commit_msg_te.textChanged)
        self.adjustSize()


class UploadWizard(QWizard):
    """New upload wizard."""

    def __init__(self, plugin_dock, upload_dialog, parent=None):
        super().__init__(parent)
        self.settings = QSettings()
        self.setWizardStyle(QWizard.ClassicStyle)
        self.plugin_dock = plugin_dock
        self.upload_dialog = upload_dialog
        self.current_local_schematisation = self.upload_dialog.current_local_schematisation
        self.schematisation = self.upload_dialog.schematisation
        self.schematisation_filepath = self.upload_dialog.schematisation_filepath
        self.tc = self.upload_dialog.tc
        self.available_revisions = self.tc.fetch_schematisation_revisions(self.schematisation.id)
        if self.available_revisions:
            self.latest_revision = max(self.available_revisions, key=attrgetter("id"))
        else:
            self.latest_revision = SchematisationRevision(number=0)
        self.start_page = StartPage(self)
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
        """Build dictionary with new upload parameters."""
        self.new_upload.clear()
        self.new_upload["schematisation"] = self.schematisation
        self.new_upload["latest_revision"] = self.latest_revision
        self.new_upload["selected_files"] = self.select_files_page.main_widget.detected_files
        self.new_upload["commit_message"] = self.select_files_page.main_widget.te_upload_description.toPlainText()
        self.new_upload["create_revision"] = True
        self.new_upload["make_3di_model"] = self.select_files_page.main_widget.cb_make_3di_model.isChecked()
        self.new_upload["cb_inherit_templates"] = self.select_files_page.main_widget.cb_inherit_templates.isChecked()

    def cancel_wizard(self):
        """Handling canceling wizard action."""
        self.settings.setValue("threedi/upload_wizard_size", self.size())
        self.reject()
