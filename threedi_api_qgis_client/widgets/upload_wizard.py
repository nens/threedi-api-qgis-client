# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import os
from collections import OrderedDict, defaultdict
from qgis.PyQt.QtSvg import QSvgWidget
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import QSettings, Qt, QSize
from qgis.PyQt.QtWidgets import QWizardPage, QWizard, QWidget, QGridLayout, QSizePolicy, QFileDialog, QLabel, QPushButton, QLineEdit
from threedi_api_client.openapi import ApiException
from ..utils import is_file_checksum_equal, sqlite_layer
from ..ui_utils import get_filepath, set_widget_background_color
from ..api_calls.threedi_calls import ThreediCalls


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
        self.latest_revision_number = self.parent_page.parent_wizard.latest_revision_number
        self.schematisation = self.parent_page.parent_wizard.upload_dialog.schematisation
        self.schematisation_sqlite = self.parent_page.parent_wizard.upload_dialog.schematisation_sqlite
        self.tc = self.parent_page.parent_wizard.tc
        self.initialize_widgets()
        # set_widget_background_color(self)

    @property
    def general_files(self):
        files_info = OrderedDict(
            (
                ("spatialite", "Spatialite"),
            )
        )
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

    def check_files_states(self):
        files_ref_tables = OrderedDict(
            (
                ("v2_global_settings", self.terrain_model_files),
                ("v2_simple_infiltration", self.simple_infiltration_files),
                ("v2_groundwater", self.groundwater_files),
                ("v2_interflow", self.interflow_files),
            )
        )
        files_info = OrderedDict()
        remote_rasters = self.tc.fetch_schematisation_revision_rasters(self.schematisation.id, self.latest_revision_number)
        sqlite_localisation = os.path.dirname(self.schematisation_sqlite)
        for sqlite_table, files_fields in files_ref_tables.items():
            sqlite_table_lyr = sqlite_layer(self.schematisation_sqlite, sqlite_table, geom_column=None)
            try:
                first_feat = next(sqlite_table_lyr.getFeatures())
            except StopIteration:
                continue
            for file_field in files_fields:
                file_relative_path = first_feat[file_field]
                if not file_relative_path:
                    continue
                filepath = os.path.join(sqlite_localisation, file_relative_path)
                # TODO: Needs to be finished

    def initialize_widgets(self):
        files_widgets = [self.widget_terrain_model, self.widget_simple_infiltration, self.widget_groundwater, self.widget_interflow]
        files_info_collection = [self.terrain_model_files, self.simple_infiltration_files, self.groundwater_files, self.interflow_files]
        for widget, files_info in zip(files_widgets, files_info_collection):
            widget_layout = widget.layout()
            for i, (field_name, name) in enumerate(files_info.items(), start=1):
                name_normalized = name.lower().replace(" ", "_")
                name_label = QLabel(name)
                name_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

                status_label = QLabel("NO CHANGES DETECTED")
                status_label.setObjectName(f"{name_normalized}_status")
                status_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

                filepath_line_edit = QLineEdit()
                filepath_line_edit.setObjectName(f"{name_normalized}_path")
                filepath_line_edit.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

                browse_pb = QPushButton("...")
                browse_pb.setObjectName(f"{name_normalized}_browse")

                update_ref_pb = QPushButton("Update reference")
                update_ref_pb.setObjectName(f"{name_normalized}_update_reference")

                ignore_pb = QPushButton("Ignore")
                ignore_pb.setObjectName(f"{name_normalized}_ignore_changes")
                ignore_pb.setCheckable(True)
                ignore_pb.setAutoExclusive(True)

                apply_pb = QPushButton("Upload")
                apply_pb.setObjectName(f"{name_normalized}_apply_changes")
                apply_pb.setCheckable(True)
                apply_pb.setAutoExclusive(True)
                apply_pb.setChecked(True)

                changes_action_widget = QWidget()
                changes_sublayout = QGridLayout()
                changes_action_widget.setLayout(changes_sublayout)
                changes_sublayout.addWidget(ignore_pb, 0, 0)
                changes_sublayout.addWidget(apply_pb, 0, 1)

                invalid_ref_sublayout = QGridLayout()
                filepath_sublayout = QGridLayout()
                filepath_sublayout.addWidget(filepath_line_edit, 0, 0)
                filepath_sublayout.addWidget(browse_pb, 0, 1)
                invalid_ref_sublayout.addLayout(filepath_sublayout, 0, 0)
                invalid_ref_sublayout.addWidget(update_ref_pb, 0, 1)

                widget_layout.addWidget(name_label, i, 0)
                widget_layout.addWidget(status_label, i, 1)

                # widget_layout.addLayout(invalid_ref_sublayout, i, 2)
                widget_layout.addWidget(changes_action_widget, i, 2)


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
        self.latest_revision_number = self.tc.fetch_schematisation_latest_revision(self.upload_dialog.schematisation.id).number  # Add handling of the first revision case
        self.start_page = StartPage(self)
        self.start_page.main_widget.lbl_schematisation.setText(self.upload_dialog.schematisation.name)
        self.start_page.main_widget.lbl_online_revision.setText(str(self.latest_revision_no))
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
        self.new_upload["latest_revision"] = self.latest_revision_no
        self.new_upload["sqlite_filepath"] = self.upload_dialog.schematisation_sqlite

    def cancel_wizard(self):
        """Handling canceling wizard action."""
        self.settings.setValue("threedi/upload_wizard_size", self.size())
        self.reject()
