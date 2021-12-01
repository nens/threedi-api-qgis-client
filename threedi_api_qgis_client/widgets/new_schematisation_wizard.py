# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import os
import shutil
from collections import defaultdict
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import QSettings, QSize, QDate, QTime, Qt
from qgis.PyQt.QtWidgets import (
    QWizardPage,
    QWizard,
    QGridLayout,
    QSizePolicy,
)
from qgis.core import QgsFeature
from threedi_api_client.openapi import ApiException
from ..utils import make_schematisation_dirs, extract_error_message, EMPTY_DB_PATH
from ..utils_ui import scan_widgets_parameters
from ..utils_qgis import sqlite_layer
from ..api_calls.threedi_calls import ThreediCalls


base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_schema_name_page, basecls_schema_name_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "new_schematisation_wizard", "page_schema_name.ui")
)
uicls_schema_settings_page, basecls_schema_settings_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "new_schematisation_wizard", "page_schema_settings.ui")
)


class SchematisationNameWidget(uicls_schema_name_page, basecls_schema_name_page):
    """Widget for the Schematisation Name and tags page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page

    def get_new_schematisation_name_data(self):
        """Return new schematisation name and tags."""
        name = self.le_schematisation_name.text()
        tags = self.le_tags.text()
        return name, tags


class SchematisationSettingsWidget(uicls_schema_settings_page, basecls_schema_settings_page):
    """Widget for the Schematisation Settings page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page

    @property
    def aggregation_settings_query(self):
        sql_qry = """
            INSERT INTO v2_aggregation_settings(global_settings_id, var_name, flow_variable, aggregation_method, aggregation_in_space, timestep)
            SELECT id, 'pump_discharge_cum', 'pump_discharge', 'cum', 0, output_time_step FROM v2_global_settings
            UNION
            SELECT id, 'lateral_discharge_cum', 'lateral_discharge', 'cum', 0, output_time_step FROM v2_global_settings
            UNION
            SELECT id, 'simple_infiltration_cum', 'simple_infiltration', 'cum', 0, output_time_step FROM v2_global_settings
            UNION
            SELECT id, 'rain_cum', 'rain', 'cum', 0, output_time_step FROM v2_global_settings
            UNION
            SELECT id, 'leakage_cum', 'leakage', 'cum', 0, output_time_step FROM v2_global_settings
            UNION
            SELECT id, 'interception_current', 'interception', 'current', 0, output_time_step FROM v2_global_settings
            UNION
            SELECT id, 'discharge_cum', 'discharge', 'cum', 0, output_time_step FROM v2_global_settings
            UNION
            SELECT id, 'discharge_cum_neg', 'discharge', 'cum_negative', 0, output_time_step FROM v2_global_settings
            UNION
            SELECT id, 'discharge_cum_pos', 'discharge', 'cum_positive', 0, output_time_step FROM v2_global_settings
            UNION
            SELECT id, 'volume_current', 'volume', 'current', 0, output_time_step  FROM v2_global_settings
            UNION
            SELECT id, 'qsss_cum_pos', 'surface_source_sink_discharge', 'cum_positive', 0, output_time_step FROM v2_global_settings
            UNION
            SELECT id, 'qsss_cum_neg', 'surface_source_sink_discharge', 'cum_negative', 0, output_time_step FROM v2_global_settings
            ;
            """
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
            "dem_obstacle_detection": False,
            "dem_obstacle_height": None,
            "dist_calc_points": 1000.0,
            "embedded_cutoff_threshold": 0.05,
            "epsg_code": None,
            "flooding_threshold": 0.0001,
            "frict_avg": 0,
            "frict_coef": None,
            "frict_coef_file": None,
            "frict_type": None,
            "grid_space": None,
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
            "max_angle_1d_advection": 90.0,
            "maximum_sim_time_step": None,
            "minimum_sim_time_step": 0.01,
            "name": "default",
            "nr_timesteps": 9999,
            "numerical_settings_id": 1,
            "output_time_step": None,
            "sim_time_step": None,
            "simple_infiltration_settings_id": None,
            "start_date": QDate.fromString("2000-01-01", "yyyy-MM-dd"),
            "start_time": QTime.fromString("00:00:00", "HH:mm:ss"),
            "table_step_size": None,
            "table_step_size_1d": 0.01,
            "table_step_size_volume_2d": None,
            "timestep_plus": False,
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
            "minimum_friction_velocity": 0.05,
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
        tables_defaults = {
            "v2_global_settings": self.global_settings_defaults,
            "v2_numerical_settings": self.numerical_settings_defaults,
        }
        return tables_defaults

    @property
    def user_input_settings(self):
        user_settings = scan_widgets_parameters(self)
        use_1d_checked = self.use_1d_flow_group.isChecked()
        use_2d_checked = self.use_2d_flow_group.isChecked()
        user_settings["advection_1d"] = 1 if use_1d_checked else 0
        user_settings["advection_2d"] = 1 if use_2d_checked else 0
        user_settings["dem_file"] = user_settings["dem_file"] or None
        frict_type_text = user_settings["frict_type_text"]
        user_settings["frict_type"] = int(frict_type_text.split(":")[0])
        user_settings["frict_coef_file"] = user_settings["frict_coef_file"] or None
        if not (self.use_1d_flow_group.isChecked() and not self.use_2d_flow_group.isChecked()):
            user_settings["manhole_storage_area"] = None
        output_time_step_text = user_settings["output_time_step_text"]
        output_time_step_map = {"0-3 hours": 300, "3-12 hours": 900, "12-24 hours": 1800, "> 24 hours": 3600}
        user_settings["output_time_step"] = output_time_step_map[output_time_step_text]
        if self.use_0d_inflow_group.isChecked():
            use_0d_inflow_surfaces = user_settings["use_0d_inflow_surfaces"]
            user_settings["use_0d_inflow"] = 2 if use_0d_inflow_surfaces else 1
        else:
            user_settings["use_0d_inflow"] = 0
        user_settings["use_1d_inflow"] = 1 if use_1d_checked else 0
        user_settings["use_2d_inflow"] = 1 if use_2d_checked else 0
        user_settings["use_2d_rain"] = 1 if use_2d_checked else 0
        sloping_checked = user_settings["frict_shallow_water_correction_sloping"]
        user_settings["frict_shallow_water_correction"] = 3 if sloping_checked else 0
        user_settings["limiter_grad_2d"] = 0 if sloping_checked else 1
        user_settings["limiter_slope_crossectional_area_2d"] = 3 if sloping_checked else 0
        user_settings["limiter_slope_friction_2d"] = 1 if sloping_checked else 0
        user_settings["limiter_slope_friction_2d"] = 1 if sloping_checked else 0
        user_settings["thin_water_layer_definition"] = 0.1 if sloping_checked else None
        user_settings["use_of_nested_newton"] = 1 if use_1d_checked else 0
        if use_1d_checked and not use_2d_checked:
            max_degree = 700
        elif use_1d_checked and use_2d_checked:
            max_degree = 7
        else:
            max_degree = 5
        user_settings["max_degree"] = max_degree
        return user_settings

    def collect_new_schematisation_settings(self):
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = SchematisationNameWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.registerField("schematisation_name*", self.main_widget.le_schematisation_name)
        self.adjustSize()


class SchematisationSettingsPage(QWizardPage):
    """New schematisation settings definition page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = SchematisationSettingsWidget(self)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class NewSchematisationWizard(QWizard):
    """New schematisation wizard."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.settings = QSettings()
        self.setWizardStyle(QWizard.ClassicStyle)
        self.plugin = plugin
        self.working_dir = self.plugin.plugin_settings.working_dir
        self.tc = ThreediCalls(self.plugin.threedi_api)
        self.new_schematisation = None
        self.schematisation_name_page = SchematisationNamePage(self)
        self.schematisation_settings_page = SchematisationSettingsPage(self)
        self.addPage(self.schematisation_name_page)
        self.addPage(self.schematisation_settings_page)

        self.setButtonText(QWizard.FinishButton, "Create schematisation")
        self.finish_btn = self.button(QWizard.FinishButton)
        self.finish_btn.clicked.connect(self.create_schematisation)
        self.cancel_btn = self.button(QWizard.CancelButton)
        self.cancel_btn.clicked.connect(self.cancel_wizard)
        self.setWindowTitle("New schematisation")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.resize(self.settings.value("threedi/new_schematisation_wizard_size", QSize(1000, 700)))

    def create_schematisation(self):
        name, tags = self.schematisation_name_page.main_widget.get_new_schematisation_name_data()
        schematisation_settings = self.schematisation_settings_page.main_widget.collect_new_schematisation_settings()
        try:
            self.new_schematisation = self.tc.create_schematisation(name, tags=tags)
            schematisation_db_filepath = make_schematisation_dirs(self.working_dir, self.new_schematisation.id, name)
            shutil.copyfile(EMPTY_DB_PATH, schematisation_db_filepath)
            for table_name, table_settings in schematisation_settings.items():
                table_layer = sqlite_layer(schematisation_db_filepath, table_name, geom_column=None)
                table_fields = table_layer.fields()
                new_settings_feat = QgsFeature(table_fields)
        except ApiException as e:
            self.new_schematisation = None
            error_msg = extract_error_message(e)
            self.plugin.communication.bar_error(error_msg, log_text_color=QColor(Qt.red))
        except Exception as e:
            self.new_schematisation = None
            error_msg = f"Error: {e}"
            self.plugin.communication.bar_error(error_msg, log_text_color=QColor(Qt.red))

    def cancel_wizard(self):
        """Handling canceling wizard action."""
        self.settings.setValue("threedi/new_schematisation_wizard_size", self.size())
        self.reject()
