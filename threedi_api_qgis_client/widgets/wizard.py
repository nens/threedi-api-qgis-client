# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
import json
from datetime import datetime
from qgis.PyQt.QtSvg import QSvgWidget
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QColor

from qgis.PyQt.QtWidgets import QWizardPage, QWizard, QGridLayout, QSizePolicy, QInputDialog
from ..deps.custom_imports import pg, relativedelta
from ..utils import icon_path


base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_p1, basecls_p1 = uic.loadUiType(os.path.join(base_dir, 'ui', 'page1.ui'))
uicls_p2, basecls_p2 = uic.loadUiType(os.path.join(base_dir, 'ui', 'page2.ui'))
uicls_p3, basecls_p3 = uic.loadUiType(os.path.join(base_dir, 'ui', 'page3.ui'))
uicls_p4, basecls_p4 = uic.loadUiType(os.path.join(base_dir, 'ui', 'page4.ui'))


def set_widget_background_color(widget, hex_color='#F0F0F0'):
    palette = widget.palette()
    palette.setColor(widget.backgroundRole(), QColor(hex_color))
    widget.setPalette(palette)


class SourceWidget(uicls_p1, basecls_p1):
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
        date_from = self.date_from.dateTime().toString('yyyy-MM-dd')
        time_from = self.time_from.time().toString('H:m')
        date_to = self.date_to.dateTime().toString('yyyy-MM-dd')
        time_to = self.time_to.time().toString('H:m')
        start = datetime.strptime(f"{date_from} {time_from}", '%Y-%m-%d %H:%M')
        end = datetime.strptime(f"{date_to} {time_to}", '%Y-%m-%d %H:%M')
        return start, end

    def calculate_duration(self):
        try:
            start, end = self.to_datetime()
            delta = end - start
            return delta.total_seconds()
        except ValueError as e:
            self.label_total_time.setText('Invalid datetime format!')
            return 0.0

    def update_time_difference(self):
        try:
            start, end = self.to_datetime()
            rel_delta = relativedelta(end, start)
            duration = (rel_delta.years, rel_delta.months, rel_delta.days, rel_delta.hours, rel_delta.minutes)
            self.label_total_time.setText('{} years, {} months, {} days, {} hours, {} minutes'.format(*duration))
        except ValueError:
            self.label_total_time.setText('Invalid datetime format!')


class PrecipitationWidget(uicls_p3, basecls_p3):
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
        self.custom_time_series = [[0, 200], [300, 300], [600, 400], [900, 200], [1200, 50]]
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(None)
        self.plot_widget.setMaximumHeight(60)
        self.plot_bar_graph = None
        self.plot_ticks = None
        self.lout_plot.addWidget(self.plot_widget, 0, 0)
        self.widget_constant.hide()
        self.widget_custom.hide()
        self.widget_design.hide()
        self.connect_signals()
        self.plot_precipitation()

    def connect_signals(self):
        self.start_after_constant_u.currentIndexChanged.connect(self.sync_units)
        self.stop_after_constant_u.currentIndexChanged.connect(self.sync_units)
        self.start_after_custom_u.currentIndexChanged.connect(self.sync_units)
        self.stop_after_custom_u.currentIndexChanged.connect(self.sync_units)
        self.start_after_design_u.currentIndexChanged.connect(self.sync_units)
        self.cbo_prec_type.currentIndexChanged.connect(self.precipitation_changed)
        self.le_intensity.textChanged.connect(self.plot_precipitation)
        self.pb_set.clicked.connect(self.set_custom_time_series)
        self.sp_start_after_constant.valueChanged.connect(self.plot_precipitation)
        self.sp_stop_after_constant.valueChanged.connect(self.plot_precipitation)
        self.sp_start_after_custom.valueChanged.connect(self.plot_precipitation)
        self.sp_stop_after_custom.valueChanged.connect(self.plot_precipitation)
        self.sp_start_after_design.valueChanged.connect(self.plot_precipitation)

    def sync_units(self, idx):
        current_text = self.cbo_prec_type.currentText()
        if current_text == 'Constant':
            if self.start_after_constant_u.currentIndex != idx:
                self.start_after_constant_u.setCurrentIndex(idx)
            if self.stop_after_constant_u.currentIndex != idx:
                self.stop_after_constant_u.setCurrentIndex(idx)
            self.current_units = self.start_after_constant_u.currentText()
        elif current_text == 'Custom':
            if self.start_after_custom_u.currentIndex != idx:
                self.start_after_custom_u.setCurrentIndex(idx)
            if self.stop_after_custom_u.currentIndex != idx:
                self.stop_after_custom_u.setCurrentIndex(idx)
            self.current_units = self.start_after_custom_u.currentText()
        elif current_text == 'Design':
            self.current_units = self.start_after_design_u.currentText()
        self.plot_precipitation()

    def refresh_current_units(self):
        current_text = self.cbo_prec_type.currentText()
        if current_text == 'Constant':
            self.current_units = self.start_after_constant_u.currentText()
        elif current_text == 'Custom':
            self.current_units = self.start_after_custom_u.currentText()
        elif current_text == 'Design':
            self.current_units = self.start_after_design_u.currentText()

    def precipitation_changed(self, idx):
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

    def refresh_duration(self):
        self.duration = self.parent_page.parent_wizard.p2.main_widget.calculate_duration()

    def duration_in_units(self):
        unit_divider = self.UNITS_DIVIDERS[self.current_units]
        duration_in_units = int(self.duration / unit_divider)
        return duration_in_units

    def get_intensity(self):
        try:
            intensity = float(self.le_intensity.text())
        except ValueError:
            return 0.0
        return intensity

    def constant_values(self):
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
        x_values, y_values = [], []
        #  TODO: Add handling for Design
        return x_values, y_values

    def set_custom_time_series(self):
        text_ts = json.dumps(self.custom_time_series) if self.custom_time_series else ''
        text, ok = QInputDialog.getMultiLineText(None, 'Precipitation Time Series', '', text=text_ts)
        if ok is False:
            return
        try:
            time_series = json.loads(text)
        except json.JSONDecodeError as e:
            return
        self.custom_time_series = time_series
        self.plot_precipitation()

    def plot_precipitation(self):
        self.refresh_duration()
        self.plot_widget.clear()
        self.plot_bar_graph = None
        self.plot_ticks = None
        current_text = self.cbo_prec_type.currentText()
        if current_text == 'Constant':
            x_values, y_values = self.constant_values()
        elif current_text == 'Custom':
            x_values, y_values = self.custom_values()
        elif current_text == 'Design':
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
        if current_text == 'Constant':
            precipitation_values = y_values[:-1]
        else:
            precipitation_values = y_values
        self.total_precipitation = sum(v/unit_multiplier * time_interval for v in precipitation_values)
        #  self.plot_widget.setXRange(0, duration_in_units)


class SummaryWidget(uicls_p4, basecls_p4):
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWizardStyle(QWizard.ClassicStyle)
        self.p1 = Page1(self)
        self.p2 = Page2(self)
        self.p3 = Page3(self)
        self.p4 = Page4(self)
        self.addPage(self.p1)
        self.addPage(self.p2)
        self.addPage(self.p3)
        self.addPage(self.p4)
        self.currentIdChanged.connect(self.page_changed)
        self.setWindowTitle("New simulation")
        self.setStyleSheet("background-color:#F0F0F0")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.resize(750, 500)

    def page_changed(self, page_id):
        if page_id == 2:
            self.p3.main_widget.plot_precipitation()
        elif page_id == 3:
            self.p4.main_widget.plot_overview_precipitation()
            self.set_overview_name()
            self.set_overview_database()
            self.set_overview_duration()
            self.set_overview_precipitation()

    def set_overview_name(self):
        name = self.p1.main_widget.le_sim_name.text()
        self.p4.main_widget.sim_name.setText(name)

    def set_overview_database(self):
        database = self.p1.main_widget.cbo_db.currentText()
        self.p4.main_widget.sim_database.setText(database)

    def set_overview_duration(self):
        duration = self.p2.main_widget.label_total_time.text()
        self.p4.main_widget.sim_duration.setText(duration)

    def set_overview_precipitation(self):
        precipitation_type = self.p3.main_widget.cbo_prec_type.currentText()
        total_precipitation = self.p3.main_widget.total_precipitation
        self.p4.main_widget.sim_prec_type.setText(precipitation_type)
        self.p4.main_widget.sim_prec_total.setText(f"{int(total_precipitation)} mm")
