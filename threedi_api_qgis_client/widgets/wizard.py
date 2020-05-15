# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
import csv
import pyqtgraph as pg
from dateutil.relativedelta import relativedelta
from datetime import datetime
from qgis.PyQt.QtSvg import QSvgWidget
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtWidgets import QWizardPage, QWizard, QGridLayout, QSizePolicy, QFileDialog
from openapi_client import ApiException
from ..ui_utils import icon_path, set_widget_background_color
from ..utils import mmh_to_ms, mmh_to_mmtimestep, mmtimestep_to_mmh
from ..api_calls.threedi_calls import ThreediCalls


base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_p1, basecls_p1 = uic.loadUiType(os.path.join(base_dir, 'ui', 'page1.ui'))
uicls_p2, basecls_p2 = uic.loadUiType(os.path.join(base_dir, 'ui', 'page2.ui'))
uicls_p3, basecls_p3 = uic.loadUiType(os.path.join(base_dir, 'ui', 'page3.ui'))
uicls_p4, basecls_p4 = uic.loadUiType(os.path.join(base_dir, 'ui', 'page4.ui'))

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


class NameWidget(uicls_p1, basecls_p1):
    """Widget for Name page."""
    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path('sim_wizard_p1.svg'))
        self.svg_widget.setMinimumHeight(75)
        self.svg_widget.setMinimumWidth(700)
        self.svg_lout.addWidget(self.svg_widget)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)


class SimulationDurationWidget(uicls_p2, basecls_p2):
    """Widget for Simulation Duration page."""
    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path('sim_wizard_p2.svg'))
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


class PrecipitationWidget(uicls_p3, basecls_p3):
    """Widget for Precipitation page."""
    SECONDS_MULTIPLIERS = {'s': 1, 'mins': 60, 'hrs': 3600}
    DESIGN_TIMESTEP = 300

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path('sim_wizard_p3.svg'))
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
        self.plot_precipitation()

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
        self.cbo_design.currentIndexChanged.connect(self.set_design_time_series)
        self.start_after_design_u.currentIndexChanged.connect(self.sync_units)
        self.sp_start_after_design.valueChanged.connect(self.plot_precipitation)

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
        self.precipitation_duration = self.get_precipitation_duration()

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

    def set_design_time_series(self):
        """Setting time series based on selected design number."""
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
        # Design precipitation timestep is 300 seconds.
        timestep = self.DESIGN_TIMESTEP
        self.design_time_series = [[t, v] for t, v in zip(range(0, len(series)*timestep, timestep), series)]
        self.plot_precipitation()

    def get_intensity(self):
        """Getting intensity value for the Constant precipitation type."""
        intensity = self.sp_intensity.value()
        return intensity

    def get_precipitation_offset(self):
        """Calculating precipitation offset in seconds."""
        current_text = self.cbo_prec_type.currentText()
        to_seconds_multiplier = self.SECONDS_MULTIPLIERS[self.current_units]
        if current_text == CONSTANT_RAIN:
            start = self.sp_start_after_constant.value()
        elif current_text == CUSTOM_RAIN:
            start = self.sp_start_after_custom.value()
        elif current_text == DESIGN_RAIN:
            start = self.sp_start_after_design.value()
        else:
            return 0.0
        offset = start * to_seconds_multiplier
        return offset

    def get_precipitation_duration(self):
        """Calculating precipitation duration in seconds."""
        current_text = self.cbo_prec_type.currentText()
        if current_text == CONSTANT_RAIN:
            to_seconds_multiplier = self.SECONDS_MULTIPLIERS[self.current_units]
            start = self.sp_start_after_constant.value()
            end = self.sp_stop_after_constant.value()
            start_in_seconds = start * to_seconds_multiplier
            end_in_seconds = end * to_seconds_multiplier
            simulation_duration = self.parent_page.parent_wizard.p2.main_widget.calculate_simulation_duration()
            if start_in_seconds > simulation_duration:
                start_in_seconds = simulation_duration
            if end_in_seconds == 0 or end_in_seconds > simulation_duration:
                end_in_seconds = simulation_duration
            precipitation_duration = end_in_seconds - start_in_seconds
            if precipitation_duration < 0:
                precipitation_duration = 0
        elif current_text == CUSTOM_RAIN:
            end_in_seconds = self.custom_time_series[-1][0] if self.custom_time_series else 0
            precipitation_duration = end_in_seconds
        elif current_text == DESIGN_RAIN:
            end_in_seconds = self.design_time_series[-1][0] if self.design_time_series else 0
            precipitation_duration = end_in_seconds
        else:
            precipitation_duration = 0
        return precipitation_duration

    def get_precipitation_values(self):
        """Calculating precipitation values in 'm/s'."""
        current_text = self.cbo_prec_type.currentText()
        if current_text == CONSTANT_RAIN:
            values = mmh_to_ms(self.get_intensity())
        elif current_text == CUSTOM_RAIN:
            ts = self.custom_time_series
            if self.cbo_units.currentText() == 'mm/h':
                values = [[t, mmh_to_ms(v)] for t, v in ts]
            else:
                timestep = ts[1][0] - ts[0][0] if len(ts) > 1 else 1
                values = [[t, mmh_to_ms(mmtimestep_to_mmh(v, timestep))] for t, v in ts]
        elif current_text == DESIGN_RAIN:
            values = [[t, mmh_to_ms(mmtimestep_to_mmh(v, self.DESIGN_TIMESTEP))] for t, v in self.design_time_series]
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
        return precipitation_type, offset, duration, units, values

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

    def plot_precipitation(self):
        """Setting up precipitation plot."""
        self.refresh_duration()
        self.plot_widget.clear()
        self.plot_bar_graph = None
        self.plot_ticks = None
        current_text = self.cbo_prec_type.currentText()
        if current_text == CONSTANT_RAIN:
            x_values, y_values = self.constant_values()
        elif current_text == CUSTOM_RAIN:
            x_values, y_values = self.custom_values()
        elif current_text == DESIGN_RAIN:
            x_values, y_values = self.design_values()
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
        elif current_text == CUSTOM_RAIN and self.cbo_units.currentText() == 'mm/h':
            self.total_precipitation = sum(mmh_to_mmtimestep(v, timestep, self.current_units)
                                           for v in precipitation_values)
        else:
            # This is for 'mm/timestep'
            self.total_precipitation = sum(precipitation_values)
        self.plot_widget.setXRange(first_time, last_time)
        self.plot_widget.setYRange(first_time, max(precipitation_values))


class SummaryWidget(uicls_p4, basecls_p4):
    """Widget for Summary page."""
    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path('sim_wizard_p4.svg'))
        self.svg_widget.setMinimumHeight(75)
        self.svg_widget.setMinimumWidth(700)
        self.svg_lout.addWidget(self.svg_widget)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(None)
        self.plot_widget.setFixedHeight(80)
        self.lout_plot.addWidget(self.plot_widget, 0, 0)

    def plot_overview_precipitation(self):
        """Setting up precipitation plot."""
        self.plot_widget.clear()
        plot_bar_graph = self.parent_page.parent_wizard.p3.main_widget.plot_bar_graph
        plot_ticks = self.parent_page.parent_wizard.p3.main_widget.plot_ticks
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


class PrecipitationPage(QWizardPage):
    """Precipitation definition page."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = PrecipitationWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget, 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class SummaryPage(QWizardPage):
    """New simulation summary page."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = SummaryWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class SimulationWizard(QWizard):
    """New simulation wizard."""
    def __init__(self, parent_dock, parent=None):
        super().__init__(parent)
        self.setWizardStyle(QWizard.ClassicStyle)
        self.parent_dock = parent_dock
        self.p1 = NamePage(self)
        self.p2 = SimulationDurationPage(self)
        self.p3 = PrecipitationPage(self)
        self.p4 = SummaryPage(self)
        self.addPage(self.p1)
        self.addPage(self.p2)
        self.addPage(self.p3)
        self.addPage(self.p4)
        self.currentIdChanged.connect(self.page_changed)
        self.setButtonText(QWizard.FinishButton, "Start Simulation")
        self.finish_btn = self.button(QWizard.FinishButton)
        self.finish_btn.clicked.connect(self.run_new_simulation)
        self.new_simulation = None
        self.new_simulation_status = None
        self.setWindowTitle("New simulation")
        self.setStyleSheet("background-color:#F0F0F0")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.resize(750, 500)

    def page_changed(self, page_id):
        """Extra pre-processing triggered by changes of the wizard pages."""
        if page_id == 2:
            self.p3.main_widget.plot_precipitation()
        elif page_id == 3:
            self.p4.main_widget.plot_overview_precipitation()
            self.set_overview_name()
            self.set_overview_database()
            self.set_overview_duration()
            self.set_overview_precipitation()

    def set_overview_name(self):
        """Setting up simulation name label in the summary page."""
        name = self.p1.main_widget.le_sim_name.text()
        self.p4.main_widget.sim_name.setText(name)

    def set_overview_database(self):
        """Setting up database name label in the summary page."""
        database = self.parent_dock.current_model.name
        self.p4.main_widget.sim_database.setText(database)

    def set_overview_duration(self):
        """Setting up simulation duration label in the summary page."""
        duration = self.p2.main_widget.label_total_time.text()
        self.p4.main_widget.sim_duration.setText(duration)

    def set_overview_precipitation(self):
        """Setting up precipitation labels in the summary page."""
        precipitation_type = self.p3.main_widget.cbo_prec_type.currentText()
        total_precipitation = self.p3.main_widget.total_precipitation
        self.p4.main_widget.sim_prec_type.setText(precipitation_type)
        self.p4.main_widget.sim_prec_total.setText(f"{round(total_precipitation)} mm")

    def run_new_simulation(self):
        """Getting data from the wizard and running new simulation."""
        name = self.p1.main_widget.le_sim_name.text()
        threedimodel_id = self.parent_dock.current_model.id
        organisation_uuid = self.parent_dock.organisation.unique_id
        start_datetime = datetime.utcnow()
        duration = self.p2.main_widget.calculate_simulation_duration()
        try:
            tc = ThreediCalls(self.parent_dock.api_client)
            new_simulation = tc.new_simulation(name=name, threedimodel=threedimodel_id, start_datetime=start_datetime,
                                               organisation=organisation_uuid, duration=duration)
            current_status = tc.simulation_current_status(new_simulation.id)
            sim_id = new_simulation.id
            ptype, poffset, pduration, punits, pvalues = self.p3.main_widget.get_precipitation_data()
            if ptype == CONSTANT_RAIN:
                tc.add_constant_precipitation(sim_id, value=pvalues, units=punits, duration=pduration, offset=poffset)
            elif ptype == CUSTOM_RAIN or ptype == DESIGN_RAIN:
                tc.add_custom_precipitation(sim_id, values=pvalues, units=punits, duration=pduration, offset=poffset)
            tc.make_action_on_simulation(sim_id, name='queue')
            self.new_simulation = new_simulation
            self.new_simulation_status = current_status
            msg = f"Simulation {new_simulation.name} added to queue!"
            self.parent_dock.communication.bar_info(msg, log_text_color=QColor(Qt.darkGreen))
        except ApiException as e:
            self.new_simulation = None
            self.new_simulation_status = None
            error_body = e.body
            error_details = error_body["details"] if "details" in error_body else error_body
            error_msg = f"Error: {error_details}"
            self.parent_dock.communication.bar_error(error_msg, log_text_color=QColor(Qt.red))
        except Exception as e:
            self.new_simulation = None
            self.new_simulation_status = None
            error_msg = f"Error: {e}"
            self.parent_dock.communication.bar_error(error_msg, log_text_color=QColor(Qt.red))
