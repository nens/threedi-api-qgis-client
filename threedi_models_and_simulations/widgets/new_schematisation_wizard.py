# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import os
import shutil
import time
from collections import defaultdict
from operator import itemgetter
from pathlib import Path

from qgis.core import QgsFeature, QgsRasterLayer
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QDate, QSettings, QSize, Qt, QTime
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QGridLayout, QSizePolicy, QWizard, QWizardPage
from threedi_api_client.openapi import ApiException
from threedi_mi_utils import LocalSchematisation

from ..api_calls.threedi_calls import ThreediCalls
from ..utils import EMPTY_DB_PATH, SchematisationRasterReferences, extract_error_message
from ..utils_qgis import execute_sqlite_queries, sqlite_layer
from ..utils_ui import ensure_valid_schema, get_filepath, scan_widgets_parameters

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


class SpatialiteError(Exception):
    pass


class SchematisationNameWidget(uicls_schema_name_page, basecls_schema_name_page):
    """Widget for the Schematisation Name and tags page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.organisations = self.parent_page.organisations
        self.populate_organisations()
        self.btn_browse_spatialite.clicked.connect(self.browse_existing_spatialite)

    def populate_organisations(self):
        """Populating organisations."""
        for org in self.organisations.values():
            self.cbo_organisations.addItem(org.name, org)

    def get_new_schematisation_name_data(self):
        """Return new schematisation name, tags and owner."""
        name = self.le_schematisation_name.text()
        tags = self.le_tags.text()
        organisation = self.cbo_organisations.currentData()
        owner = organisation.unique_id
        return name, tags, owner

    def browse_existing_spatialite(self):
        """Show dialog for choosing an existing Spatialite file path."""
        spatialite_path = get_filepath(self, dialog_title="Select Spatialite file")
        if spatialite_path is not None:
            schema_is_valid = ensure_valid_schema(
                spatialite_path, self.parent_page.parent_wizard.plugin_dock.communication
            )
            if schema_is_valid is True:
                self.le_spatialite_path.setText(spatialite_path)


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
                self.manhole_storage_area_label.setDisabled(True)
                self.manhole_storage_area.setDisabled(True)
            else:
                self.manhole_storage_area_label.setEnabled(True)
                self.manhole_storage_area.setEnabled(True)

    def on_2d_flow_toggled(self, on):
        """Logic for checking/unchecking 2D Flow settings group."""
        if on:
            self.frict_coef_label.setEnabled(True)
            self.frict_coef_file.setEnabled(True)
            self.grid_space.setValue(0.0)
            if self.use_1d_flow_group.isChecked():
                self.manhole_storage_area_label.setDisabled(True)
                self.manhole_storage_area.setDisabled(True)
        else:
            self.frict_coef_label.setDisabled(True)
            self.frict_coef_file.setDisabled(True)
            self.grid_space.setValue(9999.0)
            if self.use_1d_flow_group.isChecked():
                self.manhole_storage_area_label.setEnabled(True)
                self.manhole_storage_area.setEnabled(True)

    def on_dem_file_change(self):
        """Extra logic for changing DEM file path."""
        dem_filepath = self.dem_file.filePath()
        raster_layer = QgsRasterLayer(dem_filepath)
        if raster_layer.isValid():
            raster_crs = raster_layer.crs()
            self.crs.setCrs(raster_crs)

    @property
    def aggregation_settings_queries(self):
        """Aggregation settings query."""
        sql_qry = """
            DELETE FROM v2_aggregation_settings;
            INSERT INTO v2_aggregation_settings(global_settings_id, var_name, flow_variable, aggregation_method, timestep)
            SELECT id, 'pump_discharge_cum', 'pump_discharge', 'cum', output_time_step FROM v2_global_settings
            UNION
            SELECT id, 'lateral_discharge_cum', 'lateral_discharge', 'cum', output_time_step FROM v2_global_settings
            UNION
            SELECT id, 'simple_infiltration_cum', 'simple_infiltration', 'cum', output_time_step FROM v2_global_settings
            UNION
            SELECT id, 'rain_cum', 'rain', 'cum', output_time_step FROM v2_global_settings
            UNION
            SELECT id, 'leakage_cum', 'leakage', 'cum', output_time_step FROM v2_global_settings
            UNION
            SELECT id, 'interception_current', 'interception', 'current', output_time_step FROM v2_global_settings
            UNION
            SELECT id, 'discharge_cum', 'discharge', 'cum', output_time_step FROM v2_global_settings
            UNION
            SELECT id, 'discharge_cum_neg', 'discharge', 'cum_negative', output_time_step FROM v2_global_settings
            UNION
            SELECT id, 'discharge_cum_pos', 'discharge', 'cum_positive', output_time_step FROM v2_global_settings
            UNION
            SELECT id, 'volume_current', 'volume', 'current', output_time_step  FROM v2_global_settings
            UNION
            SELECT id, 'qsss_cum_pos', 'surface_source_sink_discharge', 'cum_positive', output_time_step FROM v2_global_settings
            UNION
            SELECT id, 'qsss_cum_neg', 'surface_source_sink_discharge', 'cum_negative', output_time_step FROM v2_global_settings
            ;"""
        return sql_qry

    @property
    def global_settings_defaults(self):
        """Global settings defaults."""
        defaults = {
            "id": 1,
            "advection_1d": 1,
            "advection_2d": 1,
            "control_group_id": None,
            "dem_file": None,
            "dem_obstacle_detection": 0,
            "dem_obstacle_height": None,
            "dist_calc_points": 1000.0,
            "embedded_cutoff_threshold": 0.05,
            "epsg_code": None,
            "flooding_threshold": 0.0001,
            "frict_avg": 0,
            "frict_coef": None,
            "frict_coef_file": None,
            "frict_type": None,
            "grid_space": 0.0,
            "groundwater_settings_id": None,
            "initial_groundwater_level": None,
            "initial_groundwater_level_file": None,
            "initial_groundwater_level_type": None,
            "initial_waterlevel": -99.0,
            "initial_waterlevel_file": None,
            "interflow_settings_id": None,
            "interception_global": None,
            "interception_file": None,
            "max_interception": None,
            "max_interception_file": None,
            "kmax": 1,
            "manhole_storage_area": None,
            "max_angle_1d_advection": 1.570795,
            "maximum_sim_time_step": None,
            "maximum_table_step_size": None,
            "minimum_sim_time_step": 0.01,
            "name": "default",
            "nr_timesteps": 9999,
            "numerical_settings_id": 1,
            "output_time_step": None,
            "sim_time_step": None,
            "simple_infiltration_settings_id": None,
            "start_date": QDate.fromString("2000-01-01", "yyyy-MM-dd"),
            "start_time": QTime.fromString("00:00:00", "HH:MM:SS"),
            "table_step_size": 0.05,
            "table_step_size_1d": 0.01,
            "timestep_plus": 0,
            "use_0d_inflow": None,
            "use_1d_flow": None,
            "use_2d_flow": None,
            "use_2d_rain": None,
            "water_level_ini_type": None,
            "wind_shielding_file": None,
        }
        return defaults

    @property
    def numerical_settings_defaults(self):
        """Numerical settings defaults."""
        defaults = {
            "id": 1,
            "cfl_strictness_factor_1d": 1.0,
            "cfl_strictness_factor_2d": 1.0,
            "convergence_cg": 0.000000001,
            "convergence_eps": 0.00001,
            "flow_direction_threshold": 0.000001,
            "frict_shallow_water_correction": None,
            "general_numerical_threshold": 0.00000001,
            "integration_method": 0,
            "limiter_grad_1d": 1,
            "limiter_grad_2d": None,
            "limiter_slope_crossectional_area_2d": None,
            "limiter_slope_friction_2d": None,
            "max_degree": None,
            "max_nonlin_iterations": 20,
            "minimum_friction_velocity": 0.005,
            "minimum_surface_area": 0.00000001,
            "precon_cg": 1,
            "preissmann_slot": 0.0,
            "pump_implicit_ratio": 1.0,
            "thin_water_layer_definition": None,
            "use_of_cg": 20,
            "use_of_nested_newton": None,
        }
        return defaults

    @property
    def settings_tables_defaults(self):
        """Settings tables defaults map."""
        tables_defaults = {
            "v2_global_settings": self.global_settings_defaults,
            "v2_numerical_settings": self.numerical_settings_defaults,
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
        user_settings["advection_1d"] = 1 if use_1d_checked else 0
        user_settings["advection_2d"] = 1 if use_2d_checked else 0
        if use_2d_checked:
            dem_file = os.path.basename(user_settings["dem_file"])
            user_settings["dem_file"] = f"rasters/{dem_file}" if dem_file else None
            sloping_checked = user_settings["frict_shallow_water_correction_sloping"]
            user_settings["frict_shallow_water_correction"] = 3 if sloping_checked else 0
            user_settings["limiter_grad_2d"] = 0 if sloping_checked else 1
            user_settings["limiter_slope_crossectional_area_2d"] = 3 if sloping_checked else 0
            user_settings["limiter_slope_friction_2d"] = 1 if sloping_checked else 0
            user_settings["limiter_slope_friction_2d"] = 1 if sloping_checked else 0
            user_settings["thin_water_layer_definition"] = 0.1 if sloping_checked else None
        frict_type_text = user_settings["frict_type_text"]
        user_settings["frict_type"] = int(frict_type_text.split(":")[0])
        frict_coef_file = os.path.basename(user_settings["frict_coef_file"])
        user_settings["frict_coef_file"] = f"rasters/{frict_coef_file}" if frict_coef_file else None
        if not use_1d_checked or use_2d_checked:
            user_settings["manhole_storage_area"] = None
        sim_time_step = user_settings["sim_time_step"]
        output_time_step_text = user_settings["output_time_step_text"]
        output_time_step_map = {"0-3 hours": 300, "3-12 hours": 900, "12-24 hours": 1800, "> 24 hours": 3600}
        suggested_ots = output_time_step_map[output_time_step_text]
        out_timestep_mod = suggested_ots % sim_time_step
        output_time_step = suggested_ots + (sim_time_step - out_timestep_mod) if out_timestep_mod else suggested_ots
        user_settings["output_time_step"] = output_time_step
        number_of_time_step_map = {
            "0-3 hours": 3 * 3600,
            "3-12 hours": 12 * 3600,
            "12-24 hours": 24 * 3600,
            "> 24 hours": 48 * 3600,
        }
        suggested_nts = number_of_time_step_map[output_time_step_text]
        num_timesteps_mod = suggested_nts % sim_time_step
        timesteps_duration = suggested_nts + (sim_time_step - num_timesteps_mod) if num_timesteps_mod else suggested_nts
        user_settings["nr_timesteps"] = timesteps_duration // sim_time_step
        if self.use_0d_inflow_group.isChecked():
            use_0d_inflow_surfaces = user_settings["use_0d_inflow_surfaces"]
            user_settings["use_0d_inflow"] = 2 if use_0d_inflow_surfaces else 1
        else:
            user_settings["use_0d_inflow"] = 0
        user_settings["use_1d_flow"] = 1 if use_1d_checked else 0
        user_settings["use_2d_flow"] = 1 if use_2d_checked else 0
        user_settings["use_2d_rain"] = 1 if use_2d_checked else 0
        user_settings["use_of_nested_newton"] = 1 if use_1d_checked else 0
        if use_1d_checked and not use_2d_checked:
            max_degree = 700
        elif use_1d_checked and use_2d_checked:
            max_degree = 7
        else:
            max_degree = 5
        user_settings["max_degree"] = max_degree
        return user_settings

    def raster_filepaths(self):
        """Get raster filepaths."""
        dem_file = self.dem_file.filePath()
        frict_coef_file = self.frict_coef_file.filePath()
        return dem_file, frict_coef_file

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
        self.registerField("from_spatialite", self.main_widget.rb_existing_spatialite)
        self.registerField("spatialite_path", self.main_widget.le_spatialite_path)
        self.main_widget.rb_existing_spatialite.toggled.connect(self.update_pages_order)
        self.main_widget.le_schematisation_name.textChanged.connect(self.update_pages_order)
        self.main_widget.le_spatialite_path.textChanged.connect(self.update_pages_order)
        self.adjustSize()

    def update_pages_order(self):
        """Check if user wants to use an existing Spatialite and finalize the wizard, if needed."""
        if self.main_widget.rb_existing_spatialite.isChecked():
            self.main_widget.le_spatialite_path.setEnabled(True)
            self.main_widget.btn_browse_spatialite.setEnabled(True)
            if self.field("spatialite_path"):
                self.setFinalPage(True)
        else:
            self.main_widget.le_spatialite_path.setEnabled(False)
            self.main_widget.btn_browse_spatialite.setEnabled(False)
            self.setFinalPage(False)
        self.completeChanged.emit()

    def nextId(self):
        if self.main_widget.rb_existing_spatialite.isChecked() and self.field("spatialite_path"):
            return -1
        else:
            return 1

    def isComplete(self):
        if self.field("schematisation_name") and (
            self.main_widget.rb_new_spatialite.isChecked()
            or (self.main_widget.rb_existing_spatialite.isChecked() and self.field("spatialite_path"))
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
            ("Simulation timestep", self.main_widget.sim_time_step),
        ]
        if self.main_widget.use_2d_flow_group.isChecked():
            non_zero_required_widgets.append(("Computational Cell Size", self.main_widget.grid_space))
            if not self.main_widget.frict_coef_file.filePath():
                non_zero_required_widgets.append(("Global 2D friction coefficient", self.main_widget.frict_coef))
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
            if self.main_widget.frict_coef.value() == 0.0:
                valid_path_required_widgets.append(("friction", self.main_widget.frict_coef_file))
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
        if self.schematisation_name_page.field("from_spatialite"):
            self.create_schematisation_from_spatialite()
        else:
            self.create_new_schematisation()

    def create_new_schematisation(self):
        """Get settings from the wizard and create new schematisation (locally and remotely)."""
        if not self.schematisation_settings_page.settings_are_valid:
            return
        name, tags, owner = self.schematisation_name_page.main_widget.get_new_schematisation_name_data()
        schematisation_settings = self.schematisation_settings_page.main_widget.collect_new_schematisation_settings()
        raster_filepaths = self.schematisation_settings_page.main_widget.raster_filepaths()
        aggregation_settings_queries = self.schematisation_settings_page.main_widget.aggregation_settings_queries
        try:
            schematisation = self.tc.create_schematisation(name, owner, tags=tags)
            local_schematisation = LocalSchematisation(
                self.working_dir, schematisation.id, name, parent_revision_number=0, create=True
            )
            wip_revision = local_schematisation.wip_revision
            sqlite_filename = f"{name}.sqlite"
            sqlite_filepath = os.path.join(wip_revision.schematisation_dir, sqlite_filename)
            shutil.copyfile(EMPTY_DB_PATH, sqlite_filepath)
            wip_revision.sqlite_filename = sqlite_filename
            for raster_filepath in raster_filepaths:
                if raster_filepath:
                    new_raster_filepath = os.path.join(wip_revision.raster_dir, os.path.basename(raster_filepath))
                    shutil.copyfile(raster_filepath, new_raster_filepath)
            for table_name, table_settings in schematisation_settings.items():
                table_layer = sqlite_layer(wip_revision.sqlite, table_name, geom_column=None)
                table_layer.startEditing()
                table_fields = table_layer.fields()
                table_fields_names = {f.name() for f in table_fields}
                new_settings_feat = QgsFeature(table_fields)
                for field_name, field_value in table_settings.items():
                    if field_name in table_fields_names:
                        new_settings_feat[field_name] = field_value
                table_layer.addFeature(new_settings_feat)
                success = table_layer.commitChanges()

                if not success:
                    commit_errors = table_layer.commitErrors()
                    errors_str = "\n".join(commit_errors)
                    error = CommitErrors(f"{table_name} commit errors:\n{errors_str}")
                    raise error
            time.sleep(0.5)
            execute_sqlite_queries(wip_revision.sqlite, aggregation_settings_queries)
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
    def get_paths_from_sqlite(sqlite_path):
        """Search SQLite database tables for attributes with file paths."""
        paths = defaultdict(dict)
        for table_name, raster_info in SchematisationRasterReferences.raster_reference_tables().items():
            settings_fields = list(raster_info.keys())
            settings_lyr = sqlite_layer(sqlite_path, table_name, geom_column=None)
            if not settings_lyr.isValid():
                raise SpatialiteError(f"'{table_name}' table could not be loaded from {sqlite_path}")
            try:
                set_feat = next(settings_lyr.getFeatures())
            except StopIteration:
                continue
            for field_name in settings_fields:
                field_value = set_feat[field_name]
                paths[table_name][field_name] = field_value if field_value else None
        return paths

    def create_schematisation_from_spatialite(self):
        """Get settings from existing Spatialite and create new schematisation (locally and remotely)."""
        try:
            name, tags, owner = self.schematisation_name_page.main_widget.get_new_schematisation_name_data()
            schematisation = self.tc.create_schematisation(name, owner, tags=tags)
            local_schematisation = LocalSchematisation(
                self.working_dir, schematisation.id, name, parent_revision_number=0, create=True
            )
            wip_revision = local_schematisation.wip_revision
            sqlite_filename = f"{name}.sqlite"
            sqlite_filepath = os.path.join(wip_revision.schematisation_dir, sqlite_filename)
            src_db = self.schematisation_name_page.field("spatialite_path")
            raster_paths = self.get_paths_from_sqlite(src_db)
            src_dir = os.path.dirname(src_db)
            shutil.copyfile(src_db, sqlite_filepath)
            wip_revision.sqlite_filename = sqlite_filename
            new_paths = defaultdict(dict)
            missing_rasters = []
            for table_name, raster_paths_info in raster_paths.items():
                for raster_name, raster_rel_path in raster_paths_info.items():
                    if not raster_rel_path:
                        continue
                    raster_full_path = os.path.join(src_dir, raster_rel_path)
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
            for settings_table_name, new_raster_paths_info in new_paths.items():
                settings_layer = sqlite_layer(wip_revision.sqlite, settings_table_name, geom_column=None)
                settings_layer.startEditing()
                s_fields = settings_layer.fields()
                s_feat = next(settings_layer.getFeatures())
                new_values = dict()
                for field_name, field_value in new_raster_paths_info.items():
                    f_idx = s_fields.lookupField(field_name)
                    if f_idx > 0 and field_value is not None:
                        new_values[f_idx] = field_value
                settings_layer.changeAttributeValues(s_feat.id(), new_values)
                success = settings_layer.commitChanges()
                if not success:
                    commit_errors = settings_layer.commitErrors()
                    errors_str = "\n".join(commit_errors)
                    error = CommitErrors(f"{settings_table_name} commit errors:\n{errors_str}")
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

    def cancel_wizard(self):
        """Handling canceling wizard action."""
        self.settings.setValue("threedi/new_schematisation_wizard_size", self.size())
        self.reject()
