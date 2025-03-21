# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import os
import shutil
import time
from collections import defaultdict
from functools import partial
from operator import itemgetter
from pathlib import Path

from qgis.core import QgsFeature, QgsRasterLayer
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QSettings, QSize, Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QGridLayout, QSizePolicy, QWizard, QWizardPage
from threedi_api_client.openapi import ApiException
from threedi_mi_utils import LocalSchematisation
from threedi_schema import ThreediDatabase

from ..api_calls.threedi_calls import ThreediCalls
from ..utils import SchematisationRasterReferences, extract_error_message
from ..utils_qgis import geopackage_layer
from ..utils_ui import ensure_valid_schema, get_filepath, read_3di_settings, save_3di_settings, scan_widgets_parameters


base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_schema_name_page, basecls_schema_name_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "new_schematisation_wizard", "page_schema_name.ui")
)
uicls_schema_explain_page, basecls_schema_explain_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "new_schematisation_wizard", "page_schema_explain.ui")
)
uicls_schema_settings_page, basecls_schema_settings_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "new_schematisation_wizard", "page_schema_settings.ui")
)


class CommitErrors(Exception):
    pass


class GeoPackageError(Exception):
    pass


class SchematisationNameWidget(uicls_schema_name_page, basecls_schema_name_page):
    """Widget for the Schematisation Name and tags page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.organisations = self.parent_page.organisations
        self.populate_organisations()
        self.btn_browse_geopackage.clicked.connect(self.browse_existing_geopackage)
        self.cbo_organisations.currentTextChanged.connect(partial(save_3di_settings, "threedi/last_used_organisation"))

    def populate_organisations(self):
        """Populating organisations."""
        for org in self.organisations.values():
            self.cbo_organisations.addItem(org.name, org)
        last_organisation = read_3di_settings("threedi/last_used_organisation")
        if last_organisation:
            self.cbo_organisations.setCurrentText(last_organisation)

    def get_new_schematisation_data(self):
        """Return new schematisation name, tags and owner."""
        name = self.le_schematisation_name.text()
        description = self.le_description.text()
        if not self.le_tags.text():
            tags = []
        else:
            tags = [tag.strip() for tag in self.le_tags.text().split(",")]
        organisation = self.cbo_organisations.currentData()
        owner = organisation.unique_id
        return name, description, tags, owner

    def browse_existing_geopackage(self):
        """Show dialog for choosing an existing GeoPackage file path."""
        gpkg_filter = "GeoPackage/SQLite (*.gpkg *.GPKG *.sqlite *SQLITE)"
        geopackage_path = get_filepath(self, dialog_title="Select Schematisation file", extension_filter=gpkg_filter)
        if geopackage_path is not None:
            schema_is_valid = ensure_valid_schema(
                geopackage_path, self.parent_page.parent_wizard.plugin_dock.communication
            )
            if schema_is_valid is True:
                if geopackage_path.lower().endswith(".sqlite"):
                    geopackage_path = geopackage_path.rsplit(".", 1)[0] + ".gpkg"
                self.le_geopackage_path.setText(geopackage_path)


class SchematisationExplainWidget(uicls_schema_explain_page, basecls_schema_explain_page):
    """Widget for the Schematisation explanation text page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page


class SchematisationSettingsWidget(uicls_schema_settings_page, basecls_schema_settings_page):
    """Widget for the Schematisation Settings page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.use_1d_flow_group.toggled.connect(self.on_1d_flow_toggled)
        self.use_2d_flow_group.toggled.connect(self.on_2d_flow_toggled)
        self.dem_file.fileChanged.connect(self.on_dem_file_change)

    def on_1d_flow_toggled(self, on):
        """Logic for checking/unchecking 1D Flow settings group."""
        if on:
            if self.use_2d_flow_group.isChecked():
                self.manhole_aboveground_storage_area_label.setDisabled(True)
                self.manhole_aboveground_storage_area.setDisabled(True)
            else:
                self.manhole_aboveground_storage_area_label.setEnabled(True)
                self.manhole_aboveground_storage_area.setEnabled(True)

    def on_2d_flow_toggled(self, on):
        """Logic for checking/unchecking 2D Flow settings group."""
        if on:
            self.friction_coefficient_label.setEnabled(True)
            self.friction_coefficient_file.setEnabled(True)
            self.minimum_cell_size.setValue(0.0)
            if self.use_1d_flow_group.isChecked():
                self.manhole_aboveground_storage_area_label.setDisabled(True)
                self.manhole_aboveground_storage_area.setDisabled(True)
        else:
            self.friction_coefficient_label.setDisabled(True)
            self.friction_coefficient_file.setDisabled(True)
            self.minimum_cell_size.setValue(9999.0)
            if self.use_1d_flow_group.isChecked():
                self.manhole_aboveground_storage_area_label.setEnabled(True)
                self.manhole_aboveground_storage_area.setEnabled(True)

    def on_dem_file_change(self):
        """Extra logic for changing DEM file path."""
        dem_filepath = self.dem_file.filePath()
        raster_layer = QgsRasterLayer(dem_filepath)
        if raster_layer.isValid():
            raster_crs = raster_layer.crs()
            self.crs.setCrs(raster_crs)

    @property
    def model_settings_defaults(self):
        """Model settings defaults."""
        defaults = {
            "dem_file": None,
            "calculation_point_distance": 1000.0,
            "embedded_cutoff_threshold": 0.05,
            "epsg_code": None,
            "friction_averaging": 0,
            "friction_coefficient": None,
            "friction_coefficient_file": None,
            "friction_type": None,
            "minimum_cell_size": 0.0,
            "use_groundwater_flow": None,
            "use_interflow": None,
            "nr_grid_levels": 1,
            "manhole_aboveground_storage_area": None,
            "max_angle_1d_advection": 1.570795,
            "maximum_table_step_size": None,
            "use_simple_infiltration": None,
            "minimum_table_step_size": 0.05,
            "table_step_size_1d": 0.01,
            "use_1d_flow": None,
            "use_2d_flow": None,
            "use_2d_rain": None,
        }
        return defaults

    @property
    def numerical_settings_defaults(self):
        """Numerical settings defaults."""
        defaults = {
            "cfl_strictness_factor_1d": 1.0,
            "cfl_strictness_factor_2d": 1.0,
            "convergence_cg": 0.000000001,
            "convergence_eps": 0.00001,
            "flooding_threshold": 0.0001,
            "flow_direction_threshold": 0.000001,
            "friction_shallow_water_depth_correction": None,
            "general_numerical_threshold": 0.00000001,
            "time_integration_method": 0,
            "limiter_waterlevel_gradient_1d": 1,
            "limiter_waterlevel_gradient_2d": None,
            "limiter_slope_crossectional_area_2d": None,
            "limiter_slope_friction_2d": None,
            "max_degree_gauss_seidel": None,
            "max_non_linear_newton_iterations": 20,
            "min_friction_velocity": 0.005,
            "min_surface_area": 0.00000001,
            "use_preconditioner_cg": 1,
            "preissmann_slot": 0.0,
            "pump_implicit_ratio": 1.0,
            "limiter_slope_thin_water_layer": None,
            "use_of_cg": 20,
            "use_nested_newton": None,
        }
        return defaults

    @property
    def simulation_template_settings_defaults(self):
        """Simulation template settings defaults."""
        defaults = {
            "name": "default",
            "use_structure_control": None,
        }
        return defaults

    @property
    def time_step_settings_defaults(self):
        """Time step settings defaults."""
        defaults = {
            "time_step": None,
            "min_time_step": 0.01,
            "max_time_step": None,
            "output_time_step": None,
            "use_time_step_stretch": 0,
            "use_0d_inflow": None,
        }
        return defaults

    @property
    def physical_settings_defaults(self):
        """Physical settings defaults."""
        defaults = {
            "use_advection_1d": 3,
            "use_advection_2d": 1,
        }
        return defaults

    @property
    def initial_conditions_defaults(self):
        """Initial conditions defaults."""
        defaults = {
            "initial_groundwater_level": None,
            "initial_groundwater_level_file": None,
            "initial_groundwater_level_aggregation": None,
            "initial_water_level_aggregation": None,
            "initial_water_level": -99.0,
            "initial_water_level_file": None,
        }
        return defaults

    @property
    def interception_defaults(self):
        """Interception defaults."""
        defaults = {
            "interception": None,
            "interception_file": None,
        }
        return defaults

    @property
    def dry_weather_flow_distribution_defaults(self):
        defaults = {
            "description": "Kennisbank Stichting Rioned - https://www.riool.net/huishoudelijk-afvalwater",
            "distribution": "3,1.5,1,1,0.5,0.5,2.5,8,7.5,6,5.5,5,4.5,4,4,3.5,3.5,4,5.5,8,7,5.5,4.5,4"
        }
        return defaults

    @property
    def surface_parameters_defaults(self):
        return {'id': ['101', '102', '103', '104', '105', '106', '107', '108', '109', '110', '111', '112', '113', '114',
                       '115'], 'description': ['gesloten verharding, hellend', 'gesloten verharding, vlak',
                                               'gesloten verharding, vlak uitgestrekt', 'open verharding, hellend',
                                               'open verharding, vlak', 'open verharding, vlak uitgestrekt',
                                               'dak, hellend', 'dak, vlak', 'dak, vlak uitgestrekt',
                                               'onverhard, hellend', 'onverhard, vlak', 'onverhard, vlak uitgestrekt',
                                               'half verhard, hellend', 'half verhard, vlak',
                                               'half verhard, vlak uitgestrekt'],
                'outflow_delay': ['0.5', '0.2', '0.1', '0.5', '0.2', '0.1', '0.5', '0.2', '0.1', '0.5', '0.2', '0.1',
                                  '0.5', '0.2', '0.1'],
                'surface_layer_thickness': ['0', '0.5', '1', '0', '0.5', '1', '0', '2', '4', '2', '4', '6', '2', '4',
                                            '6'],
                'infiltration': ['0', '0', '0', '1', '1', '1', '0', '0', '0', '1', '1', '1', '1', '1', '1'],
                'max_infiltration_capacity': ['0', '0', '0', '2', '2', '2', '0', '0', '0', '5', '5', '5', '5', '5',
                                              '5'],
                'min_infiltration_capacity': ['0', '0', '0', '0.5', '0.5', '0.5', '0', '0', '0', '1', '1', '1', '1',
                                              '1', '1'],
                'infiltration_decay_constant': ['0', '0', '0', '3', '3', '3', '0', '0', '0', '3', '3', '3', '3', '3',
                                                '3'],
                'infiltration_recovery_constant': ['0', '0', '0', '0.1', '0.1', '0.1', '0', '0', '0', '0.1', '0.1',
                                                   '0.1', '0.1', '0.1', '0.1']}

    @property
    def materials_defaults(self):
        return {'id': ['0', '1', '2', '3', '4', '5', '6', '7', '8'],
                'description': ['Concrete', 'PVC', 'Gres', 'Cast iron', 'Brickwork', 'HPE', 'HDPE', 'Plate iron',
                                'Steel'],
                'friction_type': ['2', '2', '2', '2', '2', '2', '2', '2', '2'],
                'friction_coefficient': ['0.0145', '0.011', '0.0115', '0.0135', '0.016', '0.011', '0.011', '0.0135',
                                         '0.013']}

    @property
    def settings_tables_defaults(self):
        """Settings tables defaults map."""
        tables_defaults = {
            "model_settings": self.model_settings_defaults,
            "numerical_settings": self.numerical_settings_defaults,
            "simulation_template_settings": self.simulation_template_settings_defaults,
            "time_step_settings": self.time_step_settings_defaults,
            "physical_settings": self.physical_settings_defaults,
            "initial_conditions": self.initial_conditions_defaults,
            "interception": self.interception_defaults,
            "dry_weather_flow_distribution": self.dry_weather_flow_distribution_defaults,
            "material": self.materials_defaults,
            "surface_parameters": self.surface_parameters_defaults,
        }
        return tables_defaults

    @property
    def user_input_settings(self):
        """Get user input settings."""
        user_settings = scan_widgets_parameters(self)
        crs = user_settings["crs"]
        epsg = crs.authid()
        user_settings["epsg_code"] = int(epsg.split(":")[-1]) if epsg else 0
        use_1d_checked = self.use_1d_flow_group.isChecked()
        use_2d_checked = self.use_2d_flow_group.isChecked()
        user_settings["use_advection_1d"] = 3 if use_1d_checked else 0
        user_settings["use_advection_2d"] = 1 if use_2d_checked else 0
        if use_2d_checked:
            dem_file = os.path.basename(user_settings["dem_file"])
            user_settings["dem_file"] = dem_file if dem_file else None
            sloping_checked = user_settings["friction_shallow_water_depth_correction_sloping"]
            user_settings["friction_shallow_water_depth_correction"] = 3 if sloping_checked else 0
            user_settings["limiter_waterlevel_gradient_2d"] = 0 if sloping_checked else 1
            user_settings["limiter_slope_crossectional_area_2d"] = 3 if sloping_checked else 0
            user_settings["limiter_slope_friction_2d"] = 1 if sloping_checked else 0
            user_settings["limiter_slope_thin_water_layer"] = 0.1 if sloping_checked else None
        friction_type_text = user_settings["friction_type_text"]
        user_settings["friction_type"] = int(friction_type_text.split(":")[0])
        friction_coefficient_file = os.path.basename(user_settings["friction_coefficient_file"])
        user_settings["friction_coefficient_file"] = friction_coefficient_file if friction_coefficient_file else None
        if not use_1d_checked or use_2d_checked:
            user_settings["manhole_aboveground_storage_area"] = None
        time_step = user_settings["time_step"]
        output_time_step_text = user_settings["output_time_step_text"]
        output_time_step_map = {"0-3 hours": 300, "3-12 hours": 900, "12-24 hours": 1800, "> 24 hours": 3600}
        suggested_ots = output_time_step_map[output_time_step_text]
        out_timestep_mod = suggested_ots % time_step
        output_time_step = suggested_ots + (time_step - out_timestep_mod) if out_timestep_mod else suggested_ots
        user_settings["output_time_step"] = output_time_step
        if self.use_0d_inflow_group.isChecked():
            use_0d_inflow_surfaces = user_settings["use_0d_inflow_surfaces"]
            user_settings["use_0d_inflow"] = 2 if use_0d_inflow_surfaces else 1
        else:
            user_settings["use_0d_inflow"] = 0
        user_settings["use_1d_flow"] = 1 if use_1d_checked else 0
        user_settings["use_2d_flow"] = 1 if use_2d_checked else 0
        user_settings["use_2d_rain"] = 1 if use_2d_checked else 0
        user_settings["use_nested_newton"] = 1 if use_1d_checked else 0
        if use_1d_checked and not use_2d_checked:
            max_degree = 700
        elif use_1d_checked and use_2d_checked:
            max_degree = 7
        else:
            max_degree = 5
        user_settings["max_degree_gauss_seidel"] = max_degree
        return user_settings

    def raster_filepaths(self):
        """Get raster filepaths."""
        dem_file = self.dem_file.filePath()
        friction_coefficient_file = self.friction_coefficient_file.filePath()
        return dem_file, friction_coefficient_file

    def collect_new_schematisation_settings(self):
        """Get all needed settings."""
        all_schematisation_settings = defaultdict(dict)
        user_settings = self.user_input_settings
        for table_name, settings in self.settings_tables_defaults.items():
            for entry, default_value in settings.items():
                if entry in user_settings:
                    all_schematisation_settings[table_name][entry] = user_settings[entry]
                else:
                    all_schematisation_settings[table_name][entry] = default_value
        return all_schematisation_settings


class SchematisationNamePage(QWizardPage):
    """New schematisation name and tags definition page."""

    def __init__(self, organisations, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.organisations = organisations
        self.main_widget = SchematisationNameWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.registerField("schematisation_name*", self.main_widget.le_schematisation_name)
        self.registerField("from_geopackage", self.main_widget.rb_existing_geopackage)
        self.registerField("geopackage_path", self.main_widget.le_geopackage_path)
        self.main_widget.rb_existing_geopackage.toggled.connect(self.update_pages_order)
        self.main_widget.le_schematisation_name.textChanged.connect(self.update_pages_order)
        self.main_widget.le_geopackage_path.textChanged.connect(self.update_pages_order)
        self.adjustSize()

    def update_pages_order(self):
        """Check if user wants to use an existing GeoPackage and finalize the wizard, if needed."""
        if self.main_widget.rb_existing_geopackage.isChecked():
            self.main_widget.le_geopackage_path.setEnabled(True)
            self.main_widget.btn_browse_geopackage.setEnabled(True)
            if self.field("geopackage_path"):
                self.setFinalPage(True)
        else:
            self.main_widget.le_geopackage_path.setEnabled(False)
            self.main_widget.btn_browse_geopackage.setEnabled(False)
            self.setFinalPage(False)
        self.completeChanged.emit()

    def nextId(self):
        if self.main_widget.rb_existing_geopackage.isChecked() and self.field("geopackage_path"):
            return -1
        else:
            return 1

    def isComplete(self):
        if self.field("schematisation_name") and (
            self.main_widget.rb_new_geopackage.isChecked()
            or (self.main_widget.rb_existing_geopackage.isChecked() and self.field("geopackage_path"))
        ):
            return True

        else:
            return False


class SchematisationExplainPage(QWizardPage):
    """New schematisation explanation page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = SchematisationExplainWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class SchematisationSettingsPage(QWizardPage):
    """New schematisation settings definition page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = SchematisationSettingsWidget(self)
        self.settings_are_valid = False
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()

    def validatePage(self):
        """Overriding page validation logic."""
        warning_messages = []
        self.settings_are_valid = True
        # Check non-zero settings
        non_zero_required_widgets = [
            ("Simulation timestep", self.main_widget.time_step),
        ]
        if self.main_widget.use_2d_flow_group.isChecked():
            non_zero_required_widgets.append(("Computational Cell Size", self.main_widget.minimum_cell_size))
            if not self.main_widget.friction_coefficient_file.filePath():
                non_zero_required_widgets.append(
                    ("Global 2D friction coefficient", self.main_widget.friction_coefficient)
                )
        invalid_zero_settings = []
        for setting_name, setting_widget in non_zero_required_widgets:
            if not setting_widget.value() > 0:
                invalid_zero_settings.append(setting_name)
        if invalid_zero_settings:
            self.settings_are_valid = False
            warn = "\n".join(
                f"'{setting_name}' value have to be greater than 0" for setting_name in invalid_zero_settings
            )
            warning_messages.append(warn)
        # Check the validity of the raster paths
        valid_path_required_widgets = []
        if self.main_widget.use_2d_flow_group.isChecked():
            if self.main_widget.dem_file.filePath():
                valid_path_required_widgets.append(("DEM", self.main_widget.dem_file))
            if self.main_widget.friction_coefficient.value() == 0.0:
                valid_path_required_widgets.append(("friction", self.main_widget.friction_coefficient_file))
        invalid_path_settings = []
        for setting_name, setting_widget in valid_path_required_widgets:
            raster_filepath = Path(setting_widget.filePath())
            if not os.path.exists(raster_filepath) or raster_filepath.suffix.lower() not in {".tif", ".tiff"}:
                invalid_path_settings.append(setting_name)
        if invalid_path_settings:
            self.settings_are_valid = False
            warn = "\n".join(
                f"Chosen {setting_name} file does not exist or is not a GeoTIFF (.tif or .tiff)"
                for setting_name in invalid_path_settings
            )
            warning_messages.append(warn)
        if warning_messages:
            self.parent_wizard.plugin_dock.communication.show_warn("\n".join(warning_messages))
        return self.settings_are_valid


class NewSchematisationWizard(QWizard):
    """New schematisation wizard."""

    def __init__(self, plugin_dock, parent=None):
        super().__init__(parent)
        self.settings = QSettings()
        self.setWizardStyle(QWizard.ClassicStyle)
        self.plugin_dock = plugin_dock
        self.working_dir = self.plugin_dock.plugin_settings.working_dir
        self.tc = ThreediCalls(self.plugin_dock.threedi_api)
        self.new_schematisation = None
        self.new_local_schematisation = None
        self.schematisation_name_page = SchematisationNamePage(self.plugin_dock.organisations, self)
        self.schematisation_explain_page = SchematisationExplainPage(self)
        self.schematisation_settings_page = SchematisationSettingsPage(self)
        self.addPage(self.schematisation_name_page)
        self.addPage(self.schematisation_explain_page)
        self.addPage(self.schematisation_settings_page)
        self.setButtonText(QWizard.FinishButton, "Create schematisation")
        self.finish_btn = self.button(QWizard.FinishButton)
        self.finish_btn.clicked.connect(self.create_schematisation)
        self.cancel_btn = self.button(QWizard.CancelButton)
        self.cancel_btn.clicked.connect(self.cancel_wizard)
        self.setWindowTitle("New schematisation")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setOption(QWizard.HaveNextButtonOnLastPage, False)
        self.resize(self.settings.value("threedi/new_schematisation_wizard_size", QSize(790, 700)))

    def create_schematisation(self):
        if self.schematisation_name_page.field("from_geopackage"):
            self.create_schematisation_from_geopackage()
        else:
            self.create_new_schematisation()

    def create_new_schematisation(self):
        """Get settings from the wizard and create new schematisation (locally and remotely)."""
        if not self.schematisation_settings_page.settings_are_valid:
            return
        name, description, tags, owner = self.schematisation_name_page.main_widget.get_new_schematisation_data()
        schematisation_settings = self.schematisation_settings_page.main_widget.collect_new_schematisation_settings()
        raster_filepaths = self.schematisation_settings_page.main_widget.raster_filepaths()
        try:
            schematisation = self.tc.create_schematisation(name, owner, tags=tags, meta={"description": description})
            local_schematisation = LocalSchematisation(
                self.working_dir, schematisation.id, name, parent_revision_number=0, create=True
            )
            wip_revision = local_schematisation.wip_revision

            schematisation_filename = f"{name}.gpkg"
            geopackage_filepath = os.path.join(wip_revision.schematisation_dir, schematisation_filename)
            empty_db = ThreediDatabase(geopackage_filepath)
            empty_db.schema.upgrade(epsg_code_override=schematisation_settings["model_settings"]["epsg_code"])

            for raster_filepath in raster_filepaths:
                if raster_filepath:
                    new_raster_filepath = os.path.join(wip_revision.raster_dir, os.path.basename(raster_filepath))
                    shutil.copyfile(raster_filepath, new_raster_filepath)
            for table_name, table_settings in schematisation_settings.items():
                table_layer = geopackage_layer(wip_revision.schematisation_db_filepath, table_name)
                table_layer.startEditing()
                table_fields = table_layer.fields()
                table_fields_names = {f.name() for f in table_fields}
                # Note that this assumes that all columns have the same length!!!
                nrows = len(list(table_settings.values())[0]) if isinstance(list(table_settings.values())[0],
                                                                            list) else 1
                for i in range(nrows):
                    new_settings_feat = QgsFeature(table_fields)
                    for field_name, field_value in table_settings.items():
                        if field_name in table_fields_names:
                            if isinstance(field_value, list):
                                new_settings_feat[field_name] = field_value[i]
                            else:
                                new_settings_feat[field_name] = field_value
                    table_layer.addFeature(new_settings_feat)
                success = table_layer.commitChanges()

                if not success:
                    commit_errors = table_layer.commitErrors()
                    errors_str = "\n".join(commit_errors)
                    error = CommitErrors(f"{table_name} commit errors:\n{errors_str}")
                    raise error
            time.sleep(0.5)
            self.new_schematisation = schematisation
            self.new_local_schematisation = local_schematisation
            msg = f"Schematisation '{name} ({schematisation.id})' created!"
            self.plugin_dock.communication.bar_info(msg, log_text_color=QColor(Qt.darkGreen))
        except ApiException as e:
            self.new_schematisation = None
            self.new_local_schematisation = None
            error_msg = extract_error_message(e)
            self.plugin_dock.communication.bar_error(error_msg, log_text_color=QColor(Qt.red))
        except Exception as e:
            self.new_schematisation = None
            self.new_local_schematisation = None
            error_msg = f"Error: {e}"
            self.plugin_dock.communication.bar_error(error_msg, log_text_color=QColor(Qt.red))

    @staticmethod
    def get_paths_from_geopackage(geopackage_path):
        """Search GeoPackage database tables for attributes with file paths."""
        paths = defaultdict(dict)
        for table_name, raster_info in SchematisationRasterReferences.raster_reference_tables().items():
            settings_fields = list(raster_info.keys())
            settings_lyr = geopackage_layer(geopackage_path, table_name)
            if not settings_lyr.isValid():
                raise GeoPackageError(f"'{table_name}' table could not be loaded from {geopackage_path}")
            try:
                set_feat = next(settings_lyr.getFeatures())
            except StopIteration:
                continue
            for field_name in settings_fields:
                field_value = set_feat[field_name]
                paths[table_name][field_name] = field_value if field_value else None
        return paths

    def create_schematisation_from_geopackage(self):
        """Get settings from existing GeoPackage and create new schematisation (locally and remotely)."""
        try:
            name, description, tags, owner = self.schematisation_name_page.main_widget.get_new_schematisation_data()
            schematisation = self.tc.create_schematisation(name, owner, tags=tags, meta={"description": description})
            local_schematisation = LocalSchematisation(
                self.working_dir, schematisation.id, name, parent_revision_number=0, create=True
            )
            wip_revision = local_schematisation.wip_revision
            sqlite_filename = f"{name}.gpkg"
            geopackage_filepath = os.path.join(wip_revision.schematisation_dir, sqlite_filename)
            src_db = self.schematisation_name_page.field("geopackage_path")
            raster_paths = self.get_paths_from_geopackage(src_db)
            src_dir = os.path.dirname(src_db)
            shutil.copyfile(src_db, geopackage_filepath)
            new_paths = defaultdict(dict)
            missing_rasters = []
            for table_name, raster_paths_info in raster_paths.items():
                for raster_name, raster_rel_path in raster_paths_info.items():
                    if not raster_rel_path:
                        continue
                    raster_full_path = os.path.join(src_dir, "rasters", raster_rel_path)
                    if os.path.exists(raster_full_path):
                        new_raster_filepath = os.path.join(wip_revision.raster_dir, os.path.basename(raster_rel_path))
                        shutil.copyfile(raster_full_path, new_raster_filepath)
                        new_paths[table_name][raster_name] = os.path.relpath(
                            new_raster_filepath, wip_revision.schematisation_dir
                        )
                    else:
                        new_paths[table_name][raster_name] = None
                        missing_rasters.append((raster_name, raster_rel_path))
            if missing_rasters:
                missing_rasters.sort(key=itemgetter(0))
                missing_rasters_string = "\n".join(f"{rname}: {rpath}" for rname, rpath in missing_rasters)
                warn_msg = f"Warning: the following raster files where not found:\n{missing_rasters_string}"
                self.plugin_dock.communication.show_warn(warn_msg)
                self.plugin_dock.communication.bar_warn("Schematisation creation aborted!")
                return
            self.new_schematisation = schematisation
            self.new_local_schematisation = local_schematisation
            msg = f"Schematisation '{name} ({schematisation.id})' created!"
            self.plugin_dock.communication.bar_info(msg, log_text_color=QColor(Qt.darkGreen))
        except ApiException as e:
            self.new_schematisation = None
            self.new_local_schematisation = None
            error_msg = extract_error_message(e)
            self.plugin_dock.communication.bar_error(error_msg, log_text_color=QColor(Qt.red))
        except Exception as e:
            self.new_schematisation = None
            self.new_local_schematisation = None
            error_msg = f"Error: {e}"
            self.plugin_dock.communication.bar_error(error_msg, log_text_color=QColor(Qt.red))

    def cancel_wizard(self):
        """Handling canceling wizard action."""
        self.settings.setValue("threedi/new_schematisation_wizard_size", self.size())
        self.reject()
