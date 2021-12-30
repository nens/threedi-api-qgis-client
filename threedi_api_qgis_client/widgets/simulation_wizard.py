# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import os
import csv
import time
import pyqtgraph as pg
from dateutil.relativedelta import relativedelta
from datetime import datetime
from copy import deepcopy
from collections import defaultdict
from qgis.PyQt.QtSvg import QSvgWidget
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QColor, QStandardItemModel, QStandardItem, QFont
from qgis.PyQt.QtCore import QSettings, Qt, QSize
from qgis.PyQt.QtWidgets import (
    QWizardPage,
    QWizard,
    QGridLayout,
    QSizePolicy,
    QFileDialog,
    QComboBox,
    QDoubleSpinBox,
    QLineEdit,
)
from threedi_api_client.openapi import ApiException
from ..utils_ui import (
    icon_path,
    set_widget_background_color,
    scan_widgets_parameters,
    set_widgets_parameters,
)
from ..utils import (
    apply_24h_timeseries,
    extract_error_message,
    mmh_to_ms,
    ms_to_mmh,
    mmh_to_mmtimestep,
    mmtimestep_to_mmh,
    write_laterals_to_json,
    upload_file,
    LATERALS_FILE_TEMPLATE,
    DWF_FILE_TEMPLATE,
)
from .custom_items import FilteredComboBox
from ..api_calls.threedi_calls import ThreediCalls


base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_name_page, basecls_name_page = uic.loadUiType(os.path.join(base_dir, "ui", "simulation_wizard", "page_name.ui"))
uicls_duration_page, basecls_duration_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "simulation_wizard", "page_duration.ui")
)
uicls_initial_conds, basecls_initial_conds = uic.loadUiType(
    os.path.join(base_dir, "ui", "simulation_wizard", "page_initial_conditions.ui")
)
uicls_laterals, basecls_laterals = uic.loadUiType(os.path.join(base_dir, "ui", "simulation_wizard", "page_laterals.ui"))
uicls_dwf, basecls_dwf = uic.loadUiType(os.path.join(base_dir, "ui", "simulation_wizard", "page_dwf.ui"))
uicls_breaches, basecls_breaches = uic.loadUiType(os.path.join(base_dir, "ui", "simulation_wizard", "page_breaches.ui"))
uicls_precipitation_page, basecls_precipitation_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "simulation_wizard", "page_precipitation.ui")
)
uicls_wind_page, basecls_wind_page = uic.loadUiType(os.path.join(base_dir, "ui", "simulation_wizard", "page_wind.ui"))
uicls_settings_page, basecls_settings_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "simulation_wizard", "page_settings.ui")
)
uicls_summary_page, basecls_summary_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "simulation_wizard", "page_initiation.ui")
)


CONSTANT = "Constant"
CUSTOM = "Custom"
DESIGN = "Design"
RADAR = "Radar - NL Only"
AREA_WIDE_RAIN = {
    "0": [0.0],
    "1": [0.0],
    "2": [0.0],
    "3": [0.30, 0.60, 0.90, 1.50, 2.10, 2.10, 1.50, 1.20, 1.05, 0.90, 0.75, 0.60, 0.45, 0.30, 0.15],
    "4": [0.15, 0.30, 0.45, 0.60, 0.75, 0.90, 1.05, 1.20, 1.50, 2.10, 2.10, 1.50, 0.90, 0.60, 0.30],
    "5": [0.30, 0.60, 1.50, 2.70, 2.70, 2.10, 1.50, 1.20, 1.05, 0.90, 0.75, 0.60, 0.45, 0.30, 0.15],
    "6": [0.15, 0.30, 0.45, 0.60, 0.75, 0.90, 1.05, 1.20, 1.50, 2.10, 2.70, 2.70, 1.50, 0.60, 0.30],
    "7": [0.6, 1.2, 2.1, 3.3, 3.3, 2.7, 2.1, 1.5, 1.2, 0.9, 0.6, 0.3],
    "8": [0.3, 0.6, 0.9, 1.2, 1.5, 2.1, 2.7, 3.3, 3.3, 2.1, 1.2, 0.6],
    "9": [1.5, 2.7, 4.8, 4.8, 4.2, 3.3, 2.7, 2.1, 1.5, 0.9, 0.6, 0.3],
    "10": [1.8, 3.6, 6.3, 6.3, 5.7, 4.8, 3.6, 2.4, 1.2],
    "11": [5.833333333] * 12,
    "12": [7.5] * 12,
    "13": [6.666666667] * 24,
    # Last 3 designs should use 1 hour timestep.
    "14": [0.208333333] * 48,
    "15": [0.225694444] * 48,
    "16": [0.277777778] * 48,
}

RAIN_LOOKUP = {
    "0": ("", ""),
    "1": ("0.25", "v"),
    "2": ("0.25", "a"),
    "3": ("0.50", "v"),
    "4": ("0.50", "a"),
    "5": ("1.00", "v"),
    "6": ("1.00", "a"),
    "7": ("2.00", "v"),
    "8": ("2.00", "a"),
    "9": ("5.00", "v"),
    "10": ("10.00", "v"),
    "11": ("100.00", "c"),
    "12": ("250.00", "c"),
    "13": ("1000.00", "c"),
    "14": ("100.00", "c"),
    "15": ("250.00", "c"),
    "16": ("1000.00", "c"),
}

RADAR_ID = "d6c2347d-7bd1-4d9d-a1f6-b342c865516f"


class NameWidget(uicls_name_page, basecls_name_page):
    """Widget for the Name page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path("sim_wizard_name.svg"))
        self.svg_widget.setMinimumHeight(75)
        self.svg_widget.setMinimumWidth(700)
        self.svg_lout.addWidget(self.svg_widget)
        self.svg_lout.setAlignment(self.svg_widget, Qt.AlignHCenter)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)


class SimulationDurationWidget(uicls_duration_page, basecls_duration_page):
    """Widget for the Simulation Duration page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path("sim_wizard_duration.svg"))
        self.svg_widget.setMinimumHeight(75)
        self.svg_widget.setMinimumWidth(700)
        self.svg_lout.addWidget(self.svg_widget)
        self.svg_lout.setAlignment(self.svg_widget, Qt.AlignHCenter)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)
        self.date_from.dateTimeChanged.connect(self.update_time_difference)
        self.date_to.dateTimeChanged.connect(self.update_time_difference)
        self.time_from.dateTimeChanged.connect(self.update_time_difference)
        self.time_to.dateTimeChanged.connect(self.update_time_difference)

    def to_datetime(self):
        """Method for QDateTime ==> datetime conversion."""
        date_from = self.date_from.dateTime().toString("yyyy-MM-dd")
        time_from = self.time_from.time().toString("H:m")
        date_to = self.date_to.dateTime().toString("yyyy-MM-dd")
        time_to = self.time_to.time().toString("H:m")
        start = datetime.strptime(f"{date_from} {time_from}", "%Y-%m-%d %H:%M")
        end = datetime.strptime(f"{date_to} {time_to}", "%Y-%m-%d %H:%M")
        return start, end

    def calculate_simulation_duration(self):
        """Method for simulation duration calculations."""
        try:
            start, end = self.to_datetime()
            if start > end:
                start = end
            delta = end - start
            delta_in_seconds = delta.total_seconds()
            if delta_in_seconds < 0:
                delta_in_seconds = 0.0
            return delta_in_seconds
        except ValueError:
            return 0.0

    def update_time_difference(self):
        """Updating label with simulation duration showed in the human readable format."""
        try:
            start, end = self.to_datetime()
            if start > end:
                start = end
            rel_delta = relativedelta(end, start)
            duration = (rel_delta.years, rel_delta.months, rel_delta.days, rel_delta.hours, rel_delta.minutes)
            self.label_total_time.setText("{} years, {} months, {} days, {} hours, {} minutes".format(*duration))
        except ValueError:
            self.label_total_time.setText("Invalid datetime format!")


class InitialConditionsWidget(uicls_initial_conds, basecls_initial_conds):
    """Widget for the Initial Conditions page."""

    def __init__(self, parent_page, load_conditions=False):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path("sim_wizard_initial_con.svg"))
        self.svg_widget.setMinimumHeight(75)
        self.svg_widget.setMinimumWidth(700)
        self.svg_lout.addWidget(self.svg_widget)
        self.svg_lout.setAlignment(self.svg_widget, Qt.AlignHCenter)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)
        self.new_simulations = None
        self.new_simulation_statuses = None
        self.rasters = {}
        self.saved_states = {}
        self.d1_widget.hide()
        self.d2_widget.hide()
        self.groundwater_widget.hide()
        self.cb_1d.stateChanged.connect(self.checkbox_1d_changed)
        self.cb_2d.stateChanged.connect(self.checkbox_2d_changed)
        self.cb_groundwater.stateChanged.connect(self.checkbox_groundwater_changed)
        self.dd_1d.currentIndexChanged.connect(self.dropdown_1d_changed)
        self.dd_2d.currentIndexChanged.connect(self.dropdown_2d_changed)
        self.dd_groundwater.currentIndexChanged.connect(self.dropdown_groundwater_changed)
        self.setup_initial_conditions()
        if load_conditions:
            self.load_conditions_widget.show()
            self.default_init_widget.hide()
        else:
            self.load_conditions_widget.hide()
            self.default_init_widget.show()

    def setup_initial_conditions(self):
        """Setup initial conditions widget."""
        try:
            self.dd_2d.addItem("")
            self.dd_groundwater.addItem("")
            self.cb_saved_states.addItem("")
            tc = ThreediCalls(self.parent_page.parent_wizard.plugin_dock.threedi_api)
            rasters = tc.fetch_3di_model_initial_waterlevels(
                self.parent_page.parent_wizard.model_selection_dlg.current_model.id
            )
            for raster in rasters or []:
                raster_filename = raster.file.filename
                self.rasters[raster_filename] = raster
                self.dd_2d.addItem(raster_filename)
                self.dd_groundwater.addItem(raster_filename)

            states = tc.fetch_3di_model_saved_states(
                self.parent_page.parent_wizard.model_selection_dlg.current_model.id
            )
            for state in states or []:
                state_name = state.name
                self.saved_states[state_name] = state
                self.cb_saved_states.addItem(state_name)
        except ApiException as e:
            self.new_simulations = None
            self.new_simulation_statuses = None
            error_body = e.body
            error_details = error_body["details"] if "details" in error_body else error_body
            error_msg = f"Error: {error_details}"
            self.parent_page.parent_wizard.plugin_dock.communication.bar_error(error_msg, log_text_color=QColor(Qt.red))
        except Exception as e:
            error_msg = f"Error: {e}"
            self.parent_page.parent_wizard.plugin_dock.communication.bar_error(error_msg, log_text_color=QColor(Qt.red))
        self.dd_1d.addItems(["From spatialite", "Global value"])

    def dropdown_1d_changed(self):
        """Handling dropdown menus selection changes."""
        if self.dd_1d.currentText() == "Global value":
            self.sp_1d_global_value.setEnabled(True)
            self.sp_1d_global_value.show()
            self.label_1d_gv.show()
        else:
            self.sp_1d_global_value.setDisabled(True)
            self.sp_1d_global_value.hide()
            self.label_1d_gv.hide()

    def dropdown_2d_changed(self):
        """Handling dropdown menus selection changes."""
        if self.dd_2d.currentIndex() <= 0:
            self.sp_2d_global_value.setEnabled(True)
            self.sp_2d_global_value.show()
            self.label_2d_gv.show()
        else:
            self.sp_2d_global_value.setDisabled(True)
            self.sp_2d_global_value.hide()
            self.label_2d_gv.hide()

    def dropdown_groundwater_changed(self):
        """Handling dropdown menus selection changes."""
        if self.dd_groundwater.currentIndex() <= 0:
            self.sp_gwater_global_value.setEnabled(True)
            self.sp_gwater_global_value.show()
            self.label_gw_gv.show()
        else:
            self.sp_gwater_global_value.setDisabled(True)
            self.sp_gwater_global_value.hide()
            self.label_gw_gv.hide()

    def checkbox_1d_changed(self, value):
        """Handling checkbox state changes."""
        if value == 0:
            self.d1_widget.hide()
        if value == 2:
            self.d1_widget.show()

    def checkbox_2d_changed(self, value):
        """Handling checkbox state changes."""
        if value == 0:
            self.d2_widget.hide()
        if value == 2:
            self.d2_widget.show()

    def checkbox_groundwater_changed(self, value):
        """Handling checkbox state changes."""
        if value == 0:
            self.groundwater_widget.hide()
        if value == 2:
            self.groundwater_widget.show()


class LateralsWidget(uicls_laterals, basecls_laterals):
    """Widget for the Laterals page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path("sim_wizard_laterals.svg"))
        self.svg_widget.setMinimumHeight(75)
        self.svg_widget.setMinimumWidth(700)
        self.svg_lout.addWidget(self.svg_widget)
        self.svg_lout.setAlignment(self.svg_widget, Qt.AlignHCenter)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)
        self.laterals_timeseries = {}
        self.last_uploaded_laterals = None
        self.setup_laterals()
        self.connect_signals()

    def setup_laterals(self):
        """Setup laterals widget."""
        self.overrule_widget.setVisible(False)
        self.cb_type.addItems(["1D", "2D"])

    def connect_signals(self):
        """Connect signals."""
        self.cb_overrule.stateChanged.connect(self.overrule_value_changed)
        self.pb_upload_laterals.clicked.connect(self.load_csv)
        self.pb_use_csv.clicked.connect(self.overrule_with_csv)
        self.cb_type.currentIndexChanged.connect(self.selection_changed)
        self.cb_laterals.currentIndexChanged.connect(self.laterals_change)
        self.cb_interpolate_laterals.stateChanged.connect(self.interpolate_changed)

    def laterals_change(self):
        """Handle dropdown menus selection changes."""
        lat_id = self.cb_laterals.currentText()
        self.il_location.setText(lat_id)

    def interpolate_changed(self):
        """Handle interpolate checkbox."""
        interpolate = self.cb_interpolate_laterals.isChecked()
        for val in self.laterals_timeseries.values():
            val["interpolate"] = interpolate

    def save_laterals(self):
        """Save laterals time series."""
        lat = self.laterals_timeseries.get(self.cb_laterals.currentText())
        lat.values[0] = [float(f) for f in self.il_location.text().split(",")]
        lat.values[1] = [float(f) for f in self.il_discharge.text().split(",")]
        lat.offset(self.sb_offset.value())

    def selection_changed(self, index):
        """Handle dropdown menus selection changes."""
        if index == 0:
            self.laterals_layout.setText("Upload laterals for 1D:")
        if index == 1:
            self.laterals_layout.setText("Upload laterals for 2D:")
        self.il_upload.setText("")
        self.laterals_timeseries.clear()
        self.cb_laterals.clear()
        self.cb_overrule.setChecked(False)

    def load_csv(self):
        """Load laterals from CSV file."""
        values, filename = self.open_upload_dialog()
        if not filename:
            return
        self.il_upload.setText(filename)
        self.laterals_timeseries = values
        for lat in self.laterals_timeseries.keys():
            self.cb_laterals.addItem(lat)

    def overrule_with_csv(self):
        """Overrule laterals with values from CSV file."""
        values, filename = self.open_upload_dialog()
        if not filename:
            return
        laterals = self.laterals_timeseries.get(self.cb_laterals.currentText())
        for lat in values.values():
            laterals.values = lat.values
            return

    def overrule_value_changed(self, value):
        """Handling checkbox state changes."""
        if value == 0:
            self.overrule_widget.setVisible(False)
        if value == 2:
            self.overrule_widget.setVisible(True)

    def get_laterals_data(self, timesteps_in_seconds=False):
        """Get laterals data (timesteps in seconds)."""
        if timesteps_in_seconds is False:
            return self.laterals_timeseries
        laterals_data = deepcopy(self.laterals_timeseries)
        units = self.cbo_lateral_units.currentText()
        if units == "hrs":
            seconds_per_unit = 3600
        elif units == "mins":
            seconds_per_unit = 60
        else:
            seconds_per_unit = 1
        for val in laterals_data.values():
            val["values"] = [[t * seconds_per_unit, v] for (t, v) in val["values"]]
        return laterals_data

    def handle_laterals_header(self, laterals_list, laterals_type, log_error=True):
        """
        Fetch first lateral row and handle potential header.
        Return None if fetch successful or error message if file is empty or have invalid structure.
        """
        error_message = None
        if not laterals_list:
            error_message = "Laterals list is empty!"
            if log_error:
                self.parent_page.parent_wizard.plugin_dock.communication.show_warn(error_message)
            return error_message
        header = laterals_list[0]
        if laterals_type == "1D":
            if len(header) != 3:
                error_message = "Wrong timeseries format for 1D laterals!"
        else:
            if len(header) != 5:
                error_message = "Wrong timeseries format for 2D laterals!"
        if error_message is None:
            try:
                timeseries_candidate = header[-1]
                [[float(f) for f in line.split(",")] for line in timeseries_candidate.split("\n")]
            except ValueError:
                laterals_list.pop(0)
        else:
            if log_error:
                self.parent_page.parent_wizard.plugin_dock.communication.show_warn(error_message)
        return error_message

    def open_upload_dialog(self):
        """Open dialog for selecting CSV file with laterals."""
        last_folder = QSettings().value("threedi/last_laterals_folder", os.path.expanduser("~"), type=str)
        file_filter = "CSV (*.csv );;All Files (*)"
        filename, __ = QFileDialog.getOpenFileName(self, "Laterals Time Series", last_folder, file_filter)
        if len(filename) == 0:
            return None, None
        QSettings().setValue("threedi/last_laterals_folder", os.path.dirname(filename))
        values = {}
        laterals_type = self.cb_type.currentText()
        interpolate = self.cb_interpolate_laterals.isChecked()
        laterals_list = []
        with open(filename, encoding="utf-8-sig") as lateral_file:
            laterals_reader = csv.reader(lateral_file)
            laterals_list += list(laterals_reader)
        error_msg = self.handle_laterals_header(laterals_list, laterals_type)
        if error_msg is not None:
            return None, None
        if laterals_type == "1D":
            for lat_id, connection_node_id, timeseries in laterals_list:
                try:
                    vals = [[float(f) for f in line.split(",")] for line in timeseries.split("\n")]
                    lateral = {
                        "values": vals,
                        "units": "m3/s",
                        "point": None,
                        "connection_node": int(connection_node_id),
                        "id": int(lat_id),
                        "offset": 0,
                        "interpolate": interpolate,
                    }
                    values[lat_id] = lateral
                    self.last_uploaded_laterals = lateral
                except ValueError:
                    continue
        else:
            for x, y, ltype, lat_id, timeseries in laterals_list:
                try:
                    vals = [[float(f) for f in line.split(",")] for line in timeseries.split("\n")]
                    point = {"type": "Point", "coordinates": [float(x), float(y)]}
                    lateral = {
                        "values": vals,
                        "units": "m3/s",
                        "point": point,
                        "id": int(lat_id),
                        "offset": 0,
                        "interpolate": interpolate,
                    }
                    values[lat_id] = lateral
                    self.last_uploaded_laterals = lateral
                except ValueError:
                    continue
        return values, filename


class DWFWidget(uicls_dwf, basecls_dwf):
    """Widget for the Dry Weather Flow page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path("sim_wizard_dwf.svg"))
        self.svg_widget.setMinimumHeight(75)
        self.svg_widget.setMinimumWidth(700)
        self.svg_lout.addWidget(self.svg_widget)
        self.svg_lout.setAlignment(self.svg_widget, Qt.AlignHCenter)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)
        self.dwf_timeseries = {}
        self.last_uploaded_dwf = None
        self.connect_signals()

    def connect_signals(self):
        """Connect signals."""
        self.pb_upload_dwf.clicked.connect(self.load_csv)

    def interpolate_changed(self):
        """Handle interpolate checkbox."""
        interpolate = self.cb_interpolate_dwf.isChecked()
        for val in self.dwf_timeseries.values():
            val["interpolate"] = interpolate

    def get_dwf_data(self, timeseries24=False):
        """Get Dry Weather Flow data (timesteps in seconds)."""
        if timeseries24 and self.cb_24h.isChecked():
            seconds_in_day = 86400
            dwf_data = deepcopy(self.dwf_timeseries)
            start, end = self.parent_page.parent_wizard.duration_page.main_widget.to_datetime()
            for val in dwf_data.values():
                current_values = val["values"]
                if current_values[-1][0] < seconds_in_day:
                    raise ValueError("Last timestep does not match 24 hour Dry Weather Timeseries format.")
                new_values = apply_24h_timeseries(start, end, current_values)
                val["values"] = new_values
            return dwf_data
        else:
            return self.dwf_timeseries

    def load_csv(self):
        """Load DWF CSV file."""
        values, filename = self.open_upload_dialog()
        if not filename:
            return
        self.dwf_upload.setText(filename)
        self.dwf_timeseries = values

    def handle_dwf_laterals_header(self, dwf_laterals_list, log_error=True):
        """
        Fetch first DWF lateral row and handle potential header.
        Return None if fetch successful or error message if file is empty or have invalid structure.
        """
        error_message = None
        if not dwf_laterals_list:
            error_message = "Dry Weather Flow timeseries list is empty!"
            if log_error:
                self.parent_page.parent_wizard.plugin_dock.communication.show_warn(error_message)
            return error_message
        header = dwf_laterals_list[0]
        if len(header) != 3:
            error_message = "Wrong timeseries format for Dry Weather Flow!"
        if error_message is None:
            try:
                timeseries_candidate = header[-1]
                [[float(f) for f in line.split(",")] for line in timeseries_candidate.split("\n")]
            except ValueError:
                dwf_laterals_list.pop(0)
        else:
            if log_error:
                self.parent_page.parent_wizard.plugin_dock.communication.show_warn(error_message)
        return error_message

    def open_upload_dialog(self):
        """Open dialog for selecting CSV file with Dry Weather Flow."""
        last_folder = QSettings().value("threedi/last_dwf_folder", os.path.expanduser("~"), type=str)
        file_filter = "CSV (*.csv );;All Files (*)"
        filename, __ = QFileDialog.getOpenFileName(self, "Dry Weather Flow Time Series", last_folder, file_filter)
        if len(filename) == 0:
            return None, None
        QSettings().setValue("threedi/last_dwf_folder", os.path.dirname(filename))
        values = {}
        interpolate = self.cb_interpolate_dwf.isChecked()
        dwf_laterals_list = []
        with open(filename, encoding="utf-8-sig") as dwf_file:
            dwf_reader = csv.reader(dwf_file)
            dwf_laterals_list += list(dwf_reader)
        error_msg = self.handle_dwf_laterals_header(dwf_laterals_list)
        if error_msg is not None:
            return None, None
        for dwf_id, connection_node_id, timeseries in dwf_laterals_list:
            try:
                vals = [[float(f) for f in line.split(",")] for line in timeseries.split("\n")]
                dwf = {
                    "values": vals,
                    "units": "m3/s",
                    "point": None,
                    "connection_node": int(connection_node_id),
                    "id": int(dwf_id),
                    "offset": 0,
                    "interpolate": interpolate,
                }
                values[dwf_id] = dwf
                self.last_uploaded_dwf = dwf
            except ValueError:
                continue
        return values, filename


class BreachesWidget(uicls_breaches, basecls_breaches):
    """Widget for the Breaches page."""

    SECONDS_MULTIPLIERS = {"s": 1, "mins": 60, "hrs": 3600}

    def __init__(self, parent_page, initial_conditions=None):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path("sim_wizard_breaches.svg"))
        self.svg_widget.setMinimumHeight(75)
        self.svg_widget.setMinimumWidth(700)
        self.svg_lout.addWidget(self.svg_widget)
        self.svg_lout.setAlignment(self.svg_widget, Qt.AlignHCenter)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)
        self.values = dict()
        self.breaches_layer = parent_page.parent_wizard.model_selection_dlg.breaches_layer
        self.dd_breach_id = FilteredComboBox(self)
        self.breach_lout.addWidget(self.dd_breach_id)
        self.dd_breach_id.currentIndexChanged.connect(self.write_values_into_dict)
        self.dd_simulation.currentIndexChanged.connect(self.simulation_changed)
        self.dd_units.currentIndexChanged.connect(self.write_values_into_dict)
        self.sb_duration.valueChanged.connect(self.write_values_into_dict)
        self.sb_width.valueChanged.connect(self.write_values_into_dict)
        self.sp_start_after.valueChanged.connect(self.write_values_into_dict)
        if initial_conditions.multiple_simulations and initial_conditions.simulations_difference == "breaches":
            self.simulation_widget.show()
        else:
            self.simulation_widget.hide()
        self.dd_simulation.addItems(initial_conditions.simulations_list)
        self.setup_breaches()

    def setup_breaches(self):
        """Setup breaches data with corresponding vector layer."""
        cached_breaches = self.parent_page.parent_wizard.model_selection_dlg.current_model_breaches
        if cached_breaches is not None:
            if self.breaches_layer.selectedFeatureCount() > 0:
                first_id = [str(feat["content_pk"]) for feat in self.breaches_layer.selectedFeatures()][0]
            else:
                first_id = None
            breaches_ids = [str(feat["content_pk"]) for feat in self.breaches_layer.getFeatures()]
            breaches_ids.sort(key=lambda i: int(i))
            self.dd_breach_id.addItems(breaches_ids)
            if first_id is not None:
                self.dd_breach_id.setCurrentText(first_id)
        self.write_values_into_dict()

    def write_values_into_dict(self):
        """Store current widget values."""
        simulation = self.dd_simulation.currentText()
        breach_id = self.dd_breach_id.currentText()
        duration = self.sb_duration.value()
        width = self.sb_width.value()
        units = self.dd_units.currentText()
        offset = self.sp_start_after.value()
        self.values[simulation] = {
            "breach_id": breach_id,
            "width": width,
            "duration": duration,
            "units": units,
            "offset": offset,
        }
        if self.breaches_layer is not None:
            self.parent_page.parent_wizard.plugin_dock.iface.setActiveLayer(self.breaches_layer)
            self.breaches_layer.selectByExpression(f'"content_pk"={breach_id}')
            self.parent_page.parent_wizard.plugin_dock.iface.actionZoomToSelected().trigger()

    def simulation_changed(self):
        """Handle simulation change."""
        vals = self.values.get(self.dd_simulation.currentText())
        if vals:
            self.dd_breach_id.setCurrentIndex(self.dd_breach_id.findText(vals.get("breach_id")))
            self.sb_duration.setValue(vals.get("duration"))
            self.sb_width.setValue(vals.get("width"))
            self.dd_units.setCurrentIndex(self.dd_units.findText(vals.get("units")))
            self.sp_start_after.setValue(vals.get("offset"))
        else:
            self.dd_breach_id.setCurrentIndex(0)
            self.sb_duration.setValue(0.1)
            self.sb_width.setValue(10)
            self.dd_units.setCurrentIndex(0)
            self.sp_start_after.setValue(0)

    def get_breaches_data(self):
        """Getting all needed data for adding breaches to the simulation."""
        breach_id = self.dd_breach_id.currentText()
        width = self.sb_width.value()
        duration = self.sb_duration.value()
        units = self.dd_units.currentText()
        offset = self.sp_start_after.value()
        duration_in_units = duration * self.SECONDS_MULTIPLIERS[units]
        breach_data = (
            breach_id,
            width,
            duration_in_units,
            offset,
        )
        return breach_data


class PrecipitationWidget(uicls_precipitation_page, basecls_precipitation_page):
    """Widget for the Precipitation page."""

    SECONDS_MULTIPLIERS = {"s": 1, "mins": 60, "hrs": 3600}
    DESIGN_5_MINUTES_TIMESTEP = 300
    DESIGN_HOUR_TIMESTEP = 3600

    def __init__(self, parent_page, initial_conditions=None):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path("sim_wizard_precipitation.svg"))
        self.svg_widget.setMinimumHeight(75)
        self.svg_widget.setMinimumWidth(700)
        self.svg_lout.addWidget(self.svg_widget)
        self.svg_lout.setAlignment(self.svg_widget, Qt.AlignHCenter)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)
        self.current_units = "hrs"
        self.precipitation_duration = 0
        self.total_precipitation = 0
        self.custom_time_series = defaultdict(list)
        self.design_time_series = defaultdict(list)
        self.cbo_design.addItems([str(i) for i in range(len(RAIN_LOOKUP))])
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(None)
        self.plot_widget.setFixedHeight(80)
        self.plot_bar_graph = None
        self.plot_ticks = None
        self.lout_plot.addWidget(self.plot_widget, 0, 0)
        self.widget_constant.hide()
        self.widget_custom.hide()
        self.widget_design.hide()
        self.widget_radar.hide()
        self.connect_signals()
        self.values = dict()
        if initial_conditions.multiple_simulations and initial_conditions.simulations_difference == "precipitation":
            self.simulation_widget.show()
        else:
            self.simulation_widget.hide()
        self.dd_simulation.addItems(initial_conditions.simulations_list)
        self.plot_precipitation()

    def connect_signals(self):
        """Connecting widgets signals."""
        self.cbo_prec_type.currentIndexChanged.connect(self.precipitation_changed)
        self.sp_intensity.valueChanged.connect(self.plot_precipitation)
        self.start_after_constant_u.currentIndexChanged.connect(self.sync_units)
        self.stop_after_constant_u.currentIndexChanged.connect(self.sync_units)
        self.sp_start_after_constant.valueChanged.connect(self.plot_precipitation)
        self.sp_stop_after_constant.valueChanged.connect(self.plot_precipitation)
        self.pb_upload_rain.clicked.connect(self.set_custom_time_series)
        self.start_after_custom_u.currentIndexChanged.connect(self.sync_units)
        self.sp_start_after_custom.valueChanged.connect(self.plot_precipitation)
        self.cbo_design.currentIndexChanged.connect(self.set_design_time_series)
        self.start_after_design_u.currentIndexChanged.connect(self.sync_units)
        self.sp_start_after_design.valueChanged.connect(self.plot_precipitation)
        self.start_after_radar_u.currentIndexChanged.connect(self.sync_units)
        self.stop_after_radar_u.currentIndexChanged.connect(self.sync_units)
        self.sp_start_after_radar.valueChanged.connect(self.plot_precipitation)
        self.sp_stop_after_radar.valueChanged.connect(self.plot_precipitation)
        self.dd_simulation.currentIndexChanged.connect(self.simulation_changed)
        self.rb_from_csv.toggled.connect(self.change_time_series_source)
        self.rb_from_netcdf.toggled.connect(self.change_time_series_source)
        self.cb_interpolate_rain.stateChanged.connect(self.plot_precipitation)

    def change_time_series_source(self, is_checked):
        """Handling rain time series source change."""
        if is_checked is True:
            self.le_upload_rain.clear()
            self.plot_precipitation()

    def write_values_into_dict(self):
        """Store current widget values."""
        simulation = self.dd_simulation.currentText()
        precipitation_type = self.cbo_prec_type.currentText()
        if precipitation_type == CONSTANT:
            start_after = self.sp_start_after_constant.value()
            start_after_units = self.start_after_constant_u.currentText()
            stop_after = self.sp_stop_after_constant.value()
            stop_after_units = self.stop_after_constant_u.currentText()
            intensity = self.sp_intensity.value()
            self.values[simulation] = {
                "precipitation_type": precipitation_type,
                "start_after": start_after,
                "start_after_units": start_after_units,
                "stop_after": stop_after,
                "stop_after_units": stop_after_units,
                "intensity": intensity,
            }
        elif precipitation_type == CUSTOM:
            start_after = self.sp_start_after_custom.value()
            start_after_units = self.start_after_custom_u.currentText()
            units = self.cbo_units.currentText()
            time_series = self.custom_time_series[simulation]
            time_series_path = self.le_upload_rain.text()
            interpolate = self.cb_interpolate_rain.isChecked()
            from_csv = self.rb_from_csv.isChecked()
            from_netcdf = self.rb_from_netcdf.isChecked()
            self.values[simulation] = {
                "precipitation_type": precipitation_type,
                "start_after": start_after,
                "start_after_units": start_after_units,
                "units": units,
                "time_series": time_series,
                "time_series_path": time_series_path,
                "interpolate": interpolate,
                "from_csv": from_csv,
                "from_netcdf": from_netcdf,
            }
        elif precipitation_type == DESIGN:
            start_after = self.sp_start_after_design.value()
            start_after_units = self.start_after_design_u.currentText()
            design_number = self.cbo_design.currentText()
            design_time_series = self.design_time_series[simulation]
            self.values[simulation] = {
                "precipitation_type": precipitation_type,
                "start_after": start_after,
                "start_after_units": start_after_units,
                "design_number": design_number,
                "time_series": design_time_series,
            }
        elif precipitation_type == RADAR:
            start_after = self.sp_start_after_radar.value()
            start_after_units = self.start_after_radar_u.currentText()
            stop_after = self.sp_stop_after_radar.value()
            stop_after_units = self.stop_after_radar_u.currentText()
            self.values[simulation] = {
                "precipitation_type": precipitation_type,
                "start_after": start_after,
                "start_after_units": start_after_units,
                "stop_after": stop_after,
                "stop_after_units": stop_after_units,
            }

    def simulation_changed(self):
        """Handling simulation change."""
        simulation = self.dd_simulation.currentText()
        vals = self.values.get(simulation)
        if not vals:
            self.cbo_prec_type.setCurrentIndex(self.cbo_prec_type.findText("None"))
            self.le_upload_rain.clear()
            self.cbo_design.setCurrentIndex(0)
            self.plot_precipitation()
            return
        if vals.get("precipitation_type") == CONSTANT:
            self.cbo_prec_type.setCurrentIndex(self.cbo_prec_type.findText(vals.get("precipitation_type")))
            self.sp_start_after_constant.setValue(vals.get("start_after"))
            self.start_after_constant_u.setCurrentIndex(
                self.start_after_constant_u.findText(vals.get("start_after_units"))
            )
            self.sp_stop_after_constant.setValue(vals.get("stop_after"))
            self.stop_after_constant_u.setCurrentIndex(
                self.stop_after_constant_u.findText(vals.get("stop_after_units"))
            )
            self.sp_intensity.setValue(vals.get("intensity"))
        elif vals.get("precipitation_type") == CUSTOM:
            # Temporary disconnect radio buttons signals
            self.rb_from_csv.toggled.disconnect(self.change_time_series_source)
            self.rb_from_netcdf.toggled.disconnect(self.change_time_series_source)
            # Get simulation values
            self.cbo_prec_type.setCurrentIndex(self.cbo_prec_type.findText(vals.get("precipitation_type")))
            self.sp_start_after_custom.setValue(vals.get("start_after"))
            self.start_after_custom_u.setCurrentIndex(self.start_after_custom_u.findText(vals.get("start_after_units")))
            self.cbo_units.setCurrentIndex(self.cbo_units.findText(vals.get("units")))
            self.rb_from_csv.setChecked(vals.get("from_csv", True))
            self.rb_from_netcdf.setChecked(vals.get("from_netcdf", False))
            self.le_upload_rain.setText(vals.get("time_series_path", ""))
            self.custom_time_series[simulation] = vals.get("time_series", [])
            self.cb_interpolate_rain.setChecked(vals.get("interpolate", False))
            # Connect radio buttons signals again
            self.rb_from_csv.toggled.connect(self.change_time_series_source)
            self.rb_from_netcdf.toggled.connect(self.change_time_series_source)
        elif vals.get("precipitation_type") == DESIGN:
            self.cbo_prec_type.setCurrentIndex(self.cbo_prec_type.findText(vals.get("precipitation_type")))
            self.sp_start_after_design.setValue(vals.get("start_after"))
            self.start_after_design_u.setCurrentIndex(self.start_after_design_u.findText(vals.get("start_after_units")))
            design_number = vals.get("design_number")
            self.cbo_design.setCurrentIndex(self.cbo_design.findText(design_number))
            self.design_time_series[simulation] = vals.get("time_series", [])
        elif vals.get("precipitation_type") == RADAR:
            self.cbo_prec_type.setCurrentIndex(self.cbo_prec_type.findText(vals.get("precipitation_type")))
            self.sp_start_after_radar.setValue(vals.get("start_after"))
            self.start_after_radar_u.setCurrentIndex(self.start_after_radar_u.findText(vals.get("start_after_units")))
            self.sp_stop_after_radar.setValue(vals.get("stop_after"))
            self.stop_after_radar_u.setCurrentIndex(self.stop_after_radar_u.findText(vals.get("stop_after_units")))
        self.plot_precipitation()

    def precipitation_changed(self, idx):
        """Changing widgets looks based on currently selected precipitation type."""
        if idx == 1:
            self.widget_constant.show()
            self.widget_custom.hide()
            self.widget_design.hide()
            self.widget_radar.hide()
        elif idx == 2:
            self.widget_constant.hide()
            self.widget_custom.show()
            self.widget_design.hide()
            self.widget_radar.hide()
        elif idx == 3:
            self.widget_constant.hide()
            self.widget_custom.hide()
            self.widget_design.show()
            self.widget_radar.hide()
        elif idx == 4:
            self.widget_constant.hide()
            self.widget_custom.hide()
            self.widget_design.hide()
            self.widget_radar.show()
        else:
            self.widget_constant.hide()
            self.widget_custom.hide()
            self.widget_design.hide()
            self.widget_radar.hide()

        self.refresh_current_units()
        self.plot_precipitation()

    def sync_units(self, idx):
        """Syncing units widgets."""
        current_text = self.cbo_prec_type.currentText()
        if current_text == CONSTANT:
            if self.start_after_constant_u.currentIndex != idx:
                self.start_after_constant_u.setCurrentIndex(idx)
            if self.stop_after_constant_u.currentIndex != idx:
                self.stop_after_constant_u.setCurrentIndex(idx)
            self.current_units = self.start_after_constant_u.currentText()
        elif current_text == CUSTOM:
            self.current_units = self.start_after_custom_u.currentText()
        elif current_text == DESIGN:
            self.current_units = self.start_after_design_u.currentText()
        elif current_text == RADAR:
            if self.start_after_radar_u.currentIndex != idx:
                self.start_after_radar_u.setCurrentIndex(idx)
            if self.stop_after_radar_u.currentIndex != idx:
                self.stop_after_radar_u.setCurrentIndex(idx)
            self.current_units = self.start_after_radar_u.currentText()
        self.plot_precipitation()

    def refresh_current_units(self):
        """Refreshing current units value."""
        current_text = self.cbo_prec_type.currentText()
        if current_text == CONSTANT:
            self.current_units = self.start_after_constant_u.currentText()
        elif current_text == CUSTOM:
            self.current_units = self.start_after_custom_u.currentText()
        elif current_text == DESIGN:
            self.current_units = self.start_after_design_u.currentText()
        elif current_text == RADAR:
            self.current_units = self.start_after_radar_u.currentText()

    def refresh_duration(self):
        """Refreshing precipitation duration in seconds."""
        self.precipitation_duration = self.get_precipitation_duration()

    def duration_in_units(self):
        """Calculating duration in currently selected units."""
        unit_divider = self.SECONDS_MULTIPLIERS[self.current_units]
        duration_in_units = int(self.precipitation_duration / unit_divider)
        return duration_in_units

    def set_custom_time_series(self):
        """Selecting and setting up rain time series from CSV/NetCDF format."""
        from_csv = self.rb_from_csv.isChecked()
        if from_csv:
            file_filter = "CSV (*.csv);;All Files (*)"
        else:
            file_filter = "NetCDF (*.nc);;All Files (*)"
        last_folder = QSettings().value("threedi/last_precipitation_folder", os.path.expanduser("~"), type=str)
        filename, __ = QFileDialog.getOpenFileName(self, "Precipitation Time Series", last_folder, file_filter)
        if len(filename) == 0:
            return
        QSettings().setValue("threedi/last_precipitation_folder", os.path.dirname(filename))
        time_series = []
        simulation = self.dd_simulation.currentText()
        if from_csv:
            with open(filename, encoding="utf-8-sig") as rain_file:
                rain_reader = csv.reader(rain_file)
                units_multiplier = self.SECONDS_MULTIPLIERS["mins"]
                for rtime, rain in rain_reader:
                    # We are assuming that timestep is in minutes, so we are converting it to seconds on the fly.
                    try:
                        time_series.append([float(rtime) * units_multiplier, float(rain)])
                    except ValueError:
                        continue
        self.le_upload_rain.setText(filename)
        self.custom_time_series[simulation] = time_series
        self.plot_precipitation()

    def set_design_time_series(self):
        """Setting time series based on selected design number."""
        simulation = self.dd_simulation.currentText()
        design_id = self.cbo_design.currentText()
        # Make copy of the values and add 0.0 value at the end of series
        series = AREA_WIDE_RAIN[design_id][:]
        series.append(0.0)
        period_txt, type_txt = RAIN_LOOKUP[design_id]
        if type_txt == "c":
            type_full_text = "Constant"
        elif type_txt == "v":
            type_full_text = "Peak at start"
        elif type_txt == "a":
            type_full_text = "Peak at end"
        else:
            type_full_text = type_txt
        self.return_period_lbl.setText(period_txt)
        self.type_lbl.setText(type_full_text)
        # Design precipitation timestep is 5 minutes (300 seconds) or 1 hour (3600 seconds).
        timestep = self.DESIGN_5_MINUTES_TIMESTEP if int(design_id) < 14 else self.DESIGN_HOUR_TIMESTEP
        self.design_time_series[simulation] = [
            [t, v] for t, v in zip(range(0, len(series) * timestep, timestep), series)
        ]
        self.plot_precipitation()

    def get_intensity(self):
        """Getting intensity value for the Constant precipitation type."""
        intensity = self.sp_intensity.value()
        return intensity

    def get_precipitation_offset(self):
        """Calculating precipitation offset in seconds."""
        current_text = self.cbo_prec_type.currentText()
        to_seconds_multiplier = self.SECONDS_MULTIPLIERS[self.current_units]
        if current_text == CONSTANT:
            start = self.sp_start_after_constant.value()
        elif current_text == CUSTOM:
            start = self.sp_start_after_custom.value()
        elif current_text == DESIGN:
            start = self.sp_start_after_design.value()
        elif current_text == RADAR:
            start = self.sp_start_after_radar.value()
        else:
            return 0.0
        offset = start * to_seconds_multiplier
        return offset

    def get_precipitation_duration(self):
        """Calculating precipitation duration in seconds."""
        simulation = self.dd_simulation.currentText()
        current_text = self.cbo_prec_type.currentText()
        if current_text == CONSTANT or current_text == RADAR:
            to_seconds_multiplier = self.SECONDS_MULTIPLIERS[self.current_units]
            if current_text == CONSTANT:
                start = self.sp_start_after_constant.value()
                end = self.sp_stop_after_constant.value()
            else:
                start = self.sp_start_after_radar.value()
                end = self.sp_stop_after_radar.value()
            start_in_seconds = start * to_seconds_multiplier
            end_in_seconds = end * to_seconds_multiplier
            simulation_duration = (
                self.parent_page.parent_wizard.duration_page.main_widget.calculate_simulation_duration()
            )
            if start_in_seconds > simulation_duration:
                start_in_seconds = simulation_duration
            if end_in_seconds == 0 or end_in_seconds > simulation_duration:
                end_in_seconds = simulation_duration
            precipitation_duration = end_in_seconds - start_in_seconds
            if precipitation_duration < 0:
                precipitation_duration = 0
        elif current_text == CUSTOM:
            end_in_seconds = self.custom_time_series[simulation][-1][0] if self.custom_time_series[simulation] else 0
            precipitation_duration = end_in_seconds
        elif current_text == DESIGN:
            end_in_seconds = self.design_time_series[simulation][-1][0] if self.design_time_series[simulation] else 0
            precipitation_duration = end_in_seconds
        else:
            precipitation_duration = 0
        return precipitation_duration

    def get_precipitation_values(self):
        """Calculating precipitation values in 'm/s'."""
        simulation = self.dd_simulation.currentText()
        current_text = self.cbo_prec_type.currentText()
        if current_text == CONSTANT:
            values = mmh_to_ms(self.get_intensity())
        elif current_text == CUSTOM:
            ts = self.custom_time_series[simulation]
            if self.cbo_units.currentText() == "mm/h":
                values = [[t, mmh_to_ms(v)] for t, v in ts]
            else:
                timestep = ts[1][0] - ts[0][0] if len(ts) > 1 else 1
                values = [[t, mmh_to_ms(mmtimestep_to_mmh(v, timestep))] for t, v in ts]
        elif current_text == DESIGN:
            values = [
                [t, mmh_to_ms(mmtimestep_to_mmh(v, self.DESIGN_5_MINUTES_TIMESTEP))]
                for t, v in self.design_time_series[simulation]
            ]
        else:
            values = []
        return values

    def get_precipitation_data(self):
        """Getting all needed data for adding precipitation to the simulation."""
        precipitation_type = self.cbo_prec_type.currentText()
        offset = self.get_precipitation_offset()
        duration = self.get_precipitation_duration()
        units = "m/s"
        values = self.get_precipitation_values()
        start, end = self.parent_page.parent_wizard.duration_page.main_widget.to_datetime()
        interpolate = self.cb_interpolate_rain.isChecked()
        filepath = self.le_upload_rain.text()
        from_csv = self.rb_from_csv.isChecked()
        from_netcdf = self.rb_from_netcdf.isChecked()
        return precipitation_type, offset, duration, units, values, start, interpolate, filepath, from_csv, from_netcdf

    def constant_values(self):
        """Getting plot values for the Constant precipitation."""
        x_values, y_values = [], []
        intensity = self.get_intensity()
        if intensity <= 0:
            return x_values, y_values
        duration_in_units = self.duration_in_units()
        x_values += [x for x in list(range(duration_in_units + 1))]
        y_values += [intensity] * len(x_values)
        return x_values, y_values

    def custom_values(self):
        """Getting plot values for the Custom precipitation."""
        simulation = self.dd_simulation.currentText()
        x_values, y_values = [], []
        if self.rb_from_netcdf.isChecked():
            del self.custom_time_series[simulation][:]
        else:
            units_multiplier = self.SECONDS_MULTIPLIERS[self.current_units]
            for x, y in self.custom_time_series[simulation]:
                x_in_units = x / units_multiplier
                x_values.append(x_in_units)
                y_values.append(y)
        return x_values, y_values

    def design_values(self):
        """Getting plot values for the Design precipitation."""
        simulation = self.dd_simulation.currentText()
        x_values, y_values = [], []
        units_multiplier = self.SECONDS_MULTIPLIERS[self.current_units]
        for x, y in self.design_time_series[simulation]:
            x_in_units = x / units_multiplier
            x_values.append(x_in_units)
            y_values.append(y)
        return x_values, y_values

    def plot_precipitation(self):
        """Setting up precipitation plot."""
        self.refresh_duration()
        self.plot_widget.clear()
        self.plot_label.show()
        self.plot_widget.show()
        self.plot_bar_graph = None
        self.plot_ticks = None
        current_text = self.cbo_prec_type.currentText()
        if current_text == CONSTANT:
            x_values, y_values = self.constant_values()
        elif current_text == CUSTOM:
            x_values, y_values = self.custom_values()
        elif current_text == DESIGN:
            x_values, y_values = self.design_values()
        elif current_text == RADAR:
            x_values, y_values = [], []
            self.plot_widget.hide()
            self.plot_label.hide()
        else:
            self.plot_widget.hide()
            self.plot_label.hide()
            return
        self.write_values_into_dict()
        if len(x_values) < 2:
            return
        # Bar width as time series interval value
        first_time = x_values[0]
        second_time = x_values[1]
        last_time = x_values[-1]
        timestep = second_time - first_time
        # Adding ticks in minutes
        dx = [(value, f"{value:.2f} ({self.current_units})") for value in x_values]
        self.plot_ticks = [[dx[0], dx[-1]]]
        ax = self.plot_widget.getAxis("bottom")
        ax.setTicks(self.plot_ticks)
        self.plot_bar_graph = pg.BarGraphItem(x=x_values, height=y_values, width=timestep, brush=QColor("#1883D7"))
        self.plot_widget.addItem(self.plot_bar_graph)
        if current_text == CONSTANT:
            precipitation_values = y_values[:-1]
        else:
            precipitation_values = y_values
        if current_text == CONSTANT:
            self.total_precipitation = sum(mmh_to_mmtimestep(v, 1, self.current_units) for v in precipitation_values)
        elif current_text == CUSTOM and self.cbo_units.currentText() == "mm/h":
            self.total_precipitation = sum(
                mmh_to_mmtimestep(v, timestep, self.current_units) for v in precipitation_values
            )
        else:
            # This is for 'mm/timestep'
            self.total_precipitation = sum(precipitation_values)
        self.plot_widget.setXRange(first_time, last_time)
        self.plot_widget.setYRange(first_time, max(precipitation_values))


class WindWidget(uicls_wind_page, basecls_wind_page):
    """Widget for the Wind page."""

    SECONDS_MULTIPLIERS = {"s": 1, "mins": 60, "hrs": 3600}

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path("sim_wizard_wind.svg"))
        self.svg_widget.setMinimumHeight(75)
        self.svg_widget.setMinimumWidth(700)
        self.svg_lout.addWidget(self.svg_widget)
        self.svg_lout.setAlignment(self.svg_widget, Qt.AlignHCenter)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)
        self.current_units = "hrs"
        self.wind_duration = 0
        self.custom_wind = []
        self.widget_wind_custom.hide()
        self.connect_signals()

    def connect_signals(self):
        """Connecting widgets signals."""
        self.cbo_wind_type.currentIndexChanged.connect(self.wind_changed)
        self.start_wind_constant_u.currentIndexChanged.connect(self.sync_units)
        self.stop_wind_constant_u.currentIndexChanged.connect(self.sync_units)
        self.pb_upload_wind.clicked.connect(self.set_custom_wind)
        self.start_wind_custom_u.currentIndexChanged.connect(self.sync_units)
        self.sp_direction.valueChanged.connect(self.sync_dial)
        self.wind_dial.valueChanged.connect(self.sync_direction_value)

    def wind_changed(self, idx):
        """Changing widgets looks based on currently selected wind type."""
        if idx == 0:
            self.widget_wind_constant.show()
            self.widget_wind_custom.hide()
        elif idx == 1:
            self.widget_wind_constant.hide()
            self.widget_wind_custom.show()
        else:
            self.widget_wind_constant.hide()
            self.widget_wind_custom.hide()
        self.refresh_current_units()

    def sync_units(self, idx):
        """Syncing units widgets."""
        current_text = self.cbo_wind_type.currentText()
        if current_text == CONSTANT:
            if self.start_wind_constant_u.currentIndex != idx:
                self.start_wind_constant_u.setCurrentIndex(idx)
            if self.stop_wind_constant_u.currentIndex != idx:
                self.stop_wind_constant_u.setCurrentIndex(idx)
            self.current_units = self.start_wind_constant_u.currentText()
        else:
            self.current_units = self.start_wind_custom_u.currentText()

    def sync_dial(self):
        """Syncing dial position with direction value."""
        direction = self.sp_direction.value()
        dial_value = self.wind_dial.value()
        if dial_value != direction:
            self.wind_dial.setValue(direction)

    def sync_direction_value(self):
        """Syncing direction value with dial position."""
        dial_value = self.wind_dial.value()
        direction = self.sp_direction.value()
        if dial_value != direction:
            self.sp_direction.setValue(dial_value)

    def refresh_current_units(self):
        """Refreshing current units value."""
        current_text = self.cbo_wind_type.currentText()
        if current_text == CONSTANT:
            self.current_units = self.start_wind_constant_u.currentText()
        else:
            self.current_units = self.start_wind_custom_u.currentText()

    def set_custom_wind(self):
        """Selecting and setting up wind time series from CSV format."""
        file_filter = "CSV (*.csv);;All Files (*)"
        last_folder = QSettings().value("threedi/last_wind_folder", os.path.expanduser("~"), type=str)
        filename, __ = QFileDialog.getOpenFileName(self, "Wind Time Series", last_folder, file_filter)
        if len(filename) == 0:
            return
        QSettings().setValue("threedi/last_wind_folder", os.path.dirname(filename))
        time_series = []
        with open(filename, encoding="utf-8-sig") as wind_file:
            wind_reader = csv.reader(wind_file)
            units_multiplier = self.SECONDS_MULTIPLIERS["mins"]
            for time, windspeed, direction in wind_reader:
                # We are assuming that timestep is in minutes, so we are converting it to seconds on the fly.
                try:
                    time_series.append([float(time) * units_multiplier, float(windspeed), float(direction)])
                except ValueError:
                    continue
        self.le_upload_wind.setText(filename)
        self.custom_wind = time_series

    def get_wind_offset(self):
        """Calculating wind offset in seconds."""
        current_text = self.cbo_wind_type.currentText()
        to_seconds_multiplier = self.SECONDS_MULTIPLIERS[self.current_units]
        if current_text == CONSTANT:
            start = self.sp_start_wind_constant.value()
        elif current_text == CUSTOM:
            start = self.sp_start_wind_custom.value()
        else:
            return 0.0
        offset = start * to_seconds_multiplier
        return offset

    def get_wind_duration(self):
        """Calculating wind duration in seconds."""
        current_text = self.cbo_wind_type.currentText()
        if current_text == CONSTANT:
            to_seconds_multiplier = self.SECONDS_MULTIPLIERS[self.current_units]
            start = self.sp_start_wind_constant.value()
            end = self.sp_stop_wind_constant.value()
            start_in_seconds = start * to_seconds_multiplier
            end_in_seconds = end * to_seconds_multiplier
            simulation_duration = (
                self.parent_page.parent_wizard.duration_page.main_widget.calculate_simulation_duration()
            )
            if start_in_seconds > simulation_duration:
                start_in_seconds = simulation_duration
            if end_in_seconds == 0 or end_in_seconds > simulation_duration:
                end_in_seconds = simulation_duration
            wind_duration = end_in_seconds - start_in_seconds
            if wind_duration < 0:
                wind_duration = 0
        elif current_text == CUSTOM:
            end_in_seconds = self.custom_wind[-1][0] if self.custom_wind else 0
            wind_duration = end_in_seconds
        else:
            wind_duration = 0
        return wind_duration

    def get_windspeed(self):
        """Getting wind speed value for the Constant precipitation type."""
        windspeed = self.sp_windspeed.value()
        return windspeed

    def get_direction(self):
        """Getting direction value for the Constant wind type."""
        direction = self.sp_direction.value()
        return direction

    def get_drag_coefficient(self):
        """Getting drag coefficient value."""
        current_text = self.cbo_wind_type.currentText()
        if current_text == CONSTANT:
            drag_coefficient = self.sp_dc_constant.value()
        else:
            drag_coefficient = self.sp_dc_custom.value()
        return drag_coefficient

    def get_interpolate_flags(self):
        """Getting interpolate flags values."""
        interpolate_speed = self.cb_interpolate_speed.isChecked()
        interpolate_direction = self.cb_interpolate_direction.isChecked()
        return interpolate_speed, interpolate_direction

    def get_wind_data(self):
        """Getting all needed data for adding wind to the simulation."""
        wind_type = self.cbo_wind_type.currentText()
        offset = self.get_wind_offset()
        duration = self.get_wind_duration()
        speed = self.get_windspeed()
        direction = self.get_direction()
        units = self.cbo_windspeed_u.currentText()
        drag_coeff = self.get_drag_coefficient()
        inter_speed, inter_direction = self.get_interpolate_flags()
        values = self.custom_wind
        return wind_type, offset, duration, speed, direction, units, drag_coeff, inter_speed, inter_direction, values


class SettingsWidget(uicls_settings_page, basecls_settings_page):
    """Widget for the simulation settings page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path("sim_wizard_settings.svg"))
        self.svg_widget.setMinimumHeight(75)
        self.svg_widget.setMinimumWidth(700)
        self.svg_lout.addWidget(self.svg_widget)
        self.svg_lout.setAlignment(self.svg_widget, Qt.AlignHCenter)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)
        self.aggregation_model = QStandardItemModel()
        self.aggregation_tv.setModel(self.aggregation_model)
        self.aggregation_settings_header = ["Flow variable", "Method", "Interval", "Name"]
        self.flow_variables = [
            "water_level",
            "flow_velocity",
            "discharge",
            "volume",
            "pump_discharge",
            "wet_cross_section",
            "lateral_discharge",
            "wet_surface",
            "rain",
            "simple_infiltration",
            "leakage",
            "interception",
            "surface_source_sink_discharge",
        ]
        self.flow_methods = ["min", "max", "avg", "cum", "cum_positive", "cum_negative", "current", "sum"]
        self.connect_signals()
        self.populate_aggregation_settings()

    def connect_signals(self):
        """Connecting widgets signals."""
        self.add_aggregation_entry.clicked.connect(self.add_aggregation_settings_row)
        self.remove_aggregation_entry.clicked.connect(self.remove_aggregation_settings_row)

    def populate_aggregation_settings(self, aggregation_settings_list=None):
        """Populate aggregation settings inside QTreeView."""
        if aggregation_settings_list is not None:
            self.aggregation_model.clear()
        self.aggregation_model.setHorizontalHeaderLabels(self.aggregation_settings_header)
        for i, aggregation_settings in enumerate(aggregation_settings_list or [], start=0):
            row_items = [QStandardItem("") for _ in self.aggregation_settings_header]
            self.aggregation_model.appendRow(row_items)
            self.add_aggregation_settings_widgets(i, aggregation_settings)
        for i in range(len(self.aggregation_settings_header)):
            self.aggregation_tv.resizeColumnToContents(i)

    def add_aggregation_settings_widgets(self, row_number, aggregation_settings=None):
        """Add aggregation settings widgets"""
        segoe_ui_font = QFont("Segoe UI", 8)
        flow_variable_combo = QComboBox()
        flow_variable_combo.setFont(segoe_ui_font)
        flow_variable_combo.addItems(self.flow_variables)

        flow_method_combo = QComboBox()
        flow_method_combo.setFont(segoe_ui_font)
        flow_method_combo.addItems(self.flow_methods)

        interval_spinbox = QDoubleSpinBox()
        interval_spinbox.setFont(segoe_ui_font)
        interval_spinbox.setStyleSheet("QDoubleSpinBox {background-color: white;}")
        interval_spinbox.setDecimals(4)
        interval_spinbox.setMinimum(1.0)
        interval_spinbox.setMaximum(2147483647.0)

        name_line_edit = QLineEdit()
        name_line_edit.setFont(segoe_ui_font)
        name_line_edit.setStyleSheet("QLineEdit {background-color: white;}")

        if aggregation_settings:
            flow_variable_combo.setCurrentText(aggregation_settings["flow_variable"])
            flow_method_combo.setCurrentText(aggregation_settings["method"])
            interval_spinbox.setValue(aggregation_settings["interval"])
            name_line_edit.setText(aggregation_settings["name"] or "")

        self.aggregation_tv.setIndexWidget(self.aggregation_model.index(row_number, 0), flow_variable_combo)
        self.aggregation_tv.setIndexWidget(self.aggregation_model.index(row_number, 1), flow_method_combo)
        self.aggregation_tv.setIndexWidget(self.aggregation_model.index(row_number, 2), interval_spinbox)
        self.aggregation_tv.setIndexWidget(self.aggregation_model.index(row_number, 3), name_line_edit)

    def add_aggregation_settings_row(self):
        """Add aggregation settings row into QTreeView."""
        row_count = self.aggregation_model.rowCount()
        row_items = [QStandardItem("") for _ in self.aggregation_settings_header]
        self.aggregation_model.appendRow(row_items)
        self.add_aggregation_settings_widgets(row_count)

    def remove_aggregation_settings_row(self):
        """Remove selected aggregation settings row from QTreeView."""
        index = self.aggregation_tv.currentIndex()
        if not index.isValid():
            return
        self.aggregation_model.removeRow(index.row())

    def collect_single_settings(self):
        """Get data from the single settings groupboxes."""
        physical_settings = scan_widgets_parameters(self.group_physical, get_combobox_text=False)
        numerical_settings = scan_widgets_parameters(self.group_numerical, get_combobox_text=False)
        time_step_settings = scan_widgets_parameters(self.group_timestep, get_combobox_text=False)
        return physical_settings, numerical_settings, time_step_settings

    def collect_aggregation_settings(self):
        """Get data from the aggregation settings rows."""
        aggregation_settings_list = []
        for row_number in range(self.aggregation_model.rowCount()):
            aggregation_settings = {}
            flow_variable_item = self.aggregation_model.item(row_number, 0)
            flow_variable_index = flow_variable_item.index()
            flow_variable_widget = self.aggregation_tv.indexWidget(flow_variable_index)

            flow_method_item = self.aggregation_model.item(row_number, 1)
            flow_method_index = flow_method_item.index()
            flow_method_widget = self.aggregation_tv.indexWidget(flow_method_index)

            interval_item = self.aggregation_model.item(row_number, 2)
            interval_index = interval_item.index()
            interval_widget = self.aggregation_tv.indexWidget(interval_index)

            name_item = self.aggregation_model.item(row_number, 3)
            name_index = name_item.index()
            name_widget = self.aggregation_tv.indexWidget(name_index)

            aggregation_settings["flow_variable"] = flow_variable_widget.currentText()
            aggregation_settings["method"] = flow_method_widget.currentText()
            aggregation_settings["interval"] = interval_widget.value()
            aggregation_settings["name"] = name_widget.text()
            aggregation_settings_list.append(aggregation_settings)

        return aggregation_settings_list


class SummaryWidget(uicls_summary_page, basecls_summary_page):
    """Widget for the Summary page."""

    def __init__(self, parent_page, initial_conditions=None):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path("sim_wizard_initiation.svg"))
        self.svg_widget.setMinimumHeight(75)
        self.svg_widget.setMinimumWidth(700)
        self.svg_lout.addWidget(self.svg_widget)
        self.svg_lout.setAlignment(self.svg_widget, Qt.AlignHCenter)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(None)
        self.plot_widget.setFixedHeight(80)
        self.lout_plot.addWidget(self.plot_widget, 0, 0)
        self.template_widget.hide()
        self.cb_save_template.stateChanged.connect(self.save_template_state_changed)
        self.dd_simulation.currentIndexChanged.connect(self.simulation_change)
        self.precipitation_widget.hide()
        self.breach_widget.hide()
        self.initial_conditions = initial_conditions
        if initial_conditions.multiple_simulations:
            self.simulation_widget.show()
        else:
            self.simulation_widget.hide()
        self.dd_simulation.addItems(initial_conditions.simulations_list)

    def simulation_change(self):
        """Handle simulation change."""
        if (
            self.initial_conditions.simulations_difference == "precipitation"
            and self.initial_conditions.include_precipitations
        ):
            data = self.parent_page.parent_wizard.precipitation_page.main_widget.values.get(
                self.dd_simulation.currentText()
            )
            self.plot_overview_precipitation()
            if data:
                ptype = data.get("precipitation_type")
                if ptype != RADAR:
                    total_prec_val = self.parent_page.parent_wizard.precipitation_page.main_widget.total_precipitation
                    total_prec = f"{total_prec_val:.1f}"
                else:
                    total_prec = "N/A"
                self.sim_prec_type.setText(ptype)
                self.sim_prec_total.setText(total_prec)
        elif self.initial_conditions.simulations_difference == "breaches" and self.initial_conditions.include_breaches:
            data = self.parent_page.parent_wizard.breaches_page.main_widget.values.get(self.dd_simulation.currentText())
            if data:
                breach_id = data.get("breach_id")
                duration = data.get("duration")
                self.breach_id.setText(breach_id)
                self.duration_breach.setText(str(duration))

    def plot_overview_precipitation(self):
        """Setting up precipitation plot."""
        self.plot_widget.clear()
        self.plot_label.show()
        self.plot_widget.show()
        current_sim_idx = self.dd_simulation.currentIndex()
        self.parent_page.parent_wizard.precipitation_page.main_widget.dd_simulation.setCurrentIndex(current_sim_idx)
        self.parent_page.parent_wizard.precipitation_page.main_widget.plot_precipitation()
        plot_bar_graph = self.parent_page.parent_wizard.precipitation_page.main_widget.plot_bar_graph
        plot_ticks = self.parent_page.parent_wizard.precipitation_page.main_widget.plot_ticks
        if plot_bar_graph is None:
            self.plot_widget.hide()
            self.plot_label.hide()
            return
        height = plot_bar_graph.opts["height"]
        new_bar_graph = pg.BarGraphItem(**plot_bar_graph.opts)
        ax = self.plot_widget.getAxis("bottom")
        ax.setTicks(plot_ticks)
        self.plot_widget.addItem(new_bar_graph)
        ticks = plot_ticks[0]
        first_tick_value, last_tick_value = ticks[0][0], ticks[-1][0]
        self.plot_widget.setXRange(first_tick_value, last_tick_value)
        self.plot_widget.setYRange(first_tick_value, max(height))

    def save_template_state_changed(self, value):
        """Handle template checkbox state change."""
        if value == 0:
            self.template_widget.hide()
        if value == 2:
            self.template_widget.show()


class NamePage(QWizardPage):
    """Simulation name definition page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = NameWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget, 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.registerField("simulation_name*", self.main_widget.le_sim_name)
        self.adjustSize()


class SimulationDurationPage(QWizardPage):
    """Simulation duration definition page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = SimulationDurationWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget, 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class InitialConditionsPage(QWizardPage):
    """Initial condition definition page."""

    def __init__(self, parent=None, load_conditions=False):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = InitialConditionsWidget(self, load_conditions=load_conditions)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class LateralsPage(QWizardPage):
    """Laterals definition page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = LateralsWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class DWFPage(QWizardPage):
    """Dry Weather Flow definition page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = DWFWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class BreachesPage(QWizardPage):
    """Breaches definition page."""

    def __init__(self, parent=None, initial_conditions=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = BreachesWidget(self, initial_conditions=initial_conditions)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class PrecipitationPage(QWizardPage):
    """Precipitation definition page."""

    def __init__(self, parent=None, initial_conditions=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = PrecipitationWidget(self, initial_conditions=initial_conditions)
        layout = QGridLayout()
        layout.addWidget(self.main_widget, 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class WindPage(QWizardPage):
    """Wind definition page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = WindWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class SettingsPage(QWizardPage):
    """Settings definition page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = SettingsWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class SummaryPage(QWizardPage):
    """New simulation summary page."""

    def __init__(self, parent=None, initial_conditions=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = SummaryWidget(self, initial_conditions=initial_conditions)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class SimulationWizard(QWizard):
    """New simulation wizard."""

    def __init__(self, plugin_dock, model_selection_dlg, init_conditions_dlg, parent=None):
        super().__init__(parent)
        self.settings = QSettings()
        self.setWizardStyle(QWizard.ClassicStyle)
        self.model_selection_dlg = model_selection_dlg
        self.init_conditions_dlg = init_conditions_dlg
        init_conditions = self.init_conditions_dlg.initial_conditions
        self.plugin_dock = plugin_dock
        self.name_page = NamePage(self)
        self.duration_page = SimulationDurationPage(self)
        self.addPage(self.name_page)
        self.addPage(self.duration_page)
        if init_conditions.include_initial_conditions:
            self.init_conditions_page = InitialConditionsPage(
                self, load_conditions=init_conditions.load_from_saved_state
            )
            self.addPage(self.init_conditions_page)
        if init_conditions.include_laterals:
            self.laterals_page = LateralsPage(self)
            self.addPage(self.laterals_page)
        if init_conditions.include_dwf:
            self.dwf_page = DWFPage(self)
            self.addPage(self.dwf_page)
        if init_conditions.include_breaches:
            self.breaches_page = BreachesPage(self, initial_conditions=init_conditions)
            self.addPage(self.breaches_page)
        if init_conditions.include_precipitations:
            self.precipitation_page = PrecipitationPage(self, initial_conditions=init_conditions)
            self.addPage(self.precipitation_page)
        if init_conditions.include_wind:
            self.wind_page = WindPage(self)
            self.addPage(self.wind_page)
        self.settings_page = SettingsPage(self)
        self.addPage(self.settings_page)
        self.summary_page = SummaryPage(self, initial_conditions=init_conditions)
        self.addPage(self.summary_page)
        self.currentIdChanged.connect(self.page_changed)
        self.setButtonText(QWizard.FinishButton, "Add to queue")
        self.finish_btn = self.button(QWizard.FinishButton)
        self.finish_btn.clicked.connect(self.run_new_simulation)
        self.cancel_btn = self.button(QWizard.CancelButton)
        self.cancel_btn.clicked.connect(self.cancel_wizard)
        self.new_simulations = None
        self.new_simulation_statuses = None
        self.setWindowTitle("New simulation")
        self.setStyleSheet("background-color:#F0F0F0")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.resize(self.settings.value("threedi/wizard_size", QSize(800, 600)))
        self.first_simulation = init_conditions.simulations_list[0]
        self.init_conditions = init_conditions

    def page_changed(self, page_id):
        """Extra pre-processing triggered by changes of the wizard pages."""
        if page_id == 2 and self.init_conditions.include_precipitations:
            self.precipitation_page.main_widget.plot_precipitation()
        elif isinstance(self.currentPage(), SummaryPage):
            self.set_overview_name()
            self.set_overview_database()
            self.set_overview_duration()
            if self.init_conditions.include_precipitations:
                self.summary_page.main_widget.plot_overview_precipitation()
                self.set_overview_precipitation()
            if self.init_conditions.include_breaches:
                self.set_overview_breaches()

    def set_overview_name(self):
        """Setting up simulation name label in the summary page."""
        name = self.name_page.main_widget.le_sim_name.text()
        self.summary_page.main_widget.sim_name.setText(name)
        self.summary_page.main_widget.template_name.setText(name)

    def set_overview_database(self):
        """Setting up database name label in the summary page."""
        database = self.model_selection_dlg.current_model.name
        self.summary_page.main_widget.sim_database.setText(database)

    def set_overview_duration(self):
        """Setting up simulation duration label in the summary page."""
        duration = self.duration_page.main_widget.label_total_time.text()
        self.summary_page.main_widget.sim_duration.setText(duration)

    def set_overview_precipitation(self):
        """Setting up precipitation labels in the summary page."""
        if self.precipitation_page.main_widget.values.get(self.first_simulation):
            self.summary_page.main_widget.precipitation_widget.show()
            precipitation_type = self.precipitation_page.main_widget.values.get(self.first_simulation).get(
                "precipitation_type"
            )
            total_precipitation = self.precipitation_page.main_widget.total_precipitation
            self.summary_page.main_widget.sim_prec_type.setText(precipitation_type)
            if precipitation_type != RADAR:
                total_precipitation_text = f"{total_precipitation:.0f} mm"
            else:
                total_precipitation_text = "N/A"
            self.summary_page.main_widget.sim_prec_total.setText(total_precipitation_text)

    def set_overview_breaches(self):
        """Setting breaches information in the overview page."""
        if self.breaches_page.main_widget.values.get(self.first_simulation):
            self.summary_page.main_widget.breach_widget.show()
            breach_id = self.breaches_page.main_widget.values.get(self.first_simulation).get("breach_id")
            duration_of_breach = self.breaches_page.main_widget.values.get(self.first_simulation).get("duration")
            self.summary_page.main_widget.breach_id.setText(breach_id)
            self.summary_page.main_widget.duration_breach.setText(str(duration_of_breach))

    def load_template_parameters(self, simulation, settings_overview, events):
        """Loading simulation parameters from the simulation template data."""
        # Simulation attributes
        name_params = {"le_sim_name": simulation.name, "le_tags": ", ".join(simulation.tags)}
        set_widgets_parameters(self.name_page.main_widget, **name_params)
        start_datetime = simulation.start_datetime.strftime("%Y-%m-%dT%H:%M")
        end_datetime = simulation.end_datetime.strftime("%Y-%m-%dT%H:%M")
        start_date, start_time = start_datetime.split("T")
        end_date, end_time = end_datetime.split("T")
        duration_params = {"date_from": start_date, "time_from": start_time, "date_to": end_date, "time_to": end_time}
        set_widgets_parameters(self.duration_page.main_widget, **duration_params)
        # Simulation settings
        ignore_entries = {"id", "simulation_id"}
        physical_settings = {
            k: v for k, v in settings_overview.physical_settings.to_dict().items() if k not in ignore_entries
        }
        numerical_settings = {
            k: v for k, v in settings_overview.numerical_settings.to_dict().items() if k not in ignore_entries
        }
        time_step_settings = {
            k: v for k, v in settings_overview.time_step_settings.to_dict().items() if k not in ignore_entries
        }
        set_widgets_parameters(
            self.settings_page.main_widget,
            find_combobox_text=False,
            **physical_settings,
            **numerical_settings,
            **time_step_settings,
        )
        aggregation_settings_list = [settings.to_dict() for settings in settings_overview.aggregation_settings]
        self.settings_page.main_widget.populate_aggregation_settings(aggregation_settings_list)
        # Simulation events
        simulation_duration = self.duration_page.main_widget.calculate_simulation_duration()
        init_conditions = self.init_conditions_dlg.initial_conditions
        if init_conditions.include_initial_conditions:
            init_conditions_widget = self.init_conditions_page.main_widget
            if any([events.initial_onedwaterlevel, events.initial_onedwaterlevelpredefined]):
                init_conditions_widget.cb_1d.setChecked(True)
                if events.initial_onedwaterlevel:
                    init_conditions_widget.dd_1d.setCurrentText("Global value")
                    init_conditions_widget.sp_1d_global_value.setValue(events.initial_onedwaterlevel.value)
                elif events.initial_onedwaterlevelpredefined:
                    init_conditions_widget.dd_1d.setCurrentText("From spatialite")
            if any([events.initial_twodwaterlevel, events.initial_twodwaterraster]):
                init_conditions_widget.cb_2d.setChecked(True)
                if events.initial_twodwaterlevel:
                    init_conditions_widget.sp_2d_global_value.setValue(events.initial_twodwaterlevel.value)
                elif events.initial_twodwaterraster:
                    for raster_filename, raster in init_conditions_widget.rasters.items():
                        if raster.url == events.initial_twodwaterraster.initial_waterlevel:
                            init_conditions_widget.dd_2d.setCurrentText(raster_filename)
                            init_conditions_widget.cb_2d_aggregation.setCurrentText(
                                events.initial_twodwaterraster.aggregation_method
                            )
                            break
            if any([events.initial_groundwaterlevel, events.initial_groundwaterraster]):
                init_conditions_widget.cb_groundwater.setChecked(True)
                if events.initial_groundwaterlevel:
                    init_conditions_widget.sp_gwater_global_value.setValue(events.initial_groundwaterlevel.value)
                elif events.initial_groundwaterraster:
                    for raster_filename, raster in init_conditions_widget.rasters.items():
                        if raster.url == events.initial_groundwaterlevel.initial_waterlevel:
                            init_conditions_widget.dd_groundwater.setCurrentText(raster_filename)
                            init_conditions_widget.cb_gwater_aggregation.setCurrentText(
                                events.initial_groundwaterlevel.aggregation_method
                            )
                            break
        if init_conditions.include_laterals:
            # TODO: Clarify how to handle this
            pass
        if init_conditions.include_breaches:
            breaches_widget = self.breaches_page.main_widget
            if events.breach:
                breach = events.breach[0]
                tc = ThreediCalls(self.plugin_dock.threedi_api)
                threedimodel_id_str = str(self.model_selection_dlg.current_model.id)
                potential_breach_url = breach.potential_breach.rstrip("/")
                potential_breach_id = int(potential_breach_url.split("/")[-1])
                potential_breach = tc.fetch_3di_model_potential_breach(threedimodel_id_str, potential_breach_id)
                breaches_widget.dd_breach_id.setCurrentText(str(potential_breach.connected_pnt_id))
                breaches_widget.sb_width.setValue(breach.initial_width)
                breaches_widget.sb_duration.setValue(breach.duration_till_max_depth)
                breaches_widget.dd_units.setCurrentText("s")
                breaches_widget.sp_start_after.setValue(breach.offset)
        if init_conditions.include_precipitations:
            precipitation_widget = self.precipitation_page.main_widget
            if events.timeseriesrain:
                rain = events.timeseriesrain[0]
                if rain.constant:
                    precipitation_widget.cbo_prec_type.setCurrentText("Constant")
                    precipitation_widget.sp_start_after_constant.setValue(rain.offset // 3600)
                    if rain.duration < simulation_duration:
                        precipitation_widget.sp_stop_after_constant.setValue(rain.duration // 3600)
                    intensity_ms = rain.values[0][-1]
                    intensity_mmh = ms_to_mmh(intensity_ms)
                    precipitation_widget.sp_intensity.setValue(intensity_mmh)
                else:
                    simulation = precipitation_widget.dd_simulation.currentText()
                    precipitation_widget.cbo_prec_type.setCurrentText("Custom")
                    precipitation_widget.le_upload_rain.setText("<FROM TEMPLATE>")
                    precipitation_widget.sp_start_after_custom.setValue(rain.offset // 3600)
                    precipitation_widget.cb_interpolate_rain.setChecked(rain.interpolate)
                    rain_values = rain.values
                    timestep = rain_values[1][0] - rain_values[0][0]
                    mm_timestep = [[t, mmh_to_mmtimestep(ms_to_mmh(v), timestep)] for t, v in rain_values]
                    precipitation_widget.custom_time_series[simulation] = mm_timestep
                    precipitation_widget.plot_precipitation()
            if events.lizardrasterrain:
                rain = events.lizardrasterrain[0]
                precipitation_widget.cbo_prec_type.setCurrentText("Radar - NL Only")
                precipitation_widget.sp_start_after_radar.setValue(rain.offset // 3600)
                if rain.duration < simulation_duration:
                    precipitation_widget.sp_stop_after_radar.setValue(rain.duration // 3600)
        if init_conditions.include_wind:
            pass

    def run_new_simulation(self):
        """Getting data from the wizard and running new simulation."""
        self.settings.setValue("threedi/wizard_size", self.size())
        laterals_timeout = self.settings.value("threedi/laterals_timeout", 45, type=int)
        name = self.name_page.main_widget.le_sim_name.text()
        tags = self.name_page.main_widget.le_tags.text()
        threedimodel_id = self.model_selection_dlg.current_model.id
        organisation_uuid = self.model_selection_dlg.organisation.unique_id
        start_datetime, end_datetime = self.duration_page.main_widget.to_datetime()
        duration = self.duration_page.main_widget.calculate_simulation_duration()
        # initial conditions page attributes
        global_value_1d, raster_2d, global_value_2d, raster_groundwater, global_value_groundwater, saved_state = (
            None,
        ) * 6
        if self.init_conditions.include_initial_conditions:
            global_value_1d = self.init_conditions_page.main_widget.sp_1d_global_value.value()
            raster_2d = self.init_conditions_page.main_widget.rasters.get(
                self.init_conditions_page.main_widget.dd_2d.currentText()
            )
            global_value_2d = self.init_conditions_page.main_widget.sp_2d_global_value.value()
            raster_groundwater = self.init_conditions_page.main_widget.rasters.get(
                self.init_conditions_page.main_widget.dd_groundwater.currentText()
            )
            global_value_groundwater = self.init_conditions_page.main_widget.sp_gwater_global_value.value()
            saved_state = self.init_conditions_page.main_widget.saved_states.get(
                self.init_conditions_page.main_widget.cb_saved_states.currentText()
            )
        try:
            self.new_simulations = []
            self.new_simulation_statuses = {}
            valid_states = ["processed", "valid"]
            simulation_difference = self.init_conditions.simulations_difference
            ptype, poffset, pduration, punits, pvalues, pstart, pinterpolate, pfpath, pcsv, pnetcdf = (None,) * 10
            wtype, woffset, wduration, wspeed, wdirection, wunits, wdrag_coeff, wispeed, widirection, wvalues = (
                None,
            ) * 10
            breach_id, width, d_duration, breach_offset = (None,) * 4
            for i, simulation in enumerate(self.init_conditions.simulations_list, start=1):
                laterals = []
                if hasattr(self, "laterals_page"):
                    laterals = self.laterals_page.main_widget.get_laterals_data(timesteps_in_seconds=True)
                dwf = []
                if hasattr(self, "dwf_page"):
                    dwf = self.dwf_page.main_widget.get_dwf_data(timeseries24=True)
                if hasattr(self, "breaches_page"):
                    self.breaches_page.main_widget.dd_simulation.setCurrentText(simulation)
                    breach_data = self.breaches_page.main_widget.get_breaches_data()
                    if simulation_difference == "breaches" or i == 1:
                        breach_id, width, d_duration, breach_offset = breach_data
                if hasattr(self, "precipitation_page"):
                    self.precipitation_page.main_widget.dd_simulation.setCurrentText(simulation)
                    pdata = self.precipitation_page.main_widget.get_precipitation_data()
                    if simulation_difference == "precipitation" or i == 1:
                        ptype, poffset, pduration, punits, pvalues, pstart, pinterpolate, pfpath, pcsv, pnetcdf = pdata
                if hasattr(self, "wind_page"):
                    (
                        wtype,
                        woffset,
                        wduration,
                        wspeed,
                        wdirection,
                        wunits,
                        wdrag_coeff,
                        wispeed,
                        widirection,
                        wvalues,
                    ) = self.wind_page.main_widget.get_wind_data()
                tc = ThreediCalls(self.plugin_dock.threedi_api)
                sim_name = f"{name}_{i}" if self.init_conditions.multiple_simulations is True else name
                new_simulation = tc.create_simulation(
                    name=sim_name,
                    tags=tags,
                    threedimodel=threedimodel_id,
                    start_datetime=start_datetime,
                    organisation=organisation_uuid,
                    duration=duration,
                )
                current_status = tc.fetch_simulation_status(new_simulation.id)
                sim_id = new_simulation.id
                if self.init_conditions.basic_processed_results:
                    tc.create_simulation_post_processing_lizard_basic(
                        sim_id, scenario_name=sim_name, process_basic_results=True
                    )
                if self.init_conditions.arrival_time_map:
                    tc.create_simulation_postprocessing_in_lizard_arrival(sim_id, basic_post_processing=True)
                if self.init_conditions.damage_estimation:
                    tc.create_simulation_post_processing_lizard_damage(
                        sim_id,
                        basic_post_processing=True,
                        cost_type=self.init_conditions.cost_type,
                        flood_month=self.init_conditions.flood_month,
                        inundation_period=self.init_conditions.period,
                        repair_time_infrastructure=self.init_conditions.repair_time_infrastructure,
                        repair_time_buildings=self.init_conditions.repair_time_buildings,
                    )
                if self.init_conditions.generate_saved_state:
                    tc.create_simulation_saved_state_after_simulation(sim_id, time=duration, name=sim_name)
                if self.init_conditions.include_initial_conditions:
                    if self.init_conditions_page.main_widget.cb_1d.isChecked():
                        if self.init_conditions_page.main_widget.dd_1d.currentText() == "Global value":
                            tc.create_simulation_initial_1d_water_level_constant(sim_id, value=global_value_1d)
                        else:
                            tc.create_simulation_initial_1d_water_level_predefined(sim_id)
                    if self.init_conditions_page.main_widget.cb_2d.isChecked():
                        aggregation_method = self.init_conditions_page.main_widget.cb_2d_aggregation.currentText()
                        if self.init_conditions_page.main_widget.dd_2d.currentText() == "":
                            tc.create_simulation_initial_2d_water_level_constant(sim_id, value=global_value_2d)
                        else:
                            tc.create_simulation_initial_2d_water_level_raster(
                                sim_id, aggregation_method=aggregation_method, initial_waterlevel=raster_2d.url
                            )
                    if self.init_conditions_page.main_widget.cb_groundwater.isChecked():
                        aggregation_method = self.init_conditions_page.main_widget.cb_gwater_aggregation.currentText()
                        if self.init_conditions_page.main_widget.dd_groundwater.currentText() == "":
                            tc.create_simulation_initial_groundwater_level_constant(
                                sim_id, value=global_value_groundwater
                            )
                        else:
                            tc.create_simulation_initial_groundwater_level_raster(
                                sim_id, aggregation_method=aggregation_method, initial_waterlevel=raster_groundwater.url
                            )
                    if self.init_conditions.load_from_saved_state and saved_state:
                        saved_state_id = saved_state.url.strip("/").split("/")[-1]
                        tc.create_simulation_initial_saved_state(sim_id, saved_state=saved_state_id)
                if self.init_conditions.include_laterals:
                    lateral_values = list(laterals.values())
                    write_laterals_to_json(lateral_values, LATERALS_FILE_TEMPLATE)
                    upload_event_file = tc.create_simulation_lateral_file(
                        sim_id, filename=f"{sim_name}_laterals.json", offset=0
                    )
                    upload_file(upload_event_file, LATERALS_FILE_TEMPLATE)
                    for ti in range(int(laterals_timeout // 2)):
                        uploaded_lateral = tc.fetch_lateral_files(sim_id)[0]
                        if uploaded_lateral.state in valid_states:
                            break
                        else:
                            time.sleep(2)
                if self.init_conditions.include_dwf:
                    dwf_values = list(dwf.values())
                    write_laterals_to_json(dwf_values, DWF_FILE_TEMPLATE)
                    upload_event_file = tc.create_simulation_lateral_file(
                        sim_id, filename=f"{sim_name}_dwf.json", offset=0
                    )
                    upload_file(upload_event_file, DWF_FILE_TEMPLATE)
                    for ti in range(int(laterals_timeout // 2)):
                        uploaded_dwf = tc.fetch_lateral_files(sim_id)[0]
                        if uploaded_dwf.state in valid_states:
                            break
                        else:
                            time.sleep(2)
                if self.init_conditions.include_breaches:
                    breach_obj = tc.fetch_3di_model_point_potential_breach(threedimodel_id, int(breach_id))
                    breach = breach_obj.to_dict()
                    tc.create_simulation_breaches(
                        sim_id,
                        potential_breach=breach["url"],
                        duration_till_max_depth=d_duration,
                        initial_width=width,
                        offset=breach_offset,
                    )
                if ptype == CONSTANT:
                    tc.create_simulation_constant_precipitation(
                        sim_id, value=pvalues, units=punits, duration=pduration, offset=poffset
                    )
                elif ptype == CUSTOM:
                    if pcsv:
                        tc.create_simulation_custom_precipitation(
                            sim_id,
                            values=pvalues,
                            units=punits,
                            duration=pduration,
                            offset=poffset,
                            interpolate=pinterpolate,
                        )
                    else:
                        filename = os.path.basename(pfpath)
                        upload = tc.create_simulation_custom_netcdf_precipitation(sim_id, filename=filename)
                        upload_file(upload, pfpath)
                elif ptype == DESIGN:
                    tc.create_simulation_custom_precipitation(
                        sim_id, values=pvalues, units=punits, duration=pduration, offset=poffset
                    )
                elif ptype == RADAR:
                    tc.create_simulation_radar_precipitation(
                        sim_id,
                        reference_uuid=RADAR_ID,
                        units=punits,
                        duration=pduration,
                        offset=poffset,
                        start_datetime=pstart,
                    )
                if self.init_conditions.include_wind:
                    tc.create_simulation_initial_wind_drag_coefficient(sim_id, value=wdrag_coeff)
                if wtype == CONSTANT:
                    tc.create_simulation_constant_wind(
                        sim_id,
                        offset=woffset,
                        duration=wduration,
                        units=wunits,
                        speed_value=wspeed,
                        direction_value=wdirection,
                    )
                elif wtype == CUSTOM:
                    tc.create_simulation_custom_wind(
                        sim_id,
                        offset=woffset,
                        values=wvalues,
                        units=wunits,
                        speed_interpolate=wispeed,
                        direction_interpolate=widirection,
                    )
                # Create settings instances
                main_settings = self.settings_page.main_widget.collect_single_settings()
                physical_settings, numerical_settings, time_step_settings = main_settings
                aggregation_settings_list = self.settings_page.main_widget.collect_aggregation_settings()
                tc.create_simulation_settings_physical(sim_id, **physical_settings)
                tc.create_simulation_settings_numerical(sim_id, **numerical_settings)
                tc.create_simulation_settings_time_step(sim_id, **time_step_settings)
                for aggregation_settings in aggregation_settings_list:
                    tc.create_simulation_settings_aggregation(sim_id, **aggregation_settings)
                # Run simulation
                try:
                    tc.create_simulation_action(sim_id, name="start")
                except ApiException as e:
                    if e.status == 429:
                        tc.create_simulation_action(sim_id, name="queue")
                    else:
                        raise e
                if self.summary_page.main_widget.cb_save_template.isChecked():
                    template_name = self.summary_page.main_widget.template_name.text()
                    tc.create_template_from_simulation(template_name, str(sim_id))
                self.new_simulations.append(new_simulation)
                self.new_simulation_statuses[new_simulation.id] = current_status
                msg = f"Simulation {new_simulation.name} added to queue!"
                self.plugin_dock.communication.bar_info(msg, log_text_color=QColor(Qt.darkGreen))
        except ApiException as e:
            self.new_simulations = None
            self.new_simulation_statuses = None
            error_msg = extract_error_message(e)
            self.plugin_dock.communication.bar_error(error_msg, log_text_color=QColor(Qt.red))
        except Exception as e:
            self.new_simulations = None
            self.new_simulation_statuses = None
            error_msg = f"Error: {e}"
            self.plugin_dock.communication.bar_error(error_msg, log_text_color=QColor(Qt.red))

    def cancel_wizard(self):
        """Handling canceling wizard action."""
        self.settings.setValue("threedi/wizard_size", self.size())
        self.reject()
