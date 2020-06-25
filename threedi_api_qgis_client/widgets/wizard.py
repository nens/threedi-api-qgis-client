# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import json
import os
import csv

import pyqtgraph as pg
from dateutil.relativedelta import relativedelta
from datetime import datetime
from collections import OrderedDict
from qgis.PyQt.QtSvg import QSvgWidget
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtWidgets import QWizardPage, QWizard, QGridLayout, QSizePolicy, QFileDialog
from openapi_client import ApiException
from ..ui_utils import icon_path, set_widget_background_color, scan_widgets_parameters, set_widgets_parameters
from ..utils import mmh_to_ms, mmh_to_mmtimestep, mmtimestep_to_mmh, TEMPLATE_PATH
from ..api_calls.threedi_calls import ThreediCalls


base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_name_page, basecls_name_page = uic.loadUiType(os.path.join(base_dir, 'ui', 'page_name.ui'))
uicls_duration_page, basecls_duration_page = uic.loadUiType(os.path.join(base_dir, 'ui', 'page_duration.ui'))
uicls_initial_conds, basecls_initial_conds = uic.loadUiType(os.path.join(base_dir, 'ui', 'page_initial_conditions.ui'))
uicls_laterals, basecls_laterals = uic.loadUiType(os.path.join(base_dir, 'ui', 'page_laterals.ui'))
uicls_precipitation_page, basecls_precipitation_page = uic.loadUiType(os.path.join(base_dir, 'ui', 'page_precipitation.ui'))
uicls_breaches, basecls_breaches = uic.loadUiType(os.path.join(base_dir, 'ui', 'page_breaches.ui'))
uicls_summary_page, basecls_summary_page = uic.loadUiType(os.path.join(base_dir, 'ui', 'page_initiation.ui'))


CONSTANT_RAIN = "Constant"
CUSTOM_RAIN = "Custom"
DESIGN_RAIN = "Design"
AREA_WIDE_RAIN = {
    '0': [0.0],
    '1': [0.0],
    '2': [0.0],
    '3': [0.30, 0.60, 0.90, 1.50, 2.10, 2.10, 1.50, 1.20,
          1.05, 0.90, 0.75, 0.60, 0.45, 0.30, 0.15],
    '4': [0.15, 0.30, 0.45, 0.60, 0.75, 0.90, 1.05, 1.20,
          1.50, 2.10, 2.10, 1.50, 0.90, 0.60, 0.30],
    '5': [0.30, 0.60, 1.50, 2.70, 2.70, 2.10, 1.50, 1.20,
          1.05, 0.90, 0.75, 0.60, 0.45, 0.30, 0.15],
    '6': [0.15, 0.30, 0.45, 0.60, 0.75, 0.90, 1.05, 1.20,
          1.50, 2.10, 2.70, 2.70, 1.50, 0.60, 0.30],
    '7': [0.6, 1.2, 2.1, 3.3, 3.3, 2.7, 2.1, 1.5, 1.2, 0.9, 0.6, 0.3],
    '8': [0.3, 0.6, 0.9, 1.2, 1.5, 2.1, 2.7, 3.3, 3.3, 2.1, 1.2, 0.6],
    '9': [1.5, 2.7, 4.8, 4.8, 4.2, 3.3, 2.7, 2.1, 1.5, 0.9, 0.6, 0.3],
    '10': [1.8, 3.6, 6.3, 6.3, 5.7, 4.8, 3.6, 2.4, 1.2],
    '11': [5.833333333] * 12,
    '12': [7.5] * 12,
    '13': [6.666666667] * 24,
    '14': [0.208333333] * 576,
    '15': [0.225694444] * 576,
    '16': [0.277777778] * 576
}

RAIN_LOOKUP = {
    '0': ('', ''),
    '1': ('0.25', 'v'),
    '2': ('0.25', 'a'),
    '3': ('0.50', 'v'),
    '4': ('0.50', 'a'),
    '5': ('1.00', 'v'),
    '6': ('1.00', 'a'),
    '7': ('2.00', 'v'),
    '8': ('2.00', 'a'),
    '9': ('5.00', 'v'),
    '10': ('10.00', 'v'),
    '11': ('100.00', 'c'),
    '12': ('250.00', 'c'),
    '13': ('1000.00', 'c'),
    '14': ('100.00', 'c'),
    '15': ('250.00', 'c'),
    '16': ('1000.00', 'c')
}


class NameWidget(uicls_name_page, basecls_name_page):
    """Widget for Name page."""
    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path('sim_wizard_name.svg'))
        self.svg_widget.setMinimumHeight(75)
        self.svg_widget.setMinimumWidth(700)
        self.svg_lout.addWidget(self.svg_widget)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)


class SimulationDurationWidget(uicls_duration_page, basecls_duration_page):
    """Widget for Simulation Duration page."""
    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path('sim_wizard_duration.svg'))
        self.svg_widget.setMinimumHeight(75)
        self.svg_widget.setMinimumWidth(700)
        self.svg_lout.addWidget(self.svg_widget)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)
        self.date_from.dateTimeChanged.connect(self.update_time_difference)
        self.date_to.dateTimeChanged.connect(self.update_time_difference)
        self.time_from.dateTimeChanged.connect(self.update_time_difference)
        self.time_to.dateTimeChanged.connect(self.update_time_difference)

    def to_datetime(self):
        """Method for QDateTime ==> datetime conversion."""
        date_from = self.date_from.dateTime().toString('yyyy-MM-dd')
        time_from = self.time_from.time().toString('H:m')
        date_to = self.date_to.dateTime().toString('yyyy-MM-dd')
        time_to = self.time_to.time().toString('H:m')
        start = datetime.strptime(f"{date_from} {time_from}", '%Y-%m-%d %H:%M')
        end = datetime.strptime(f"{date_to} {time_to}", '%Y-%m-%d %H:%M')
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
            self.label_total_time.setText('{} years, {} months, {} days, {} hours, {} minutes'.format(*duration))
        except ValueError:
            self.label_total_time.setText('Invalid datetime format!')


class InitialConditionsWidget(uicls_initial_conds, basecls_initial_conds):
    def __init__(self, parent_page, load_conditions=False):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path('sim_wizard_initial_con.svg'))
        self.svg_widget.setMinimumHeight(75)
        self.svg_widget.setMinimumWidth(700)
        self.svg_lout.addWidget(self.svg_widget)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)
        self.rasters = {}
        self.saved_states = {}
        self.d1_widget.hide()
        self.d2_widget.hide()
        self.groundwater_widget.hide()
        self.cb_1d.stateChanged.connect(self.d1_change_state)
        self.cb_2d.stateChanged.connect(self.d2_change_state)
        self.cb_groundwater.stateChanged.connect(self.groundwater_change_state)
        self.dd_1d.currentIndexChanged.connect(self.dropdown_d1_changed)
        self.dd_2d.currentIndexChanged.connect(self.dropdown_d2_changed)
        self.dd_groundwater.currentIndexChanged.connect(self.dropdown_groundwater_changed)
        self._fill_checkboxes()
        if load_conditions:
            self.load_conditions_widget.show()
            self.default_init_widget.hide()
        else:
            self.load_conditions_widget.hide()
            self.default_init_widget.show()

    def _fill_checkboxes(self):
        try:
            self.dd_2d.addItem("")
            self.dd_groundwater.addItem("")
            self.cb_saved_states.addItem("")
            tc = ThreediCalls(self.parent_page.parent_wizard.parent_dock.api_client)
            rasters = tc.fetch_initial_waterlevels(self.parent_page.parent_wizard.parent_dock.current_model.id)
            for raster in rasters or []:
                raster_filename = raster.file.filename
                self.rasters[raster_filename] = raster
                self.dd_2d.addItem(raster_filename)
                self.dd_groundwater.addItem(raster_filename)

            states = tc.fetch_saved_states_list(self.parent_page.parent_wizard.parent_dock.current_model.id)
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
            self.parent_page.parent_wizard.parent_dock.communication.bar_error(error_msg, log_text_color=QColor(Qt.red))
        except Exception as e:
            error_msg = f"Error: {e}"
            self.parent_page.parent_wizard.parent_dock.communication.bar_error(error_msg, log_text_color=QColor(Qt.red))
        self.dd_1d.addItems(["Predefined", "Global value"])

    def dropdown_d1_changed(self):
        if self.dd_1d.currentText() == "Global value":
            self.sp_1d_global_value.setEnabled(True)
        else:
            self.sp_1d_global_value.setDisabled(True)

    def dropdown_d2_changed(self):
        if self.dd_2d.currentIndex() <= 0:
            self.sp_2d_global_value.setEnabled(True)
        else:
            self.sp_2d_global_value.setDisabled(True)

    def dropdown_groundwater_changed(self):
        if self.dd_groundwater.currentIndex() <= 0:
            self.sp_gwater_global_value.setEnabled(True)
        else:
            self.sp_gwater_global_value.setDisabled(True)

    def d1_change_state(self, value):
        if value == 0:
            self.d1_widget.hide()
        if value == 2:
            self.d1_widget.show()

    def d2_change_state(self, value):
        if value == 0:
            self.d2_widget.hide()
        if value == 2:
            self.d2_widget.show()

    def groundwater_change_state(self, value):
        if value == 0:
            self.groundwater_widget.hide()
        if value == 2:
            self.groundwater_widget.show()


class LateralsWidget(uicls_laterals, basecls_laterals):
    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path('sim_wizard_laterals.svg'))
        self.svg_widget.setMinimumHeight(75)
        self.svg_widget.setMinimumWidth(700)
        self.svg_lout.addWidget(self.svg_widget)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)
        self.laterals_timeseries = {}
        self.last_uploaded_laterals = None
        self._init_widget()
        self._connect_signals()

    def _init_widget(self):
        self.overrule_widget.setVisible(False)
        self.cb_type.addItems(["1D", "2D"])

    def _connect_signals(self):
        self.cb_overrule.stateChanged.connect(self.overrule_value_changed)
        self.pb_upload.clicked.connect(self.load_csv)
        self.pb_use_csv.clicked.connect(self.overrule_with_csv)
        self.cb_type.currentIndexChanged.connect(self.selection_changed)
        self.cb_laterals.activated.connect(self.laterals_change)

    def laterals_change(self):
        lat_id = self.cb_laterals.currentText()
        self.il_location.setText(lat_id)

    def save_laterals(self):
        lat = self.laterals_timeseries.get(self.cb_laterals.currentText())
        lat.values[0] = [float(f) for f in self.il_location.text().split(",")]
        lat.values[1] = [float(f) for f in self.il_discharge.text().split(",")]
        lat.offset(self.sb_offset.value())

    def selection_changed(self, index):
        if index == 0:
            self.laterals_layout.setText("Upload laterals for 1D:")
        if index == 1:
            self.laterals_layout.setText("Upload laterals for 2D:")

    def load_csv(self):
        values, filename = self.open_upload_dialog()
        if not filename:
            return
        self.il_upload.setText(filename)
        self.laterals_timeseries = values
        for lat in self.laterals_timeseries.keys():
            self.cb_laterals.addItem(lat)

    def overrule_with_csv(self):
        values, filename = self.open_upload_dialog()
        if not filename:
            return
        laterals = self.laterals_timeseries.get(self.cb_laterals.currentText())
        for lat in values.values():
            laterals.values = lat.values
            return

    def overrule_value_changed(self, value):
        if value == 0:
            self.overrule_widget.setVisible(False)
        if value == 2:
            self.overrule_widget.setVisible(True)

    def get_laterals_data(self):
        return self.laterals_timeseries

    def open_upload_dialog(self):
        last_folder = QSettings().value("threedi/last_precipitation_folder", os.path.expanduser("~"), type=str)
        file_filter = "CSV (*.csv );;All Files (*)"
        filename, __ = QFileDialog.getOpenFileName(self, "Precipitation Time Series", last_folder, file_filter)
        if len(filename) == 0:
            return None, None
        QSettings().setValue("threedi/last_precipitation_folder", os.path.dirname(filename))
        values = {}
        laterals_type = self.cb_type.currentText()
        with open(filename) as lateral_file:
            laterals_reader = csv.reader(lateral_file)
            next(laterals_reader, None)
            if laterals_type == "1D":
                try:
                    for row_id, lat_id, connection_node_id, timeseries in laterals_reader:
                        vals = [[float(f) for f in line.split(",")] for line in timeseries.split("\n")]
                        lateral = {"values": vals, "units": "m3/s", "point": None,
                                   "connection_node": int(connection_node_id), "id": int(lat_id), "offset": 0}
                        values[lat_id] = lateral
                        self.last_uploaded_laterals = lateral
                except ValueError:
                    return None, None
            else:
                try:
                    for x, y, ltype, lat_id, timeseries in laterals_reader:
                        vals = [[float(f) for f in line.split(",")] for line in timeseries.split("\n")]
                        point = {"type": "point",  "coordinates": [float(x), float(y)]}
                        lateral = {"values": vals, "units": "m3/s", "point": point, "id": int(lat_id), "offset": 0}
                        values[lat_id] = lateral
                        self.last_uploaded_laterals = lateral
                except ValueError:
                    return None, None
        return values, filename


class PrecipitationWidget(uicls_precipitation_page, basecls_precipitation_page):
    """Widget for Precipitation page."""
    SECONDS_MULTIPLIERS = {'s': 1, 'mins': 60, 'hrs': 3600}
    DESIGN_TIMESTEP = 300

    def __init__(self, parent_page, initial_conditions=None):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path('sim_wizard_precipitation.svg'))
        self.svg_widget.setMinimumHeight(75)
        self.svg_widget.setMinimumWidth(700)
        self.svg_lout.addWidget(self.svg_widget)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)
        self.current_units = 'hrs'
        self.precipitation_duration = 0
        self.total_precipitation = 0
        self.custom_time_series = []
        self.design_time_series = []
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
        self.connect_signals()
        self.values = dict()
        self.plot_precipitation()
        if initial_conditions.multiple_simulations and initial_conditions.simulations_difference == "precipitation":
            self.dd_simulation.addItems([f"Simulation{str(i)}" for i in range(1, initial_conditions.number_of_simulations + 1)])
            self.simulation_widget.show()
        else:
            self.dd_simulation.addItem("Simulation1")
            self.write_values_into_dict()
            self.simulation_widget.hide()

    def connect_signals(self):
        """Connecting widgets signals."""
        self.cbo_prec_type.currentIndexChanged.connect(self.precipitation_changed)
        self.sp_intensity.valueChanged.connect(self.plot_precipitation)
        self.start_after_constant_u.currentIndexChanged.connect(self.sync_units)
        self.stop_after_constant_u.currentIndexChanged.connect(self.sync_units)
        self.sp_start_after_constant.valueChanged.connect(self.plot_precipitation)
        self.sp_stop_after_constant.valueChanged.connect(self.plot_precipitation)
        self.pb_csv.clicked.connect(self.set_custom_time_series)
        self.start_after_custom_u.currentIndexChanged.connect(self.sync_units)
        self.sp_start_after_custom.valueChanged.connect(self.plot_precipitation)
        self.cbo_design.currentIndexChanged.connect(self.plot_precipitation)
        self.start_after_design_u.currentIndexChanged.connect(self.sync_units)
        self.sp_start_after_design.valueChanged.connect(self.plot_precipitation)
        self.dd_simulation.activated.connect(self.simulation_changed)

    def write_values_into_dict(self):
        simulation = self.dd_simulation.currentText()
        precipitation_type = self.cbo_prec_type.currentText()
        if precipitation_type == "Constant":
            start_after = self.sp_start_after_constant.value()
            start_after_units = self.start_after_constant_u.currentText()
            stop_after = self.sp_stop_after_constant.value()
            stop_after_units = self.stop_after_constant_u.currentText()
            intensity = self.sp_intensity.value()
            self.values[simulation] = {"precipitation_type": precipitation_type,
                                       "start_after": start_after,
                                       "start_after_units": start_after_units,
                                       "stop_after": stop_after,
                                       "stop_after_units": stop_after_units,
                                       "intensity": intensity}
        elif precipitation_type == "Custom":
            start_after = self.sp_start_after_custom.value()
            start_after_units = self.start_after_custom_u.currentText()
            units = self.cbo_units.currentText()
            time_series = self.custom_time_series
            self.values[simulation] = {"precipitation_type": precipitation_type,
                                       "start_after": start_after,
                                       "start_after_units": start_after_units,
                                       "units": units,
                                       "time_series": time_series}
        elif precipitation_type == "Design":
            start_after = self.sp_start_after_design.value()
            start_after_units = self.start_after_design_u.currentText()
            design_number = self.cbo_design.currentText()
            self.values[simulation] = {"precipitation_type": precipitation_type,
                                       "start_after": start_after,
                                       "start_after_units": start_after_units,
                                       "design_number": design_number,
                                       "time_series": self.design_time_series}

    def simulation_changed(self):
        vals = self.values.get(self.dd_simulation.currentText())
        if not vals:
            self.cbo_prec_type.setCurrentText("None")
            self.plot_precipitation()
            return
        if vals.get("precipitation_type") == "Constant":
            self.cbo_prec_type.setCurrentText(vals.get("precipitation_type"))
            self.sp_start_after_constant.setValue(vals.get("start_after"))
            self.start_after_constant_u.setCurrentText(vals.get("start_after_units"))
            self.sp_stop_after_constant.setValue(vals.get("stop_after"))
            self.stop_after_constant_u.setCurrentText(vals.get("stop_after_units"))
            self.sp_intensity.setValue(vals.get("intensity"))
        elif vals.get("precipitation_type") == "Custom":
            self.cbo_prec_type.setCurrentText(vals.get("precipitation_type"))
            self.sp_start_after_custom.setValue(vals.get("start_after"))
            self.start_after_custom_u.setCurrentText(vals.get("start_after_units"))
            self.cbo_units.setCurrentText(vals.get("units"))
            self.custom_time_series = vals.get("time_series")
        elif vals.get("precipitation_type") == "Design":
            self.cbo_prec_type.setCurrentText(vals.get("precipitation_type"))
            self.sp_start_after_design.setValue(vals.get("start_after"))
            self.start_after_design_u.setCurrentText(vals.get("start_after_units"))
            self.cbo_design.setCurrentText(vals.get("design_number"))
        self.plot_precipitation()

    def precipitation_changed(self, idx):
        """Changing widgets looks based on currently selected precipitation type."""
        if idx == 1:
            self.widget_constant.show()
            self.widget_custom.hide()
            self.widget_design.hide()
        elif idx == 2:
            self.widget_constant.hide()
            self.widget_custom.show()
            self.widget_design.hide()
        elif idx == 3:
            self.widget_constant.hide()
            self.widget_custom.hide()
            self.widget_design.show()
        else:
            self.widget_constant.hide()
            self.widget_custom.hide()
            self.widget_design.hide()
        self.refresh_current_units()
        self.plot_precipitation()

    def sync_units(self, idx):
        """Syncing units widgets."""
        current_text = self.cbo_prec_type.currentText()
        if current_text == CONSTANT_RAIN:
            if self.start_after_constant_u.currentIndex != idx:
                self.start_after_constant_u.setCurrentIndex(idx)
            if self.stop_after_constant_u.currentIndex != idx:
                self.stop_after_constant_u.setCurrentIndex(idx)
            self.current_units = self.start_after_constant_u.currentText()
        elif current_text == CUSTOM_RAIN:
            self.current_units = self.start_after_custom_u.currentText()
        elif current_text == DESIGN_RAIN:
            self.current_units = self.start_after_design_u.currentText()
        self.plot_precipitation()

    def refresh_current_units(self):
        """Refreshing current units value."""
        current_text = self.cbo_prec_type.currentText()
        if current_text == CONSTANT_RAIN:
            self.current_units = self.start_after_constant_u.currentText()
        elif current_text == CUSTOM_RAIN:
            self.current_units = self.start_after_custom_u.currentText()
        elif current_text == DESIGN_RAIN:
            self.current_units = self.start_after_design_u.currentText()

    def refresh_duration(self):
        """Refreshing precipitation duration in seconds."""
        self.precipitation_duration = self.get_precipitation_duration(None)

    def duration_in_units(self):
        """Calculating duration in currently selected units."""
        unit_divider = self.SECONDS_MULTIPLIERS[self.current_units]
        duration_in_units = int(self.precipitation_duration / unit_divider)
        return duration_in_units

    def set_custom_time_series(self):
        """Selecting and setting up rain time series from CSV format."""
        last_folder = QSettings().value("threedi/last_precipitation_folder", os.path.expanduser("~"), type=str)
        file_filter = "CSV (*.csv );;All Files (*)"
        filename, __ = QFileDialog.getOpenFileName(self, "Precipitation Time Series", last_folder, file_filter)
        if len(filename) == 0:
            return
        QSettings().setValue("threedi/last_precipitation_folder", os.path.dirname(filename))
        time_series = []
        with open(filename) as rain_file:
            rain_reader = csv.reader(rain_file)
            units_multiplier = self.SECONDS_MULTIPLIERS['mins']
            for time, rain in rain_reader:
                # We are assuming that timestep is in minutes, so we are converting it to seconds on the fly.
                try:
                    time_series.append([float(time)*units_multiplier, float(rain)])
                except ValueError:
                    continue
        self.custom_time_series = time_series
        self.plot_precipitation()

    def set_design_time_series(self, i=0, simulation=None):
        """Setting time series based on selected design number."""
        if not simulation:
            simulation = self.dd_simulation.currentText()
        data = self.values.get(simulation)
        design_id = data.get("design_number")
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
        # Design precipitation timestep is 300 seconds.
        timestep = self.DESIGN_TIMESTEP
        self.design_time_series = [[t, v] for t, v in zip(range(0, len(series)*timestep, timestep), series)]

    def get_precipitation_offset(self, simulation):
        """Calculating precipitation offset in seconds."""
        to_seconds_multiplier = self.SECONDS_MULTIPLIERS[self.current_units]
        data = self.values.get(simulation)
        if data:
            start = data.get("start_after")
            offset = start * to_seconds_multiplier
            return offset
        else:
            return 0.0

    def get_precipitation_duration(self, simulation):
        """Calculating precipitation duration in seconds."""
        if not simulation:
            simulation = self.dd_simulation.currentText()
        data = self.values.get(simulation)
        if data:
            current_text = data.get("precipitation_type")
            if current_text == CONSTANT_RAIN:
                to_seconds_multiplier = self.SECONDS_MULTIPLIERS[self.current_units]
                start = data.get("start_after")
                end = data.get("stop_after")
                start_in_seconds = start * to_seconds_multiplier
                end_in_seconds = end * to_seconds_multiplier
                simulation_duration = self.parent_page.parent_wizard.duration_page.main_widget.calculate_simulation_duration()
                if start_in_seconds > simulation_duration:
                    start_in_seconds = simulation_duration
                if end_in_seconds == 0 or end_in_seconds > simulation_duration:
                    end_in_seconds = simulation_duration
                precipitation_duration = end_in_seconds - start_in_seconds
                if precipitation_duration < 0:
                    precipitation_duration = 0
            elif current_text == CUSTOM_RAIN or current_text == DESIGN_RAIN:
                end_in_seconds = data.get("time_series")[-1][0] if data.get("time_series") else 0
                precipitation_duration = end_in_seconds
            else:
                precipitation_duration = 0
            return precipitation_duration
        else:
            return 0

    def get_precipitation_values(self, simulation):
        """Calculating precipitation values in 'm/s'."""
        data = self.values.get(simulation)
        values = []
        if data:
            current_text = data.get("precipitation_type")
            if current_text == CONSTANT_RAIN:
                values = mmh_to_ms(data.get("intensity"))
            elif current_text == CUSTOM_RAIN:
                ts = data.get("time_series")
                if data.get("units") == 'mm/h':
                    values = [[t, mmh_to_ms(v)] for t, v in ts]
                else:
                    timestep = ts[1][0] - ts[0][0] if len(ts) > 1 else 1
                    values = [[t, mmh_to_ms(mmtimestep_to_mmh(v, timestep))] for t, v in ts]
            elif current_text == DESIGN_RAIN:
                values = [[t, mmh_to_ms(mmtimestep_to_mmh(v, self.DESIGN_TIMESTEP))] for t, v in data.get("time_series")]
        return values

    def get_precipitation_data(self, simulation):
        """Getting all needed data for adding precipitation to the simulation."""
        data = self.values.get(simulation)
        precipitation_type = None
        if data:
            precipitation_type = data.get("precipitation_type")
        offset = self.get_precipitation_offset(simulation)
        duration = self.get_precipitation_duration(simulation)
        units = "m/s"
        values = self.get_precipitation_values(simulation)
        return precipitation_type, offset, duration, units, values

    def constant_values(self, simulation):
        """Getting plot values for the Constant precipitation."""
        x_values, y_values = [], []
        data = self.values.get(simulation)
        intensity = 0
        if data:
            intensity = data.get("intensity")
        if intensity <= 0:
            return x_values, y_values
        duration_in_units = self.duration_in_units()
        x_values += [x for x in list(range(duration_in_units + 1))]
        y_values += [intensity] * len(x_values)
        return x_values, y_values

    def custom_values(self):
        """Getting plot values for the Custom precipitation."""
        x_values, y_values = [], []
        units_multiplier = self.SECONDS_MULTIPLIERS[self.current_units]
        for x, y in self.custom_time_series:
            x_in_units = x / units_multiplier
            x_values.append(x_in_units)
            y_values.append(y)
        return x_values, y_values

    def design_values(self):
        """Getting plot values for the Design precipitation."""
        x_values, y_values = [], []
        units_multiplier = self.SECONDS_MULTIPLIERS[self.current_units]
        for x, y in self.design_time_series:
            x_in_units = x / units_multiplier
            x_values.append(x_in_units)
            y_values.append(y)
        return x_values, y_values

    def plot_precipitation(self, i=0, simulation=None):
        """Setting up precipitation plot."""
        self.write_values_into_dict()
        self.refresh_duration()
        self.plot_widget.clear()
        self.plot_bar_graph = None
        self.plot_ticks = None

        current_text = ""
        if not simulation:
            simulation = self.dd_simulation.currentText()
        data = self.values.get(simulation)
        if data:
            current_text = data.get("precipitation_type")
        if current_text == CONSTANT_RAIN:
            x_values, y_values = self.constant_values(simulation)
        elif current_text == CUSTOM_RAIN:
            x_values, y_values = self.custom_values()
        elif current_text == DESIGN_RAIN:
            x_values, y_values = self.design_values()
            self.set_design_time_series(simulation=simulation)
        else:
            return
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
        ax = self.plot_widget.getAxis('bottom')
        ax.setTicks(self.plot_ticks)
        self.plot_bar_graph = pg.BarGraphItem(x=x_values, height=y_values, width=timestep, brush=QColor('#1883D7'))
        self.plot_widget.addItem(self.plot_bar_graph)
        if current_text == CONSTANT_RAIN:
            precipitation_values = y_values[:-1]
        else:
            precipitation_values = y_values
        if current_text == CONSTANT_RAIN:
            self.total_precipitation = sum(mmh_to_mmtimestep(v, 1, self.current_units) for v in precipitation_values)
        elif current_text == CUSTOM_RAIN and data.get("units") == 'mm/h':
            self.total_precipitation = sum(mmh_to_mmtimestep(v, timestep, self.current_units)
                                           for v in precipitation_values)
        else:
            # This is for 'mm/timestep'
            self.total_precipitation = sum(precipitation_values)
        self.plot_widget.setXRange(first_time, last_time)
        self.plot_widget.setYRange(first_time, max(precipitation_values))


class BreachesWidget(uicls_breaches, basecls_breaches):
    SECONDS_MULTIPLIERS = {'s': 1, 'mins': 60, 'hrs': 3600}

    def __init__(self, parent_page, initial_conditions=None):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path('sim_wizard_breaches.svg'))
        self.svg_widget.setMinimumHeight(75)
        self.svg_widget.setMinimumWidth(700)
        self.svg_lout.addWidget(self.svg_widget)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)
        self.values = dict()
        self.breaches = dict()
        self.dd_breach_id.activated.connect(self.write_values_into_dict)
        self.dd_simulation.activated.connect(self.simulation_changed)
        self.dd_units.activated.connect(self.write_values_into_dict)
        self.sb_duration.valueChanged.connect(self.write_values_into_dict)
        self.sb_width.valueChanged.connect(self.write_values_into_dict)
        if initial_conditions.multiple_simulations and initial_conditions.simulations_difference == "breaches":
            self.dd_simulation.addItems([f"Simulation{i}" for i in range(1, initial_conditions.number_of_simulations + 1)])
            self.simulation_widget.show()
        else:
            self.dd_simulation.addItem("Simulation1")
            self.simulation_widget.hide()
        self.fill_comboboxes()

    def fill_comboboxes(self):
        tc = ThreediCalls(self.parent_page.parent_wizard.parent_dock.api_client)
        breaches = tc.fetch_breaches_list(self.parent_page.parent_wizard.parent_dock.current_model.id)
        for breach in breaches:
            self.breaches[breach.connected_pnt_id] = breach.to_dict()
            self.dd_breach_id.addItem(str(breach.connected_pnt_id))
        self.write_values_into_dict()

    def write_values_into_dict(self, i=0):
        simulation = self.dd_simulation.currentText()
        breach_id = self.dd_breach_id.currentText()
        duration = self.sb_duration.value()
        width = self.sb_width.value()
        units = self.dd_units.currentText()
        self.values[simulation] = {"breach_id": breach_id,
                                   "breach": self.breaches.get(int(breach_id) if breach_id.isnumeric() else None),
                                   "width": width,
                                   "duration": duration,
                                   "units": units}

    def simulation_changed(self):
        vals = self.values.get(self.dd_simulation.currentText())
        if vals:
            self.dd_breach_id.setCurrentText(vals.get("breach_id"))
            self.sb_duration.setValue(vals.get("duration"))
            self.sb_width.setValue(vals.get("width"))
            self.dd_units.setCurrentText(vals.get("units"))
        else:
            self.dd_breach_id.setCurrentIndex(0)
            self.sb_duration.setValue(0)
            self.sb_width.setValue(0)
            self.dd_units.setCurrentIndex(0)

    def get_breaches_data(self, simulation):
        data = self.values.get(simulation)
        if data:
            breach_data = (data.get("breach_id"), data.get("breach"), data.get("width"),
                           int(data.get("duration")) * self.SECONDS_MULTIPLIERS[data.get("units")])
        else:
            breach_data = (None,) * 4
        return breach_data


class SummaryWidget(uicls_summary_page, basecls_summary_page):
    """Widget for Summary page."""
    def __init__(self, parent_page, initial_conditions=None):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path('sim_wizard_initation.svg'))
        self.svg_widget.setMinimumHeight(75)
        self.svg_widget.setMinimumWidth(700)
        self.svg_lout.addWidget(self.svg_widget)
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
            self.dd_simulation.addItems([f"Simulation{i}" for i in range(1, initial_conditions.number_of_simulations + 1)])
        else:
            self.dd_simulation.addItem("Simulation1")
            self.simulation_widget.hide()

    def simulation_change(self):
        if self.initial_conditions.simulations_difference == "precipitation" and self.initial_conditions.include_precipitations:
            data = self.parent_page.parent_wizard.precipitation_page.main_widget.values.get(self.dd_simulation.currentText())
            self.plot_overview_precipitation()
            if data:
                ptype = data.get("precipitation_type")
                total_prec = self.parent_page.parent_wizard.precipitation_page.main_widget.total_precipitation
                self.sim_prec_type.setText(ptype)
                self.sim_prec_total.setText(str(total_prec))
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
        self.parent_page.parent_wizard.precipitation_page.main_widget.plot_precipitation(simulation=self.dd_simulation.currentText())
        plot_bar_graph = self.parent_page.parent_wizard.precipitation_page.main_widget.plot_bar_graph
        plot_ticks = self.parent_page.parent_wizard.precipitation_page.main_widget.plot_ticks
        if plot_bar_graph is None:
            return
        height = plot_bar_graph.opts['height']
        new_bar_graph = pg.BarGraphItem(**plot_bar_graph.opts)
        ax = self.plot_widget.getAxis('bottom')
        ax.setTicks(plot_ticks)
        self.plot_widget.addItem(new_bar_graph)
        ticks = plot_ticks[0]
        first_tick_value, last_tick_value = ticks[0][0], ticks[-1][0]
        self.plot_widget.setXRange(first_tick_value, last_tick_value)
        self.plot_widget.setYRange(first_tick_value, max(height))

    def save_template_state_changed(self, value):
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
    """New simulation summary page."""
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
    """New simulation summary page."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = LateralsWidget(self)
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


class BreachesPage(QWizardPage):
    """New simulation summary page."""
    def __init__(self, parent=None, initial_conditions=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = BreachesWidget(self, initial_conditions=initial_conditions)
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
    def __init__(self, parent_dock, init_conditions_dlg, parent=None):
        super().__init__(parent)
        self.setWizardStyle(QWizard.ClassicStyle)
        self.init_conditions_dlg = init_conditions_dlg
        init_conditions = self.init_conditions_dlg.initial_conditions
        self.parent_dock = parent_dock
        self.name_page = NamePage(self)
        self.duration_page = SimulationDurationPage(self)
        self.addPage(self.name_page)
        self.addPage(self.duration_page)
        if init_conditions.include_initial_conditions:
            self.init_conditions_page = InitialConditionsPage(self, load_conditions=init_conditions.load_from_saved_state)
            self.addPage(self.init_conditions_page)
        if init_conditions.include_laterals:
            self.laterals_page = LateralsPage(self)
            self.addPage(self.laterals_page)
        if init_conditions.include_breaches:
            self.breaches_page = BreachesPage(self, initial_conditions=init_conditions)
            self.addPage(self.breaches_page)
        if init_conditions.include_precipitations:
            self.precipitation_page = PrecipitationPage(self, initial_conditions=init_conditions)
            self.addPage(self.precipitation_page)
        self.summary_page = SummaryPage(self, initial_conditions=init_conditions)
        self.addPage(self.summary_page)
        self.currentIdChanged.connect(self.page_changed)
        self.setButtonText(QWizard.FinishButton, "Add to queue")
        self.finish_btn = self.button(QWizard.FinishButton)
        self.finish_btn.clicked.connect(self.run_new_simulation)
        self.new_simulations = None
        self.new_simulation_statuses = None
        self.setWindowTitle("New simulation")
        self.setStyleSheet("background-color:#F0F0F0")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.resize(800, 500)
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

    def set_overview_database(self):
        """Setting up database name label in the summary page."""
        database = self.parent_dock.current_model.name
        self.summary_page.main_widget.sim_database.setText(database)

    def set_overview_duration(self):
        """Setting up simulation duration label in the summary page."""
        duration = self.duration_page.main_widget.label_total_time.text()
        self.summary_page.main_widget.sim_duration.setText(duration)

    def set_overview_precipitation(self):
        """Setting up precipitation labels in the summary page."""
        if self.precipitation_page.main_widget.values.get("Simulation1"):
            self.summary_page.main_widget.precipitation_widget.show()
            precipitation_type = self.precipitation_page.main_widget.values.get("Simulation1").get("precipitation_type")
            total_precipitation = self.precipitation_page.main_widget.total_precipitation
            self.summary_page.main_widget.sim_prec_type.setText(precipitation_type)
            self.summary_page.main_widget.sim_prec_total.setText(f"{round(total_precipitation, 2)} mm")

    def set_overview_breaches(self):
        if self.breaches_page.main_widget.values.get("Simulation1"):
            self.summary_page.main_widget.breach_widget.show()
            breach_id = self.breaches_page.main_widget.values.get("Simulation1").get("breach_id")
            duration_of_breach = self.breaches_page.main_widget.values.get("Simulation1").get("duration")
            self.summary_page.main_widget.breach_id.setText(breach_id)
            self.summary_page.main_widget.duration_breach.setText(str(duration_of_breach))

    def save_simulation_as_template(self):
        simulation_template = OrderedDict()
        template_name = self.summary_page.main_widget.template_name.text()
        simulation_template["options"] = scan_widgets_parameters(self.init_conditions_dlg)
        simulation_template["name_page"] = scan_widgets_parameters(self.name_page.main_widget)
        simulation_template["duration_page"] = scan_widgets_parameters(self.duration_page.main_widget)
        if hasattr(self, "init_conditions_page"):
            simulation_template["init_conditions_page"] = scan_widgets_parameters(self.init_conditions_page.main_widget)
        if hasattr(self, "laterals_page"):
            simulation_template["laterals_page"] = scan_widgets_parameters(self.laterals_page.main_widget)
            laterals_values = self.laterals_page.main_widget.get_laterals_data()
            simulation_template["laterals_page"]["values"] = laterals_values
        if hasattr(self, "precipitation_page"):
            simulation_template["precipitation_page"] = scan_widgets_parameters(self.precipitation_page.main_widget)
            precipitation_values = self.precipitation_page.main_widget.values
            simulation_template["precipitation_page"]["values"] = precipitation_values
        if hasattr(self, "breaches_page"):
            simulation_template["breaches_page"] = scan_widgets_parameters(self.breaches_page.main_widget)
            breaches_values = self.breaches_page.main_widget.values
            simulation_template["breaches_page"]["values"] = breaches_values

        with open(TEMPLATE_PATH, 'a'):
            os.utime(TEMPLATE_PATH, None)
        with open(TEMPLATE_PATH, 'r+') as json_file:
            data = {}
            if os.path.getsize(TEMPLATE_PATH):
                data = json.load(json_file)
            data[template_name] = simulation_template
            jsonf = json.dumps(data)
            json_file.seek(0)
            json_file.write(jsonf)
            json_file.truncate()

    def load_template_parameters(self, simulation_template):
        set_widgets_parameters(self.name_page.main_widget, **simulation_template["name_page"])
        set_widgets_parameters(self.duration_page.main_widget, **simulation_template["duration_page"])
        if hasattr(self, "init_conditions_page"):
            set_widgets_parameters(self.init_conditions_page.main_widget, **simulation_template["init_conditions_page"])
        if hasattr(self, "laterals_page"):
            set_widgets_parameters(self.laterals_page.main_widget, **simulation_template["laterals_page"])
            laterals_values = simulation_template["laterals_page"]["values"]
            self.laterals_page.main_widget.laterals_timeseries.update(laterals_values)
            for lat in self.laterals_page.main_widget.laterals_timeseries.keys():
                self.laterals_page.main_widget.cb_laterals.addItem(lat)
        if hasattr(self, "precipitation_page"):
            set_widgets_parameters(self.precipitation_page.main_widget, **simulation_template["precipitation_page"])
            precipitation_values = simulation_template["precipitation_page"]["values"]
            self.precipitation_page.main_widget.values.update(precipitation_values)
        if hasattr(self, "breaches_page"):
            set_widgets_parameters(self.breaches_page.main_widget, **simulation_template["breaches_page"])
            breaches_values = simulation_template["breaches_page"]["values"]
            self.breaches_page.main_widget.values.update(breaches_values)

    def run_new_simulation(self):
        """Getting data from the wizard and running new simulation."""
        name = self.name_page.main_widget.le_sim_name.text()
        threedimodel_id = self.parent_dock.current_model.id
        organisation_uuid = self.parent_dock.organisation.unique_id
        start_datetime = datetime.utcnow()
        duration = self.duration_page.main_widget.calculate_simulation_duration()
        # initial conditions page attributes
        global_value_1d, raster_2d, global_value_2d, raster_groundwater, global_value_groundwater, saved_state = (None,) *6
        if self.init_conditions.include_initial_conditions:
            global_value_1d = self.init_conditions_page.main_widget.sp_1d_global_value.value()
            raster_2d = self.init_conditions_page.main_widget.rasters.get(self.init_conditions_page.main_widget.dd_2d.currentText())
            global_value_2d = self.init_conditions_page.main_widget.sp_2d_global_value.value()
            raster_groundwater = self.init_conditions_page.main_widget.rasters.get(self.init_conditions_page.main_widget.dd_groundwater.currentText())
            global_value_groundwater = self.init_conditions_page.main_widget.sp_gwater_global_value.value()
            saved_state = self.init_conditions_page.main_widget.saved_states.get(self.init_conditions_page.main_widget.cb_saved_states.currentText())

        if self.summary_page.main_widget.cb_save_template.isChecked():
            self.save_simulation_as_template()

        try:
            self.new_simulations = []
            self.new_simulation_statuses = {}
            for simulation in range(1, (self.init_conditions.number_of_simulations + 1)):
                ptype, poffset, pduration, punits, pvalues = (None,) * 5
                breach_id, breach, width, d_duration = (None,) * 4
                laterals = []
                if hasattr(self, "precipitation_page"):
                    ptype, poffset, pduration, punits, pvalues = self.precipitation_page.main_widget.get_precipitation_data(f"Simulation{simulation}")
                if hasattr(self, "breaches_page"):
                    breach_id, breach, width, d_duration = self.breaches_page.main_widget.get_breaches_data(f"Simulation{simulation}")
                if hasattr(self, "laterals_page"):
                    laterals = self.laterals_page.main_widget.get_laterals_data()

                tc = ThreediCalls(self.parent_dock.api_client)
                sim_name = f"{name}_{simulation}" if simulation > 1 else name
                new_simulation = tc.new_simulation(name=sim_name, threedimodel=threedimodel_id,
                                                   start_datetime=start_datetime, organisation=organisation_uuid,
                                                   duration=duration)
                current_status = tc.simulation_current_status(new_simulation.id)
                sim_id = new_simulation.id
                if self.init_conditions.basic_processed_results:
                    tc.add_post_processing_lizard_basic(sim_id, scenario_name=sim_name, process_basic_results=True)
                if self.init_conditions.arrival_time_map:
                    tc.add_postprocessing_in_lizard_arrival(sim_id, basic_post_processing=True)
                if self.init_conditions.damage_estimation:
                    tc.add_post_processing_lizard_damage(
                        sim_id, basic_post_processing=True, cost_type=self.init_conditions.cost_type,
                        flood_month=self.init_conditions.flood_month, inundation_period=self.init_conditions.period,
                        repair_time_infrastructure=self.init_conditions.repair_time_infrastructure,
                        repair_time_buildings=self.init_conditions.repair_time_buildings)
                if self.init_conditions.generate_saved_state:
                    tc.add_saved_state_after_simulation(sim_id, time=duration)
                if self.init_conditions.include_breaches:
                    tc.add_breaches(sim_id, potential_breach=breach["url"], duration_till_max_depth=d_duration,
                                    initial_width=width, offset=0)
                if self.init_conditions.include_laterals:
                    for lateral in laterals.values():
                        tc.add_lateral_timeseries(sim_id, **lateral)
                if self.init_conditions.include_initial_conditions:
                    if self.init_conditions_page.main_widget.cb_1d.isChecked():
                        if self.init_conditions_page.main_widget.dd_1d.currentText() == "Global value":
                            tc.add_initial_1d_water_level_constant(sim_id, value=global_value_1d)
                        else:
                            tc.add_initial_1d_water_level_predefined(sim_id)
                    if self.init_conditions_page.main_widget.cb_2d.isChecked():
                        if self.init_conditions_page.main_widget.dd_2d.currentText() == "":
                            tc.add_initial_2d_water_level_constant(sim_id, value=global_value_2d)
                        else:
                            tc.add_initial_2d_water_level_raster(sim_id, aggregation_method="mean",
                                                                 initial_waterlevel=raster_2d.url)
                    if self.init_conditions_page.main_widget.cb_groundwater.isChecked():
                        if self.init_conditions_page.main_widget.dd_groundwater.currentText() == "":
                            tc.add_initial_groundwater_level_constant(sim_id, value=global_value_groundwater)
                        else:
                            tc.add_initial_groundwater_level_raster(sim_id, aggregation_method="mean",
                                                                    initial_waterlevel=raster_groundwater.url)
                    if self.init_conditions.load_from_saved_state and saved_state:
                        saved_state_id = saved_state.url.strip("/").split("/")[-1]
                        tc.add_initial_saved_state(sim_id, saved_state=saved_state_id)

                if ptype == CONSTANT_RAIN:
                    tc.add_constant_precipitation(sim_id, value=pvalues, units=punits, duration=pduration,
                                                  offset=poffset)
                elif ptype == CUSTOM_RAIN or ptype == DESIGN_RAIN:
                    tc.add_custom_precipitation(sim_id, values=pvalues, units=punits, duration=pduration,
                                                offset=poffset)
                tc.make_action_on_simulation(sim_id, name='queue')
                self.new_simulations.append(new_simulation)
                self.new_simulation_statuses[new_simulation.id] = current_status
                msg = f"Simulation {new_simulation.name} added to queue!"
                self.parent_dock.communication.bar_info(msg, log_text_color=QColor(Qt.darkGreen))
        except ApiException as e:
            self.new_simulations = None
            self.new_simulation_statuses = None
            error_body = e.body
            error_details = error_body["details"] if "details" in error_body else error_body
            error_msg = f"Error: {error_details}"
            self.parent_dock.communication.bar_error(error_msg, log_text_color=QColor(Qt.red))
        except Exception as e:
            self.new_simulations = None
            self.new_simulation_statuses = None
            error_msg = f"Error: {e}"
            self.parent_dock.communication.bar_error(error_msg, log_text_color=QColor(Qt.red))
