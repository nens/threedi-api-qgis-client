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
from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import QWizardPage, QWizard, QGridLayout, QSizePolicy, QFileDialog
from ..utils import icon_path, set_widget_background_color, mmh_to_ms
from ..api_calls.threedi_calls import ThreediCalls, ApiException


base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_p1, basecls_p1 = uic.loadUiType(os.path.join(base_dir, 'ui', 'page1.ui'))
uicls_p2, basecls_p2 = uic.loadUiType(os.path.join(base_dir, 'ui', 'page2.ui'))
uicls_p3, basecls_p3 = uic.loadUiType(os.path.join(base_dir, 'ui', 'page3.ui'))
uicls_p4, basecls_p4 = uic.loadUiType(os.path.join(base_dir, 'ui', 'page4.ui'))

CONSTANT_RAIN = "Constant"
CUSTOM_RAIN = "Custom"
DESIGN_RAIN = "Design"


class SourceWidget(uicls_p1, basecls_p1):
    """Widget for Source page."""
    def __init__(self, parent_page):
        super(SourceWidget, self).__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path('sim_wizard_p1.svg'))
        self.svg_lout.addWidget(self.svg_widget)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)
        line_edit = self.cbo_db.lineEdit()
        line_edit.setPlaceholderText('Choose database')


class SimulationDurationWidget(uicls_p2, basecls_p2):
    """Widget for Simulation Duration page."""
    def __init__(self, parent_page):
        super(SimulationDurationWidget, self).__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path('sim_wizard_p2.svg'))
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

    def calculate_duration(self):
        """Method for simulation duration calculations."""
        try:
            start, end = self.to_datetime()
            delta = end - start
            return delta.total_seconds()
        except ValueError:
            self.label_total_time.setText('Invalid datetime format!')
            return 0.0

    def update_time_difference(self):
        """Updating label with simulation duration showed in the human readable format."""
        try:
            start, end = self.to_datetime()
            rel_delta = relativedelta(end, start)
            duration = (rel_delta.years, rel_delta.months, rel_delta.days, rel_delta.hours, rel_delta.minutes)
            self.label_total_time.setText('{} years, {} months, {} days, {} hours, {} minutes'.format(*duration))
        except ValueError:
            self.label_total_time.setText('Invalid datetime format!')


class PrecipitationWidget(uicls_p3, basecls_p3):
    """Widget for Precipitation page."""
    UNITS_DIVIDERS = {'s': 1, 'mins': 60, 'hrs': 3600}
    UNITS_MULTIPLIERS = {'s': 3600, 'mins': 60, 'hrs': 1}

    def __init__(self, parent_page):
        super(PrecipitationWidget, self).__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path('sim_wizard_p3.svg'))
        self.svg_lout.addWidget(self.svg_widget)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)
        self.current_units = 's'
        self.duration = 0
        self.total_precipitation = 0
        self.custom_time_series = []
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(None)
        self.plot_widget.setMaximumHeight(80)
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
        self.start_after_constant_u.currentIndexChanged.connect(self.sync_units)
        self.stop_after_constant_u.currentIndexChanged.connect(self.sync_units)
        self.start_after_custom_u.currentIndexChanged.connect(self.sync_units)
        self.stop_after_custom_u.currentIndexChanged.connect(self.sync_units)
        self.start_after_design_u.currentIndexChanged.connect(self.sync_units)
        self.cbo_prec_type.currentIndexChanged.connect(self.precipitation_changed)
        self.le_intensity.textChanged.connect(self.plot_precipitation)
        self.pb_csv.clicked.connect(self.set_custom_time_series)
        self.sp_start_after_constant.valueChanged.connect(self.plot_precipitation)
        self.sp_stop_after_constant.valueChanged.connect(self.plot_precipitation)
        self.sp_start_after_custom.valueChanged.connect(self.plot_precipitation)
        self.sp_stop_after_custom.valueChanged.connect(self.plot_precipitation)
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
            if self.start_after_custom_u.currentIndex != idx:
                self.start_after_custom_u.setCurrentIndex(idx)
            if self.stop_after_custom_u.currentIndex != idx:
                self.stop_after_custom_u.setCurrentIndex(idx)
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
        self.duration = self.parent_page.parent_wizard.p2.main_widget.calculate_duration()

    def duration_in_units(self):
        """Calculating duration in currently selected units."""
        unit_divider = self.UNITS_DIVIDERS[self.current_units]
        duration_in_units = int(self.duration / unit_divider)
        return duration_in_units

    def set_custom_time_series(self):
        """Selecting and setting up rain time series from CSV format."""
        last_folder = QSettings().value("threedi/last_folder", os.path.expanduser("~"), type=str)
        file_filter = "CSV (*.csv );;All Files (*)"
        filename, __ = QFileDialog.getOpenFileName(self, "Precipitation Time Series", last_folder, file_filter)
        if len(filename) == 0:
            return
        QSettings().setValue("threedi/last_folder", os.path.dirname(filename))
        time_series = []
        with open(filename) as rain_file:
            rain_reader = csv.reader(rain_file)
            for row in rain_reader:
                time_series.append([float(v) for v in row])
        self.custom_time_series = time_series
        self.plot_precipitation()

    def get_intensity(self):
        """Getting intensity value for the Constant precipitation type."""
        try:
            intensity = float(self.le_intensity.text())
        except ValueError:
            return 0.0
        return intensity

    def get_precipitation_offset(self):
        """Calculating precipitation offset in seconds."""
        current_text = self.cbo_prec_type.currentText()
        units_multiplier = self.UNITS_DIVIDERS[self.current_units]
        if current_text == CONSTANT_RAIN:
            start = self.sp_start_after_constant.value()
        elif current_text == CUSTOM_RAIN:
            start = self.sp_start_after_custom.value()
        else:
            return 0.0
        offset = start * units_multiplier
        return offset

    def get_precipitation_duration(self):
        """Calculating precipitation duration in seconds."""
        current_text = self.cbo_prec_type.currentText()
        units_multiplier = self.UNITS_DIVIDERS[self.current_units]
        if current_text == CONSTANT_RAIN:
            start = self.sp_start_after_constant.value()
            end = self.sp_stop_after_constant.value()
        elif current_text == CUSTOM_RAIN:
            start = self.sp_start_after_custom.value()
            end = self.sp_stop_after_custom.value()
        else:
            return self.duration
        if start == 0 and end == 0:
            duration = self.duration
        else:
            duration = (end * units_multiplier) - (start * units_multiplier)
        return duration

    def get_precipitation_values(self):
        """Calculating precipitation values in 'm/s'."""
        current_text = self.cbo_prec_type.currentText()
        if current_text == CONSTANT_RAIN:
            values = mmh_to_ms(self.get_intensity())
        elif current_text == CUSTOM_RAIN:
            unit_multiplier = self.UNITS_MULTIPLIERS[self.current_units]
            values = [[t*unit_multiplier, mmh_to_ms(v)] for t, v in self.custom_time_series]
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
        start = self.sp_start_after_constant.value()
        end = self.sp_stop_after_constant.value()
        if start < 0:
            start = 0
        if end > duration_in_units or end == 0:
            end = duration_in_units
        x_values += [x for x in list(range(duration_in_units + 1)) if start <= x <= end]
        y_values += [intensity] * len(x_values)
        return x_values, y_values

    def custom_values(self):
        """Getting plot values for the Custom precipitation."""
        x_values, y_values = [], []
        duration_in_units = self.duration_in_units()
        start = self.sp_start_after_custom.value()
        end = self.sp_stop_after_custom.value()
        if start < 0:
            start = 0
        if end > duration_in_units or end == 0:
            end = duration_in_units
        for x, y in self.custom_time_series:
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                return [], []
            if start <= x <= end:
                x_values.append(x)
                y_values.append(y)
            else:
                continue
        return x_values, y_values

    def design_values(self):
        """Getting plot values for the Design precipitation."""
        x_values, y_values = [], []
        #  TODO: Add handling for Design
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
        time_interval = x_values[1] - x_values[0]
        # Adding ticks in minutes
        dx = [(value, f"{value} ({self.current_units})") for value in x_values]
        self.plot_ticks = [[dx[0], dx[-1]]]
        ax = self.plot_widget.getAxis('bottom')
        ax.setTicks(self.plot_ticks)
        self.plot_bar_graph = pg.BarGraphItem(x=x_values, height=y_values, width=time_interval, brush=QColor('#1883D7'))
        self.plot_widget.addItem(self.plot_bar_graph)
        unit_multiplier = self.UNITS_MULTIPLIERS[self.current_units]
        if current_text == CONSTANT_RAIN:
            precipitation_values = y_values[:-1]
        else:
            precipitation_values = y_values
        self.total_precipitation = sum(v/unit_multiplier * time_interval for v in precipitation_values)
        #  self.plot_widget.setXRange(0, duration_in_units)


class SummaryWidget(uicls_p4, basecls_p4):
    """Widget for Summary page."""
    def __init__(self, parent_page):
        super(SummaryWidget, self).__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.svg_widget = QSvgWidget(icon_path('sim_wizard_p4.svg'))
        self.svg_lout.addWidget(self.svg_widget)
        set_widget_background_color(self.svg_widget)
        set_widget_background_color(self)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(None)
        self.plot_widget.setMaximumHeight(60)
        self.lout_plot.addWidget(self.plot_widget, 0, 0)

    def plot_overview_precipitation(self):
        """Setting up precipitation plot."""
        self.plot_widget.clear()
        plot_bar_graph = self.parent_page.parent_wizard.p3.main_widget.plot_bar_graph
        plot_ticks = self.parent_page.parent_wizard.p3.main_widget.plot_ticks
        if plot_bar_graph is None:
            return
        new_bar_graph = pg.BarGraphItem(**plot_bar_graph.opts)
        ax = self.plot_widget.getAxis('bottom')
        ax.setTicks(plot_ticks)
        self.plot_widget.addItem(new_bar_graph)


class Page1(QWizardPage):
    """Source definition page."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = SourceWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget, 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class Page2(QWizardPage):
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


class Page3(QWizardPage):
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


class Page4(QWizardPage):
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
        self.p1 = Page1(self)
        self.p2 = Page2(self)
        self.p3 = Page3(self)
        self.p4 = Page4(self)
        self.addPage(self.p1)
        self.addPage(self.p2)
        self.addPage(self.p3)
        self.addPage(self.p4)
        self.currentIdChanged.connect(self.page_changed)
        self.finish_btn = self.button(QWizard.FinishButton)
        self.finish_btn.clicked.connect(self.run_new_simulation)
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
        database = self.p1.main_widget.cbo_db.currentText()
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
        self.p4.main_widget.sim_prec_total.setText(f"{int(total_precipitation)} mm")

    def run_new_simulation(self):
        """Getting data from the wizard and running new simulation."""
        name = self.p1.main_widget.le_sim_name.text()
        threedimodel = self.p1.main_widget.cbo_db.currentData()
        organisation = self.parent_dock.organisation.unique_id
        start_datetime = datetime.utcnow()
        duration = self.p3.main_widget.duration
        try:
            tc = ThreediCalls(self.parent_dock.api_client)
            new_simulation = tc.new_simulation(name=name, threedimodel=threedimodel, start_datetime=start_datetime,
                                               organisation=organisation, duration=duration)
            sim_id = new_simulation.id
            ptype, poffset, pduration, punits, pvalues = self.p3.main_widget.get_precipitation_data()
            if ptype == CONSTANT_RAIN:
                tc.add_constant_precipitation(sim_id, value=pvalues, units=punits, duration=pduration, offset=poffset)
            elif ptype == CUSTOM_RAIN:
                tc.add_custom_precipitation(sim_id, values=pvalues, units=punits, duration=pduration, offset=poffset)
            tc.make_action_on_simulation(sim_id, name='start')
            self.parent_dock.communication.bar_info(f"Simulation {new_simulation.name} started!")
        except ApiException as e:
            self.parent_dock.communication.bar_error(e.body)
