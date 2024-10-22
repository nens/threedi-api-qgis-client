# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import csv
import logging
import os
from collections import OrderedDict, defaultdict
from copy import deepcopy
from datetime import datetime
from functools import partial
from operator import attrgetter
from typing import List, Optional

import pyqtgraph as pg
from dateutil.relativedelta import relativedelta
from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapToolIdentifyFeature
from qgis.PyQt import uic
from qgis.PyQt.QtCore import (QDateTime, QSettings, QSize, Qt, QTimeZone,
                              pyqtSignal)
from qgis.PyQt.QtGui import (QColor, QDoubleValidator, QFont, QStandardItem,
                             QStandardItemModel)
from qgis.PyQt.QtWidgets import (QComboBox, QDoubleSpinBox, QFileDialog,
                                 QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                                 QLineEdit, QRadioButton, QScrollArea,
                                 QSizePolicy, QSpacerItem, QSpinBox,
                                 QTableWidgetItem, QWidget, QWizard,
                                 QWizardPage)
from threedi_api_client.openapi import ApiException, Threshold

from ..api_calls.threedi_calls import ThreediCalls
from ..data_models import simulation_data_models as dm
from ..utils import (TEMPDIR, EventTypes, apply_24h_timeseries,
                     convert_timeseries_to_seconds, extract_error_message,
                     get_download_file, handle_csv_header, intervals_are_even,
                     mmh_to_mmtimestep, mmh_to_ms, mmtimestep_to_mmh,
                     ms_to_mmh, parse_timeseries, read_json_data)
from ..utils_ui import (NumericDelegate, get_filepath,
                        qgis_layers_cbo_get_layer_uri, read_3di_settings,
                        save_3di_settings, scan_widgets_parameters,
                        set_widget_background_color, set_widgets_parameters)
from .custom_items import FilteredComboBox
from .initial_concentrations import (Initial1DConcentrationsWidget,
                                     Initial2DConcentrationsWidget)
from .substance_concentrations import SubstanceConcentrationsWidget

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_name_page, basecls_name_page = uic.loadUiType(os.path.join(base_dir, "ui", "simulation_wizard", "page_name.ui"))
uicls_duration_page, basecls_duration_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "simulation_wizard", "page_duration.ui")
)
uicls_substances, basecls_substances = uic.loadUiType(
    os.path.join(base_dir, "ui", "simulation_wizard", "page_substances.ui")
)
uicls_boundary_conditions, basecls_boundary_conditions = uic.loadUiType(
    os.path.join(base_dir, "ui", "simulation_wizard", "page_boundary_conditions.ui")
)
uicls_structure_controls, basecls_structure_controls = uic.loadUiType(
    os.path.join(base_dir, "ui", "simulation_wizard", "page_structure_controls.ui")
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
uicls_lizard_post_processing_page, basecls_lizard_post_processing_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "simulation_wizard", "page_lizard_post_processing.ui")
)

uicls_saved_state_page, basecls_saved_state_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "simulation_wizard", "page_saved_state.ui")
)

uicls_summary_page, basecls_summary_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "simulation_wizard", "page_initiation.ui")
)
logger = logging.getLogger(__name__)


class NameWidget(uicls_name_page, basecls_name_page):
    """Widget for the Name page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        set_widget_background_color(self)


class SimulationDurationWidget(uicls_duration_page, basecls_duration_page):
    """Widget for the Simulation Duration page."""

    UTC_DISPLAY_NAME = "UTC"

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        set_widget_background_color(self)
        self.settings = QSettings()
        self.date_from.dateTimeChanged.connect(self.update_time_difference)
        self.date_to.dateTimeChanged.connect(self.update_time_difference)
        self.time_from.dateTimeChanged.connect(self.update_time_difference)
        self.time_to.dateTimeChanged.connect(self.update_time_difference)
        self.timezone_template = self.label_utc_info.text()
        self.setup_timezones()
        self.grp_timezone.toggled.connect(self.on_timezone_applied)
        self.cbo_timezone.currentTextChanged.connect(self.on_timezone_change)

    def setup_timezones(self):
        """Populate timezones."""
        default_timezone = self.settings.value("threedi/timezone", self.UTC_DISPLAY_NAME)
        for timezone_id in QTimeZone.availableTimeZoneIds():
            timezone_text = timezone_id.data().decode()
            timezone = QTimeZone(timezone_id)
            self.cbo_timezone.addItem(timezone_text, timezone)
        self.cbo_timezone.setCurrentText(default_timezone)
        self.on_timezone_change(default_timezone)

    def on_timezone_applied(self):
        """Method for handling timezone group toggling."""
        self.on_timezone_change(self.cbo_timezone.currentText())

    def on_timezone_change(self, timezone_id_str):
        """Method for handling timezone change."""
        self.update_time_difference()
        if self.grp_timezone.isChecked():
            if timezone_id_str == self.UTC_DISPLAY_NAME:
                self.label_utc_info.hide()
            else:
                self.label_utc_info.show()
        else:
            self.label_utc_info.hide()
        self.settings.setValue("threedi/timezone", timezone_id_str)

    def to_datetime(self):
        """Method for QDateTime ==> datetime conversion."""
        date_from = self.date_from.date()
        time_from = self.time_from.time()
        date_to = self.date_to.date()
        time_to = self.time_to.time()
        if self.grp_timezone.isChecked() and self.cbo_timezone.currentText() != self.UTC_DISPLAY_NAME:
            current_timezone = self.cbo_timezone.currentData()
            datetime_from = QDateTime(date_from, time_from, current_timezone)
            datetime_to = QDateTime(date_to, time_to, current_timezone)
            datetime_from_utc = datetime_from.toUTC()
            datetime_to_utc = datetime_to.toUTC()
            date_from, time_from = datetime_from_utc.date(), datetime_from_utc.time()
            date_to, time_to = datetime_to_utc.date(), datetime_to_utc.time()
        date_from_str = date_from.toString("yyyy-MM-dd")
        time_from_str = time_from.toString("H:m")
        date_to_str = date_to.toString("yyyy-MM-dd")
        time_to_str = time_to.toString("H:m")
        start = datetime.strptime(f"{date_from_str} {time_from_str}", "%Y-%m-%d %H:%M")
        end = datetime.strptime(f"{date_to_str} {time_to_str}", "%Y-%m-%d %H:%M")
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
        """Updating label with simulation duration showed in the human-readable format."""
        try:
            start, end = self.to_datetime()
            if start > end:
                start = end
            rel_delta = relativedelta(end, start)
            duration = (rel_delta.years, rel_delta.months, rel_delta.days, rel_delta.hours, rel_delta.minutes)
            self.label_total_time.setText("{} years, {} months, {} days, {} hours, {} minutes".format(*duration))
            self.label_utc_info.setText(self.timezone_template.format(start, end))
        except ValueError:
            self.label_total_time.setText("Invalid datetime format!")


class SubstancesWidget(uicls_substances, basecls_substances):
    """Widget for the Substances page."""

    MINIMUM_WIDTH = 100

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.substances = []
        set_widget_background_color(self)
        self.connect_signals()
        self.init_table()
        self.add_item()  # Add an empty row by default

    def connect_signals(self):
        """Connecting widgets signals."""
        self.pb_add.clicked.connect(self.add_item)
        self.pb_remove.clicked.connect(self.remove_items)
        self.tw_substances.itemChanged.connect(self.handle_item_changed)

    def init_table(self):
        """Initialize substances table."""
        NAME_COLUMN = 0
        DECAY_COEFFICIENT_COLUMN = 2
        DIFFUSION_COEFFICIENT_COLUMN = 3

        # Set minimum width for the columns
        self.tw_substances.setColumnWidth(NAME_COLUMN, self.MINIMUM_WIDTH)  # Name
        self.tw_substances.setColumnWidth(DECAY_COEFFICIENT_COLUMN, 160)  # Decay coefficient
        self.tw_substances.setColumnWidth(DIFFUSION_COEFFICIENT_COLUMN, 160)  # Diffusion coefficient
        # Set the numeric delegate for the decay coefficient column
        numeric_delegate = NumericDelegate(self.tw_substances)
        self.tw_substances.setItemDelegateForColumn(DECAY_COEFFICIENT_COLUMN, numeric_delegate)
        self.tw_substances.setItemDelegateForColumn(DIFFUSION_COEFFICIENT_COLUMN, numeric_delegate)

    def prepopulate_substances_table(self, substances):
        self.tw_substances.setRowCount(0)
        for substance in substances:
            self.add_item()
            row = self.tw_substances.rowCount() - 1
            name = substance.get("name", "")
            units = substance.get("units", "")
            decay_coefficient = substance.get("decay_coefficient", "")
            diffusion_coefficient = substance.get("diffusion_coefficient", "")
            if name:
                name_item = QTableWidgetItem(name)
                units_item = QTableWidgetItem(units)
                decay_coefficient_item = QTableWidgetItem(str(decay_coefficient))
                diffusion_coefficient_item = QTableWidgetItem(str(diffusion_coefficient))
                self.tw_substances.setItem(row, 0, name_item)
                self.tw_substances.setItem(row, 1, units_item)
                self.tw_substances.setItem(row, 2, decay_coefficient_item)
                self.tw_substances.setItem(row, 3, diffusion_coefficient_item)
        self.set_substances_data()
        self.update_substances()

    def add_item(self):
        row_count = self.tw_substances.rowCount()
        self.tw_substances.insertRow(row_count)
        self.tw_substances.setItem(row_count, 0, QTableWidgetItem())
        self.tw_substances.setItem(row_count, 1, QTableWidgetItem())
        self.tw_substances.setItem(row_count, 2, QTableWidgetItem())
        self.tw_substances.setItem(row_count, 3, QTableWidgetItem())

    def remove_items(self):
        selected_rows = set()
        for item in self.tw_substances.selectedItems():
            selected_rows.add(item.row())
        for row in sorted(selected_rows, reverse=True):
            self.tw_substances.removeRow(row)
            # Remove item from the substances list
            if row < len(self.substances):
                del self.substances[row]
                self.update_substances()

    def handle_item_changed(self, item):
        # Check for duplicate names
        if item.column() == 0:
            row_count = self.tw_substances.rowCount()
            for row in range(row_count):
                if row == item.row():
                    continue
                name_item = self.tw_substances.item(row, 0)
                if name_item and name_item.text() and name_item.text() == item.text():
                    self.parent_page.parent_wizard.plugin_dock.communication.show_warn(
                        "Substance with the same name already exists!"
                    )
                    item.setText("")
        # Check for units length
        units_length = 16
        if item.column() == 1:
            if len(item.text()) > units_length:
                item.setText(item.text()[:units_length])
                self.parent_page.parent_wizard.plugin_dock.communication.show_warn(
                    "Units length should be less than 16 characters!"
                )
        if item.column() == 3:
            if item.text():
                if float(item.text()) < 0 or float(item.text()) > 1:
                    self.parent_page.parent_wizard.plugin_dock.communication.show_warn(
                        "Diffusion coefficient should be between 0 and 1"
                    )
                    item.setText("")
        # Resize name column to contents and enforce minimum width
        self.tw_substances.resizeColumnToContents(0)
        if self.tw_substances.columnWidth(0) < self.MINIMUM_WIDTH:
            self.tw_substances.setColumnWidth(0, self.MINIMUM_WIDTH)
        self.set_substances_data()
        self.update_substances()

    def set_substances_data(self):
        """Setting substances data."""
        self.substances.clear()
        row_count = self.tw_substances.rowCount()
        for row in range(row_count):
            name_item = self.tw_substances.item(row, 0)
            units_item = self.tw_substances.item(row, 1)
            decay_coefficient_item = self.tw_substances.item(row, 2)
            diffusion_coefficient_item = self.tw_substances.item(row, 3)
            
            if name_item and units_item and decay_coefficient_item and diffusion_coefficient_item:
                name = name_item.text()
                units = units_item.text()
                decay_coefficient = decay_coefficient_item.text()
                diffusion_coefficient = diffusion_coefficient_item.text()
                if name:
                    substance = {"name": name}
                    if units:
                        substance["units"] = units
                    if decay_coefficient:
                        substance["decay_coefficient"] = decay_coefficient
                    if diffusion_coefficient:
                        substance["diffusion_coefficient"] = float(diffusion_coefficient)
                    self.substances.append(substance)

    def update_substances(self):
        if hasattr(self.parent_page.parent_wizard, "boundary_conditions_page"):
            self.parent_page.parent_wizard.boundary_conditions_page.main_widget.setup_substance_concentrations()
        if hasattr(self.parent_page.parent_wizard, "laterals_page"):
            self.parent_page.parent_wizard.laterals_page.main_widget.setup_substance_concentrations()
        if hasattr(self.parent_page.parent_wizard, "init_conditions_page"):
            self.parent_page.parent_wizard.init_conditions_page.main_widget.setup_2d_initial_concentrations()
            self.parent_page.parent_wizard.init_conditions_page.main_widget.setup_1d_initial_concentrations()


class BoundaryConditionsWidget(uicls_boundary_conditions, basecls_boundary_conditions):
    """Widget for the Boundary Conditions page."""

    TYPE_1D = "1D"
    TYPE_2D = "2D"

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.current_model = parent_page.parent_wizard.model_selection_dlg.current_model
        self.substances = (
            parent_page.parent_wizard.substances_page.main_widget.substances
            if hasattr(parent_page.parent_wizard, "substances_page")
            else []
        )
        set_widget_background_color(self)
        self.template_boundary_conditions = None
        self.template_boundary_conditions_1d_timeseries = []
        self.template_boundary_conditions_2d_timeseries = []
        self.boundary_conditions_1d_timeseries = []
        self.boundary_conditions_2d_timeseries = []
        self.substance_concentrations_1d = {}
        self.substance_concentrations_2d = {}
        self.connect_signals()

    def connect_signals(self):
        """Connecting widgets signals."""
        self.rb_from_template.toggled.connect(self.change_boundary_conditions_source)
        self.rb_upload_file.toggled.connect(self.change_boundary_conditions_source)
        self.pb_upload_file_bc_1d.clicked.connect(partial(self.load_csv, self.TYPE_1D))
        self.pb_upload_file_bc_2d.clicked.connect(partial(self.load_csv, self.TYPE_2D))
        self.cb_interpolate_bc_1d.stateChanged.connect(partial(self.interpolate_changed, self.TYPE_1D))
        self.cb_interpolate_bc_2d.stateChanged.connect(partial(self.interpolate_changed, self.TYPE_2D))

    def setup_substance_concentrations(self):
        if hasattr(self, "groupbox"):
            self.groupbox.setParent(None)
        if not self.substances:
            return
        substance_concentration_widget = SubstanceConcentrationsWidget(
            self.substances, self.current_model, self.handle_substance_errors
        )
        self.groupbox = substance_concentration_widget.groupbox
        self.substance_concentrations_1d = substance_concentration_widget.substance_concentrations_1d
        self.substance_concentrations_2d = substance_concentration_widget.substance_concentrations_2d
        parent_layout = self.layout()
        parent_layout.addWidget(self.groupbox, 6, 2)

    def handle_substance_errors(self, header, substance_list, bc_type, units):
        """
        First, check if boundary condition values are available.
        Second, check if substance concentrations timesteps match exactly the boundary condition values timesteps.
        Return None if they match or error message if not.
        """
        error_message = handle_csv_header(header)
        bc_timeseries = []
        if bc_type == self.TYPE_1D:
            if self.rb_from_template.isChecked():
                bc_timeseries = self.template_boundary_conditions_1d_timeseries
            else:
                bc_timeseries = self.boundary_conditions_1d_timeseries
        else:
            if self.rb_from_template.isChecked():
                bc_timeseries = self.template_boundary_conditions_2d_timeseries
            else:
                bc_timeseries = self.boundary_conditions_2d_timeseries
        if not bc_timeseries:
            if self.rb_from_template.isChecked():
                error_message = "No boundary conditions found in template file!"
            else:
                error_message = "No boundary conditions uploaded yet!"
        if not substance_list:
            error_message = "CSV file is empty!"
        if error_message is None:
            for substance in substance_list:
                bc_id = int(substance.get("id"))
                timeseries = substance.get("timeseries")
                boundary_condition = next((bc for bc in bc_timeseries if bc["id"] == bc_id), None)
                if boundary_condition is None:
                    error_message = f"Boundary condition with ID {bc_id} not found!"
                    break
                bc_values = boundary_condition["values"]
                bc_units = (
                    self.cbo_bc_units_1d.currentText()
                    if bc_type == self.TYPE_1D
                    else self.cbo_bc_units_2d.currentText()
                )
                converted_bc_values = convert_timeseries_to_seconds(bc_values, bc_units)
                bc_timesteps = [t for (t, _) in converted_bc_values]
                concentrations = parse_timeseries(timeseries)
                converted_concentrations = convert_timeseries_to_seconds(concentrations, units)
                concentrations_timesteps = [t for (t, _) in converted_concentrations]
                if bc_timesteps != concentrations_timesteps:
                    error_message = (
                        "Substance concentrations timesteps do not match boundary condition values timesteps!"
                    )
                    break
        if error_message is not None:
            self.parent_page.parent_wizard.plugin_dock.communication.show_warn(error_message)
        return error_message

    def set_template_boundary_conditions(self, template_boundary_conditions=None):
        """Setting boundary conditions data derived from the simulation template."""
        if template_boundary_conditions is not None:
            self.template_boundary_conditions = template_boundary_conditions
            self.rb_from_template.setEnabled(True)
            self.rb_from_template.setChecked(True)
        else:
            self.rb_from_template.setDisabled(True)
            self.rb_upload_file.setChecked(True)

    def change_boundary_conditions_source(self):
        """Disable/enable widgets based on the boundary conditions source."""
        if self.rb_from_template.isChecked():
            self.gb_upload_1d.setChecked(False)
            self.gb_upload_2d.setChecked(False)
            self.gb_upload_1d.setDisabled(True)
            self.gb_upload_2d.setDisabled(True)
        if self.rb_upload_file.isChecked():
            self.gb_upload_1d.setEnabled(True)
            self.gb_upload_2d.setEnabled(True)

    def load_csv(self, boundary_conditions_type):
        """Load boundary conditions from the CSV file."""
        values, filename = self.open_upload_dialog(boundary_conditions_type)
        if not filename:
            return
        if boundary_conditions_type == self.TYPE_1D:
            self.file_bc_1d_upload.setText(filename)
            self.boundary_conditions_1d_timeseries = values
        elif boundary_conditions_type == self.TYPE_2D:
            self.file_bc_2d_upload.setText(filename)
            self.boundary_conditions_2d_timeseries = values
        else:
            raise NotImplementedError

    def open_upload_dialog(self, boundary_conditions_type):
        """Open dialog for selecting CSV file with boundary conditions."""
        last_folder = read_3di_settings("last_boundary_conditions_folder", os.path.expanduser("~"))
        file_filter = "CSV (*.csv );;All Files (*)"
        filename, __ = QFileDialog.getOpenFileName(self, "Boundary Conditions Time Series", last_folder, file_filter)
        if len(filename) == 0:
            return None, None
        save_3di_settings("last_boundary_conditions_folder", os.path.dirname(filename))
        values = []
        with open(filename, encoding="utf-8-sig") as csvfile:
            reader = csv.DictReader(csvfile)
            header = reader.fieldnames
            boundary_conditions_list = list(reader)
        error_msg = handle_csv_header(header)
        if error_msg is not None:
            self.parent_page.parent_wizard.plugin_dock.communication.show_warn(error_msg)
            return None, None
        interpolate = (
            self.cb_interpolate_bc_1d.isChecked()
            if boundary_conditions_type == self.TYPE_1D
            else self.cb_interpolate_bc_2d.isChecked()
        )
        for row in boundary_conditions_list:
            bc_id = row.get("id")
            timeseries = row.get("timeseries")
            try:
                vals = parse_timeseries(timeseries)
                boundary_condition = {
                    "id": int(bc_id),
                    "type": boundary_conditions_type,
                    "interpolate": interpolate,
                    "values": vals,
                }
                values.append(boundary_condition)
            except ValueError:
                continue
        return values, filename

    def interpolate_changed(self, boundary_conditions_type):
        """Handle interpolate checkbox."""
        boundary_conditions_timeseries = (
            self.boundary_conditions_1d_timeseries
            if boundary_conditions_type == self.TYPE_1D
            else self.boundary_conditions_2d_timeseries
        )
        interpolate = (
            self.cb_interpolate_bc_1d.isChecked()
            if boundary_conditions_type == self.TYPE_1D
            else self.cb_interpolate_bc_2d.isChecked()
        )
        for val in boundary_conditions_timeseries:
            val["interpolate"] = interpolate

    def recalculate_boundary_conditions_timeseries(self, boundary_conditions_type, timesteps_in_seconds=False):
        """Recalculate boundary conditions timeseries (timesteps in seconds)."""
        boundary_conditions_timeseries = (
            self.boundary_conditions_1d_timeseries
            if boundary_conditions_type == self.TYPE_1D
            else self.boundary_conditions_2d_timeseries
        )
        if timesteps_in_seconds is False:
            return boundary_conditions_timeseries
        boundary_conditions_data = deepcopy(boundary_conditions_timeseries)
        units = (
            self.cbo_bc_units_1d.currentText()
            if boundary_conditions_type == self.TYPE_1D
            else self.cbo_bc_units_2d.currentText()
        )
        for val in boundary_conditions_data:
            val["values"] = convert_timeseries_to_seconds(val["values"], units)
        return boundary_conditions_data

    def recalculate_substances_timeseries(self, bc_type, timesteps_in_seconds=False):
        """Recalculate substances timeseries (timesteps in seconds)."""
        substance_concentrations = {}
        if bc_type == self.TYPE_1D:
            substance_concentrations.update(self.substance_concentrations_1d)
        else:
            substance_concentrations.update(self.substance_concentrations_2d)
        substances = deepcopy(substance_concentrations)
        substances_data = {}
        if bc_type == self.TYPE_1D:
            bc_timeseries = self.boundary_conditions_1d_timeseries
        else:
            bc_timeseries = self.boundary_conditions_2d_timeseries
        for bc in bc_timeseries:
            bc_id = str(bc["id"])
            if bc_id in substances:
                substances_data[bc_id] = substances[bc_id]
        if timesteps_in_seconds is False:
            return substances_data
        for bc_substances in substances_data.values():
            for substance in bc_substances:
                units = substance["units"]
                substance["concentrations"] = convert_timeseries_to_seconds(substance["concentrations"], units)
        return substances_data

    def update_boundary_conditions_with_substances(self, boundary_conditions_data, substances):
        """ "Update boundary conditions with substances."""
        for bc in boundary_conditions_data:
            bc_id = str(bc["id"])
            if bc_id in substances:
                bc["substances"] = substances[bc_id]

    def get_boundary_conditions_data(self, timesteps_in_seconds=False):
        """Get boundary conditions data."""
        boundary_conditions_data_1d = []
        boundary_conditions_data_2d = []
        if self.gb_upload_1d.isChecked():
            boundary_conditions_data_1d = self.recalculate_boundary_conditions_timeseries(
                self.TYPE_1D, timesteps_in_seconds
            )
            if self.substance_concentrations_1d:
                substances = self.recalculate_substances_timeseries(self.TYPE_1D, timesteps_in_seconds)
                self.update_boundary_conditions_with_substances(boundary_conditions_data_1d, substances)
        if self.gb_upload_2d.isChecked():
            boundary_conditions_data_2d = self.recalculate_boundary_conditions_timeseries(
                self.TYPE_2D, timesteps_in_seconds
            )
            if self.substance_concentrations_2d:
                substances = self.recalculate_substances_timeseries(self.TYPE_2D, timesteps_in_seconds)
                self.update_boundary_conditions_with_substances(boundary_conditions_data_2d, substances)
        boundary_conditions_data = boundary_conditions_data_1d + boundary_conditions_data_2d
        return self.template_boundary_conditions, boundary_conditions_data


class StructureControlsWidget(uicls_structure_controls, basecls_structure_controls):
    """Widget for the Structure Controls page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        set_widget_background_color(self)
        self.template_file_structure_controls = None
        self.template_memory_structure_controls = None
        self.template_table_structure_controls = None
        self.template_timed_structure_controls = None
        self.connect_signals()

    def connect_signals(self):
        """Connecting widgets signals."""
        self.gb_from_template.toggled.connect(self.toggle_template_structures)
        self.pb_upload_file_sc.clicked.connect(self.set_control_structure_file)

    def toggle_template_structures(self, checked):
        """Enabling/disabling template structure controls checkboxes."""
        if checked:
            if self.template_file_structure_controls is not None:
                self.cb_file_sc.setEnabled(True)
            else:
                self.cb_file_sc.setDisabled(True)
            if self.template_memory_structure_controls is not None:
                self.cb_memory_sc.setEnabled(True)
            else:
                self.cb_memory_sc.setDisabled(True)
            if self.template_table_structure_controls is not None:
                self.cb_table_sc.setEnabled(True)
            else:
                self.cb_table_sc.setDisabled(True)
            if self.template_timed_structure_controls is not None:
                self.cb_timed_sc.setEnabled(True)
            else:
                self.cb_timed_sc.setDisabled(True)

    def set_template_structure_controls(
        self,
        template_file_structure_controls=None,
        template_memory_structure_controls=None,
        template_table_structure_controls=None,
        template_timed_structure_controls=None,
    ):
        """Setting structure controls data derived from the simulation template."""
        if not any(
            [
                template_file_structure_controls,
                template_memory_structure_controls,
                template_table_structure_controls,
                template_timed_structure_controls,
            ]
        ):
            return
        if template_file_structure_controls is not None:
            self.template_file_structure_controls = template_file_structure_controls
            self.cb_file_sc.setChecked(True)
        if template_memory_structure_controls is not None:
            self.template_memory_structure_controls = template_memory_structure_controls
            self.cb_memory_sc.setChecked(True)
        if template_table_structure_controls is not None:
            self.template_table_structure_controls = template_table_structure_controls
            self.cb_table_sc.setChecked(True)
        if template_timed_structure_controls is not None:
            self.template_timed_structure_controls = template_timed_structure_controls
            self.cb_timed_sc.setChecked(True)
        self.gb_from_template.setEnabled(True)
        self.gb_from_template.setChecked(True)

    def set_control_structure_file(self):
        """Selecting and setting up structure control file in JSON format."""
        file_filter = "JSON (*.json);;All Files (*)"
        last_folder = QSettings().value("threedi/last_control_structure_file_folder", os.path.expanduser("~"), type=str)
        filename, __ = QFileDialog.getOpenFileName(self, "Select structure control file", last_folder, file_filter)
        if len(filename) == 0:
            return
        QSettings().setValue("threedi/last_control_structure_file_folder", os.path.dirname(filename))
        self.file_sc_upload.setText(filename)

    def get_structure_control_data(self):
        """Getting all needed data for adding structure controls to the simulation."""
        local_sc_filepath = self.file_sc_upload.text()
        structure_control_data = [
            self.template_file_structure_controls,
            self.template_memory_structure_controls,
            self.template_table_structure_controls,
            self.template_timed_structure_controls,
            local_sc_filepath if local_sc_filepath else None,
        ]
        return structure_control_data


class InitialConditionsWidget(uicls_initial_conds, basecls_initial_conds):
    """Widget for the Initial Conditions page."""

    def __init__(self, parent_page, initial_conditions=None):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.current_model = parent_page.parent_wizard.model_selection_dlg.current_model
        self.substances = (
            parent_page.parent_wizard.substances_page.main_widget.substances
            if hasattr(parent_page.parent_wizard, "substances_page")
            else []
        )
        set_widget_background_color(self)
        self.initial_saved_state = initial_conditions.initial_saved_state
        self.initial_waterlevels = {}
        self.initial_waterlevels_1d = {}
        self.saved_states = {}
        self.initial_concentrations_widget = QWidget()
        self.initial_concentrations_widget_1D = QWidget()
        self.rasters = []
        self.online_files = []
        self.local_data = {}
        self.gb_saved_state.setChecked(False)
        self.gb_1d.setChecked(False)
        self.gb_2d.setChecked(False)
        self.gb_groundwater.setChecked(False)
        self.cbo_2d_local_raster.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.cbo_gw_local_raster.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.btn_browse_2d_local_raster.clicked.connect(partial(self.browse_for_local_raster, self.cbo_2d_local_raster))
        self.btn_browse_gw_local_raster.clicked.connect(partial(self.browse_for_local_raster, self.cbo_gw_local_raster))
        self.btn_1d_upload_csv.clicked.connect(self.load_1d_initial_waterlevel_csv)
        self.setup_initial_conditions()
        self.setup_2d_initial_concentrations()
        self.setup_1d_initial_concentrations()
        self.connect_signals()

    def connect_signals(self):
        """Connecting widgets signals."""
        self.gb_saved_state.toggled.connect(self.on_saved_state_change)
        self.gb_1d.toggled.connect(self.on_initial_waterlevel_change)
        self.gb_2d.toggled.connect(self.on_initial_waterlevel_change)
        self.gb_groundwater.toggled.connect(self.on_initial_waterlevel_change)

    def setup_2d_initial_concentrations(self):
        if hasattr(self, "initial_concentrations_widget"):
            self.initial_concentrations_widget.setParent(None)
        if not self.substances:
            self.initial_concentrations_2d_label.hide()
            return
        self.initial_concentrations_2d_label.show()
        initial_concentrations_widget = Initial2DConcentrationsWidget(self.substances, self.parent_page)
        self.initial_concentrations_widget = initial_concentrations_widget.widget
        self.rasters = initial_concentrations_widget.rasters
        parent_layout = self.layout()
        parent_layout.addWidget(self.initial_concentrations_widget, 5, 2)

    def setup_1d_initial_concentrations(self):
        if hasattr(self, "initial_concentrations_widget_1D"):
            self.initial_concentrations_widget_1D.setParent(None)
        if not self.substances:
            self.initial_concentrations_1d_label.hide()
            return
        self.initial_concentrations_1d_label.show()
        initial_concentrations_widget_1D = Initial1DConcentrationsWidget(self.substances, self.parent_page)
        self.local_data = initial_concentrations_widget_1D.local_data
        self.online_files = initial_concentrations_widget_1D.online_files
        self.initial_concentrations_widget_1D = initial_concentrations_widget_1D.widget
        self.layout().addWidget(self.initial_concentrations_widget_1D, 3, 2)

    def on_saved_state_change(self, checked):
        """Handle saved state group checkbox."""
        if checked:
            if self.gb_1d.isChecked():
                self.gb_1d.setChecked(False)
            if self.gb_2d.isChecked():
                self.gb_2d.setChecked(False)
            if self.gb_groundwater.isChecked():
                self.gb_groundwater.setChecked(False)

            # Disable concentrations, if required
            for substance in self.substances:
                substance_name = substance.get("name")
                groupbox_ic_1d = self.initial_concentrations_widget_1D.findChild(QGroupBox, f"gb_initial_concentrations_1d_{substance_name}")
                if groupbox_ic_1d.isChecked():
                    groupbox_ic_1d.setChecked(False)
                groupbox_ic_1d.setDisabled(True)
                groupbox_ic_2d = self.initial_concentrations_widget.findChild(QGroupBox, f"gb_initial_concentrations_2d_{substance_name}")
                if groupbox_ic_2d.isChecked():
                    groupbox_ic_2d.setChecked(False)
                groupbox_ic_2d.setDisabled(True)
        else:
            for substance in self.substances:
                substance_name = substance.get("name")
                groupbox_ic_1d = self.initial_concentrations_widget_1D.findChild(QGroupBox, f"gb_initial_concentrations_1d_{substance_name}")
                groupbox_ic_2d = self.initial_concentrations_widget.findChild(QGroupBox, f"gb_initial_concentrations_2d_{substance_name}")
                groupbox_ic_2d.setDisabled(False)
                groupbox_ic_1d.setDisabled(False)
                

    def on_initial_waterlevel_change(self, checked):
        """Handle initial waterlevel group checkbox."""
        if checked and self.gb_saved_state.isChecked():
            self.gb_saved_state.setChecked(False)

        if self.sender() is self.gb_1d:
            for substance in self.substances:
                substance_name = substance.get("name")
                groupbox_ic_1d = self.initial_concentrations_widget_1D.findChild(QGroupBox, f"gb_initial_concentrations_1d_{substance_name}")
                groupbox_ic_1d.setEnabled(checked)
                if not checked:
                    groupbox_ic_1d.setChecked(False)

        if self.sender() is self.gb_2d:
            for substance in self.substances:
                substance_name = substance.get("name")
                groupbox_ic_2d = self.initial_concentrations_widget.findChild(QGroupBox, f"gb_initial_concentrations_2d_{substance_name}")
                groupbox_ic_2d.setEnabled(checked)
                if not checked:
                    groupbox_ic_2d.setChecked(False)
            

    def setup_initial_conditions(self):
        """Setup initial conditions widget."""
        try:
            tc = ThreediCalls(self.parent_page.parent_wizard.plugin_dock.threedi_api)
            model_id = self.parent_page.parent_wizard.model_selection_dlg.current_model.id
            states = tc.fetch_3di_model_saved_states(model_id)
            if not states:
                self.gb_saved_state.setDisabled(True)
            else:
                for state in states:
                    state_name = state.name
                    self.saved_states[state_name] = state
                    self.cbo_saved_states.addItem(state_name)
            if self.initial_saved_state:
                initial_saved_state_idx = self.cbo_saved_states.findText(self.initial_saved_state.saved_state.name)
                if initial_saved_state_idx >= 0:
                    self.cbo_saved_states.setCurrentIndex(initial_saved_state_idx)
            initial_waterlevels = tc.fetch_3di_model_initial_waterlevels(model_id) or []
            initial_waterlevels_2d = [iw for iw in initial_waterlevels if iw.dimension == "two_d"]
            if initial_waterlevels_2d:
                self.rb_2d_online_raster.setChecked(True)
                self.rb_gw_online_raster.setChecked(True)
            for iw in sorted(initial_waterlevels_2d, key=attrgetter("id")):
                raster = tc.fetch_3di_model_raster(model_id, iw.source_raster_id)
                raster_filename = raster.file.filename
                self.initial_waterlevels[raster_filename] = iw
                self.cbo_2d_online_raster.addItem(raster_filename)
                self.cbo_gw_online_raster.addItem(raster_filename)
        except ApiException as e:
            error_msg = extract_error_message(e)
            self.parent_page.parent_wizard.plugin_dock.communication.bar_error(error_msg, log_text_color=QColor(Qt.red))
        except Exception as e:
            error_msg = f"Error: {e}"
            self.parent_page.parent_wizard.plugin_dock.communication.bar_error(error_msg, log_text_color=QColor(Qt.red))

    def load_1d_initial_waterlevel_csv(self):
        """Load 1D initial water level from the CSV file."""
        waterlevels, filename = self.open_upload_1d_initial_waterlevel_dialog()
        if not filename:
            return
        self.le_1d_upload_csv.setText(filename)
        self.initial_waterlevels_1d = waterlevels

    def handle_1D_initial_waterlevels_header(self, header: List[str]):
        """
        Handle 1D initial waterlevels potential header.
        Return None if fetch successful or error message if file is empty or have invalid structure.
        """
        error_message = None
        if not header:
            error_message = "CSV file is empty!"
            return error_message
        if "id" not in header:
            error_message = "Missing 'id' column in CSV file!"
        if "value" not in header:
            error_message = "Missing 'value' column in CSV file!"
        return error_message

    def open_upload_1d_initial_waterlevel_dialog(self):
        """Open dialog for selecting CSV file with 1D initial waterlevels."""
        last_folder = read_3di_settings("last_1d_initial_waterlevels", os.path.expanduser("~"))
        file_filter = "CSV (*.csv );;All Files (*)"
        filename, __ = QFileDialog.getOpenFileName(self, "1D Initial Waterlevels Time Series", last_folder, file_filter)
        if len(filename) == 0:
            return None, None
        save_3di_settings("last_1d_initial_waterlevels", os.path.dirname(filename))
        node_ids = []
        values = []
        with open(filename, encoding="utf-8-sig") as csvfile:
            reader = csv.DictReader(csvfile)
            header = reader.fieldnames
            waterlevels_list = list(reader)
        error_msg = self.handle_1D_initial_waterlevels_header(header)
        if error_msg is not None:
            self.parent_page.parent_wizard.plugin_dock.communication.show_warn(error_msg)
            return None, None
        for row in waterlevels_list:
            node_id_str = row.get("id").strip()
            value_str = row.get("value").strip()
            if not node_id_str or not value_str:
                error_msg = "Missing values in CSV file. Please remove these lines or fill in a value and try again."
                self.parent_page.parent_wizard.plugin_dock.communication.show_warn(error_msg)
                return None, None
            try:
                node_id = int(node_id_str)
                value = float(value_str)
                node_ids.append(node_id)
                values.append(value)
            except ValueError:
                error_msg = f"Invalid data format in CSV: id='{node_id_str}', value='{value_str}'"
                self.parent_page.parent_wizard.plugin_dock.communication.show_warn(error_msg)
                return None, None
        waterlevels = {
            "node_ids": node_ids,
            "values": values,
        }
        return waterlevels, filename

    @staticmethod
    def browse_for_local_raster(layers_widget):
        """Allow user to browse for a raster layer and insert it to the layers_widget."""
        name_filter = "GeoTIFF (*.tif *.TIF *.tiff *.TIFF)"
        title = "Select raster file"
        raster_file = get_filepath(None, extension_filter=name_filter, dialog_title=title)
        if not raster_file:
            return
        items = layers_widget.additionalItems()
        if raster_file not in items:
            items.append(raster_file)
        layers_widget.setAdditionalItems(items)


class LateralsWidget(uicls_laterals, basecls_laterals):
    """Widget for the Laterals page."""

    TYPE_1D = "1D"
    TYPE_2D = "2D"

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        self.current_model = parent_page.parent_wizard.model_selection_dlg.current_model
        self.substances = (
            parent_page.parent_wizard.substances_page.main_widget.substances
            if hasattr(parent_page.parent_wizard, "substances_page")
            else []
        )
        set_widget_background_color(self)
        self.laterals_1d = []
        self.laterals_2d = []
        self.laterals_1d_timeseries = {}
        self.laterals_2d_timeseries = {}
        self.laterals_1d_timeseries_template = {}
        self.laterals_2d_timeseries_template = {}
        self.substance_concentrations_1d = {}
        self.substance_concentrations_2d = {}
        self.last_upload_1d_filepath = ""
        self.last_upload_2d_filepath = ""
        self.setup_laterals()
        self.connect_signals()

    def setup_laterals(self):
        # 1D laterals
        if self.current_model.extent_one_d is not None:
            self.groupbox_1d_laterals.setEnabled(True)
            self.groupbox_1d_laterals.setChecked(True)
            if not self.cb_use_1d_laterals.isChecked():
                self.cb_upload_1d_laterals.setChecked(True)
            if not self.cb_upload_1d_laterals.isChecked():
                self.uploadgroup_1d.setEnabled(False)
        else:
            self.groupbox_1d_laterals.setEnabled(False)
            self.groupbox_1d_laterals.setChecked(False)

        # 2D laterals
        if self.current_model.extent_two_d is not None:
            self.groupbox_2d_laterals.setEnabled(True)
            self.groupbox_2d_laterals.setChecked(True)
            if not self.cb_use_2d_laterals.isChecked():
                self.cb_upload_2d_laterals.setChecked(True)
            if not self.cb_upload_2d_laterals.isChecked():
                self.uploadgroup_2d.setEnabled(False)
        else:
            self.groupbox_2d_laterals.setEnabled(False)
            self.groupbox_2d_laterals.setChecked(False)

    def connect_signals(self):
        """Connect signals."""
        # 1D laterals
        self.cb_upload_1d_laterals.toggled.connect(self.toggle_1d_laterals_upload)
        self.pb_upload_1d_laterals.clicked.connect(partial(self.load_csv, self.TYPE_1D))
        self.cb_1d_interpolate.stateChanged.connect(partial(self.interpolate_changed, self.TYPE_1D))

        # 2D laterals
        self.cb_upload_2d_laterals.toggled.connect(self.toggle_2d_laterals_upload)
        self.pb_upload_2d_laterals.clicked.connect(partial(self.load_csv, self.TYPE_2D))
        self.cb_2d_interpolate.stateChanged.connect(partial(self.interpolate_changed, self.TYPE_2D))

    def setup_substance_concentrations(self):
        if hasattr(self, "groupbox"):
            self.groupbox.setParent(None)
        if not self.substances:
            return
        substance_concentration_widget = SubstanceConcentrationsWidget(
            self.substances, self.current_model, self.handle_substance_timesteps
        )
        self.groupbox = substance_concentration_widget.groupbox
        self.substance_concentrations_1d = substance_concentration_widget.substance_concentrations_1d
        self.substance_concentrations_2d = substance_concentration_widget.substance_concentrations_2d
        parent_layout = self.layout()
        parent_layout.addWidget(self.groupbox, 3, 2)

    def handle_substance_timesteps(self, header, substance_list, laterals_type, units):
        """
        First, check if lateral values are uploaded.
        Second, check if substance concentrations timesteps match exactly the lateral values timesteps.
        Return None if they match or error message if not.
        """
        error_message = handle_csv_header(header)
        laterals_timeseries = (
            self.laterals_1d_timeseries if laterals_type == self.TYPE_1D else self.laterals_2d_timeseries
        )
        if not laterals_timeseries:
            error_message = "No laterals uploaded yet!"
        if not substance_list:
            error_message = "CSV file is empty!"
        if error_message is None:
            for substance in substance_list:
                lat_id = substance.get("id")
                timeseries = substance.get("timeseries")
                lateral = laterals_timeseries.get(lat_id)
                if lateral is None:
                    error_message = f"Laterals with ID {lat_id} not found!"
                    break
                lateral_values = lateral["values"]
                lateral_units = (
                    self.cbo_1d_units.currentText()
                    if laterals_type == self.TYPE_1D
                    else self.cbo_2d_units.currentText()
                )
                converted_lateral_values = convert_timeseries_to_seconds(lateral_values, lateral_units)
                laterals_timesteps = [t for (t, _) in converted_lateral_values]
                concentrations = parse_timeseries(timeseries)
                converted_concentrations = convert_timeseries_to_seconds(concentrations, units)
                concentrations_timesteps = [t for (t, _) in converted_concentrations]
                if laterals_timesteps != concentrations_timesteps:
                    error_message = "Substance concentrations timesteps do not match lateral values timesteps!"
                    break
        if error_message is not None:
            self.parent_page.parent_wizard.plugin_dock.communication.show_warn(error_message)
        return error_message

    def toggle_1d_laterals_upload(self, checked):
        """Handle 1D laterals toggle."""
        if checked:
            self.uploadgroup_1d.setEnabled(True)
        else:
            self.uploadgroup_1d.setEnabled(False)

    def toggle_2d_laterals_upload(self, checked):
        """Handle 2D laterals toggle."""
        if checked:
            self.uploadgroup_2d.setEnabled(True)
        else:
            self.uploadgroup_2d.setEnabled(False)

    def interpolate_changed(self, laterals_type):
        """Handle interpolate checkbox."""
        laterals_timeseries = (
            self.laterals_1d_timeseries if laterals_type == self.TYPE_1D else self.laterals_2d_timeseries
        )
        interpolate = (
            self.cb_1d_interpolate.isChecked() if laterals_type == self.TYPE_1D else self.cb_2d_interpolate.isChecked()
        )
        for val in laterals_timeseries.values():
            val["interpolate"] = interpolate

    def load_csv(self, laterals_type):
        """Load laterals from CSV file."""
        values, filename = self.open_upload_dialog(laterals_type)
        if not filename:
            return
        if laterals_type == self.TYPE_1D:
            self.il_1d_upload.setText(filename)
            self.last_upload_1d_filepath = filename
            self.laterals_1d_timeseries = values
        elif laterals_type == self.TYPE_2D:
            self.il_2d_upload.setText(filename)
            self.last_upload_2d_filepath = filename
            self.laterals_2d_timeseries = values
        else:
            raise NotImplementedError

    def recalculate_laterals_timeseries(self, laterals_type, timesteps_in_seconds=False):
        """Recalculate laterals timeseries (timesteps in seconds)."""
        laterals_timeseries = {}
        if laterals_type == self.TYPE_1D:
            if self.cb_use_1d_laterals:
                laterals_timeseries.update(self.laterals_1d_timeseries_template)
            if self.cb_upload_1d_laterals:
                laterals_timeseries.update(self.laterals_1d_timeseries)
        else:
            if self.cb_use_2d_laterals:
                laterals_timeseries.update(self.laterals_2d_timeseries_template)
            if self.cb_upload_2d_laterals:
                laterals_timeseries.update(self.laterals_2d_timeseries)
        if timesteps_in_seconds is False:
            return laterals_timeseries
        laterals_data = deepcopy(laterals_timeseries)
        units = self.cbo_1d_units.currentText() if laterals_type == self.TYPE_1D else self.cbo_2d_units.currentText()
        for val in laterals_data.values():
            val["values"] = convert_timeseries_to_seconds(val["values"], units)
        return laterals_data

    def recalculate_substances_timeseries(self, laterals_type, timesteps_in_seconds=False):
        """Recalculate substances timeseries (timesteps in seconds)."""
        substance_concentrations = {}
        if laterals_type == self.TYPE_1D:
            substance_concentrations.update(self.substance_concentrations_1d)
        else:
            substance_concentrations.update(self.substance_concentrations_2d)
        substances = deepcopy(substance_concentrations)
        substances_data = {}
        if laterals_type == self.TYPE_1D:
            laterals_timeseries = self.laterals_1d_timeseries
        else:
            laterals_timeseries = self.laterals_2d_timeseries
        for lat_id in laterals_timeseries.keys():
            if lat_id in substances:
                substances_data[lat_id] = substances[lat_id]
        if timesteps_in_seconds is False:
            return substances_data
        for lateral_substances in substances_data.values():
            for substance in lateral_substances:
                units = substance["units"]
                substance["concentrations"] = convert_timeseries_to_seconds(substance["concentrations"], units)
        return substances_data

    def update_laterals_with_substances(self, file_laterals, substances):
        """Update laterals with substances."""
        for lat_id, lat_data in file_laterals.items():
            lateral_substances = substances.get(lat_id)
            if lateral_substances is None:
                continue
            lat_data["substances"] = lateral_substances

    def get_laterals_data(self, timesteps_in_seconds=False):
        """Get laterals data."""
        constant_laterals = []
        file_laterals_1d = {}
        file_laterals_2d = {}
        if self.groupbox_1d_laterals.isChecked():
            if self.cb_use_1d_laterals:
                constant_laterals.extend(self.laterals_1d)
            file_laterals_1d.update(self.recalculate_laterals_timeseries(self.TYPE_1D, timesteps_in_seconds))
            if self.substance_concentrations_1d:
                substances = self.recalculate_substances_timeseries(self.TYPE_1D, timesteps_in_seconds)
                self.update_laterals_with_substances(file_laterals_1d, substances)
        if self.groupbox_2d_laterals.isChecked():
            if self.cb_use_2d_laterals:
                constant_laterals.extend(self.laterals_2d)
            file_laterals_2d.update(self.recalculate_laterals_timeseries(self.TYPE_2D, timesteps_in_seconds))
            if self.substance_concentrations_2d:
                substances = self.recalculate_substances_timeseries(self.TYPE_2D, timesteps_in_seconds)
                self.update_laterals_with_substances(file_laterals_2d, substances)
        return constant_laterals, file_laterals_1d, file_laterals_2d

    def handle_laterals_header(self, header: List[str], laterals_type: str, log_error=True):
        """
        Handle laterals potential header.
        Return None if fetch successful or error message if file is empty or have invalid structure.
        """
        error_message = None
        if not header:
            error_message = "CSV file is empty!"
            if log_error:
                self.parent_page.parent_wizard.plugin_dock.communication.show_warn(error_message)
            return error_message
        if laterals_type == "1D":
            if any(k not in header for k in ["id", "connection_node_id", "timeseries"]):
                error_message = "Wrong timeseries format for 1D laterals!"
        else:
            if (
                any(k not in header for k in ["id", "timeseries"])
                or not any(k in header for k in ["x", "X"])
                or not any(k in header for k in ["y", "Y"])
            ):
                error_message = "Wrong timeseries format for 2D laterals!"
        if log_error and error_message:
            self.parent_page.parent_wizard.plugin_dock.communication.show_warn(error_message)
        return error_message

    def open_upload_dialog(self, laterals_type):
        """Open dialog for selecting CSV file with laterals."""
        last_folder = read_3di_settings("last_laterals_folder", os.path.expanduser("~"))
        file_filter = "CSV (*.csv );;All Files (*)"
        filename, __ = QFileDialog.getOpenFileName(self, "Laterals Time Series", last_folder, file_filter)
        if len(filename) == 0:
            return None, None
        save_3di_settings("last_laterals_folder", os.path.dirname(filename))
        values = {}
        with open(filename, encoding="utf-8-sig") as csvfile:
            reader = csv.DictReader(csvfile)
            header = reader.fieldnames
            laterals_list = list(reader)
        error_msg = self.handle_laterals_header(header, laterals_type)
        if error_msg is not None:
            return None, None
        if laterals_type == "1D":
            interpolate = self.cb_1d_interpolate.isChecked()
            for row in laterals_list:
                lat_id = row.get("id")
                connection_node_id = row.get("connection_node_id")
                timeseries = row.get("timeseries")
                try:
                    vals = parse_timeseries(timeseries)
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
                    self.last_uploaded_1d_laterals = lateral
                except ValueError:
                    continue
        else:
            interpolate = self.cb_2d_interpolate.isChecked()
            for row in laterals_list:
                x = row.get("x") or row.get("X")
                y = row.get("y") or row.get("Y")
                lat_id = row.get("id")
                timeseries = row.get("timeseries")
                try:
                    vals = parse_timeseries(timeseries)
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
                    self.last_uploaded_2d_laterals = lateral
                except ValueError:
                    continue
        return values, filename


class DWFWidget(uicls_dwf, basecls_dwf):
    """Widget for the Dry Weather Flow page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        set_widget_background_color(self)
        self.dwf_timeseries = {}
        self.last_uploaded_dwf = None
        self.last_upload_filepath = ""
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
        self.last_upload_filepath = filename
        self.dwf_timeseries = values

    def handle_dwf_laterals_header(self, header: List[str], log_error=True):
        """
        Handle DWF laterals header.
        Return None if fetch successful or error message if file is empty or have invalid structure.
        """
        error_message = None
        if not header:
            error_message = "CSV file is empty!"
            if log_error:
                self.parent_page.parent_wizard.plugin_dock.communication.show_warn(error_message)
            return error_message
        if len(header) != 3:
            error_message = "Wrong timeseries format for Dry Weather Flow!"
            if log_error:
                self.parent_page.parent_wizard.plugin_dock.communication.show_warn(error_message)
        return error_message

    def open_upload_dialog(self):
        """Open dialog for selecting CSV file with Dry Weather Flow."""
        last_folder = read_3di_settings("last_dwf_folder", os.path.expanduser("~"))
        file_filter = "CSV (*.csv );;All Files (*)"
        filename, __ = QFileDialog.getOpenFileName(self, "Dry Weather Flow Time Series", last_folder, file_filter)
        if len(filename) == 0:
            return None, None
        save_3di_settings("last_dwf_folder", os.path.dirname(filename))
        values = {}
        interpolate = self.cb_interpolate_dwf.isChecked()
        with open(filename, encoding="utf-8-sig") as csvfile:
            reader = csv.DictReader(csvfile)
            header = reader.fieldnames
            dwf_laterals_list = list(reader)
        error_msg = self.handle_dwf_laterals_header(header)
        if error_msg is not None:
            return None, None
        for row in dwf_laterals_list:
            dwf_id = row.get("id")
            connection_node_id = row.get("connection_node_id")
            timeseries = row.get("timeseries")
            try:
                vals = parse_timeseries(timeseries)
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
        self.map_canvas = self.parent_page.parent_wizard.plugin_dock.iface.mapCanvas()
        set_widget_background_color(self)
        self.added_breaches = defaultdict(dict)
        self.breaches_model = QStandardItemModel()
        self.breaches_tv.setModel(self.breaches_model)
        self.potential_breaches_layer = parent_page.parent_wizard.model_selection_dlg.potential_breaches_layer
        self.flowlines_layer = parent_page.parent_wizard.model_selection_dlg.flowlines_layer
        self.dd_breach_id = FilteredComboBox(self)
        self.breach_lout.addWidget(self.dd_breach_id)
        self.dd_simulation.currentIndexChanged.connect(self.simulation_changed)
        self.potential_breach_selection_tool = None
        self.flowline_selection_tool = None
        self.pb_add_breach_from_list.clicked.connect(self.select_potential_breach_from_list)
        self.pb_select_potential_breach.clicked.connect(self.select_potential_breach)
        self.pb_select_flowline.clicked.connect(self.select_flowline)
        self.pb_remove_breach.clicked.connect(self.remove_breach)
        if initial_conditions.multiple_simulations and initial_conditions.simulations_difference == "breaches":
            self.simulation_widget.show()
        else:
            self.simulation_widget.hide()
        self.dd_simulation.addItems(initial_conditions.simulations_list)
        self.setup_breaches()

    @property
    def current_simulation_number(self):
        return self.dd_simulation.currentIndex()

    @property
    def breach_parameters(self):
        """Breach parameters with human-friendly labels."""
        parameters = {
            "breach_id": "ID",
            "code": "Code",
            "display_name": "Display name",
            "offset": "Start after",
            "offset_units": "[units]",
            "initial_width": "Initial width",
            "duration": "Duration till max depth",
            "duration_units": "[units]",
            "levee_material": "Levee material",
            "max_breach_depth": "Max breach depth [m]",
            "discharge_coefficient_positive": "Discharge coefficient positive",
            "discharge_coefficient_negative": "Discharge coefficient negative",
        }
        return parameters

    def setup_breaches(self):
        """Setup breaches data with corresponding vector layer."""
        if self.potential_breaches_layer is not None:
            breach_ids_map = {
                f'{f["content_pk"]} | {f["code"]} | {f["display_name"]}': f.id()
                for f in self.potential_breaches_layer.getFeatures()
            }
            for breach_id, breach_fid in sorted(breach_ids_map.items(), key=lambda i: i[1]):
                self.dd_breach_id.addItem(breach_id, breach_fid)
        self.breaches_model.setHorizontalHeaderLabels(self.breach_parameters.values())

    def select_potential_breach_from_list(self):
        """Add potential breach from the dropdown menu to the selected breaches list."""
        if self.potential_breaches_layer is None:
            self.parent_page.parent_wizard.plugin_dock.communication.show_warn(
                "Potential breaches are not available!", self
            )
            return
        breach_fid = self.dd_breach_id.currentData()
        potential_breach_feat = self.potential_breaches_layer.getFeature(breach_fid)
        self.on_potential_breach_feature_identified(potential_breach_feat)

    def select_potential_breach(self):
        """Add potential breach from the map canvas to the selected breaches list."""
        if self.potential_breaches_layer is None:
            self.parent_page.parent_wizard.plugin_dock.communication.show_warn(
                "Potential breaches are not available!", self
            )
            return
        self.potential_breach_selection_tool = QgsMapToolIdentifyFeature(self.map_canvas, self.potential_breaches_layer)
        self.potential_breach_selection_tool.activated.connect(self.parent_page.parent_wizard.hide)
        self.potential_breach_selection_tool.deactivated.connect(self.parent_page.parent_wizard.show)
        self.potential_breach_selection_tool.featureIdentified.connect(self.on_potential_breach_feature_identified)
        self.map_canvas.setMapTool(self.potential_breach_selection_tool)

    def select_flowline(self):
        """Add flowline from the map canvas to the selected breaches list."""
        if self.flowlines_layer is None:
            self.parent_page.parent_wizard.plugin_dock.communication.show_warn(
                "1D2D flowlines are not available!", self
            )
            return
        self.flowline_selection_tool = QgsMapToolIdentifyFeature(self.map_canvas, self.flowlines_layer)
        self.flowline_selection_tool.activated.connect(self.parent_page.parent_wizard.hide)
        self.flowline_selection_tool.deactivated.connect(self.parent_page.parent_wizard.show)
        self.flowline_selection_tool.featureIdentified.connect(self.on_flowline_feature_identified)
        self.map_canvas.setMapTool(self.flowline_selection_tool)

    def on_potential_breach_feature_identified(self, potential_breach_feat):
        """Action on featureIdentified signal for potential breaches layer."""
        self.map_canvas.unsetMapTool(self.potential_breach_selection_tool)
        potential_breach_fid = potential_breach_feat.id()
        self.potential_breaches_layer.selectByIds([potential_breach_fid])
        breach_key = (BreachSourceType.POTENTIAL_BREACHES, potential_breach_fid)
        if breach_key in self.added_breaches[self.current_simulation_number]:
            self.parent_page.parent_wizard.plugin_dock.communication.show_warn(
                "Potential breach already selected!", self
            )
            return
        self.add_breach(BreachSourceType.POTENTIAL_BREACHES, potential_breach_feat)
        self.potential_breaches_layer.removeSelection()

    def on_flowline_feature_identified(self, flowline_feat):
        """Action on featureIdentified signal for flowlines layer."""
        self.map_canvas.unsetMapTool(self.flowline_selection_tool)
        flowline_fid = flowline_feat.id()
        self.flowlines_layer.selectByIds([flowline_fid])
        breach_key = (BreachSourceType.FLOWLINES, flowline_fid)
        if breach_key in self.added_breaches[self.current_simulation_number]:
            self.parent_page.parent_wizard.plugin_dock.communication.show_warn("1D2D flowline already selected!", self)
            return
        self.add_breach(BreachSourceType.FLOWLINES, flowline_feat)

    def breach_widgets_for_feature(self, breach_source_type, breach_feature):
        """Setup breach widgets out of the feature."""
        segoe_ui_font = QFont("Segoe UI", 8)
        maxsize = 2147483647
        breach_fid = breach_feature.id()
        breach_key = (breach_source_type, breach_fid)

        id_line_edit = QLineEdit()
        id_line_edit.setFont(segoe_ui_font)
        id_line_edit.setStyleSheet("QLineEdit {background-color: white;}")
        id_line_edit.setReadOnly(True)
        id_line_edit.breach_key = breach_key
        id_line_edit.simulation_number = self.current_simulation_number

        code_line_edit = QLineEdit()
        code_line_edit.setFont(segoe_ui_font)
        code_line_edit.setStyleSheet("QLineEdit {background-color: white;}")
        code_line_edit.setReadOnly(True)

        display_name_line_edit = QLineEdit()
        display_name_line_edit.setFont(segoe_ui_font)
        display_name_line_edit.setStyleSheet("QLineEdit {background-color: white;}")
        display_name_line_edit.setReadOnly(True)

        offset_spinbox = QSpinBox()
        offset_spinbox.setFont(segoe_ui_font)
        offset_spinbox.setStyleSheet("QSpinBox {background-color: white;}")
        offset_spinbox.setMinimum(0)
        offset_spinbox.setMaximum(maxsize)

        offset_units_combo = QComboBox()
        offset_units_combo.setFont(segoe_ui_font)
        offset_units_combo.addItems(self.SECONDS_MULTIPLIERS.keys())

        initial_width_spinbox = QDoubleSpinBox()
        initial_width_spinbox.setFont(segoe_ui_font)
        initial_width_spinbox.setStyleSheet("QDoubleSpinBox {background-color: white;}")
        initial_width_spinbox.setDecimals(1)
        initial_width_spinbox.setMinimum(0.0)
        initial_width_spinbox.setMaximum(maxsize)

        duration_spinbox = QSpinBox()
        duration_spinbox.setFont(segoe_ui_font)
        duration_spinbox.setStyleSheet("QSpinBox {background-color: white;}")
        duration_spinbox.setMinimum(0)
        duration_spinbox.setMaximum(maxsize)

        duration_units_combo = QComboBox()
        duration_units_combo.setFont(segoe_ui_font)
        duration_units_combo.addItems(self.SECONDS_MULTIPLIERS.keys())

        levee_material_combo = QComboBox()
        levee_material_combo.setFont(segoe_ui_font)
        levee_material_combo.addItems(["sand", "clay"])

        max_breach_depth_spinbox = QDoubleSpinBox()
        max_breach_depth_spinbox.setFont(segoe_ui_font)
        max_breach_depth_spinbox.setStyleSheet("QDoubleSpinBox {background-color: white;}")
        max_breach_depth_spinbox.setDecimals(3)
        max_breach_depth_spinbox.setMinimum(0.0)
        max_breach_depth_spinbox.setMaximum(maxsize)

        discharge_coefficient_positive_spinbox = QDoubleSpinBox()
        discharge_coefficient_positive_spinbox.setFont(segoe_ui_font)
        discharge_coefficient_positive_spinbox.setStyleSheet("QDoubleSpinBox {background-color: white;}")
        discharge_coefficient_positive_spinbox.setDecimals(3)
        discharge_coefficient_positive_spinbox.setMinimum(0.0)
        discharge_coefficient_positive_spinbox.setMaximum(maxsize)

        discharge_coefficient_negative_spinbox = QDoubleSpinBox()
        discharge_coefficient_negative_spinbox.setFont(segoe_ui_font)
        discharge_coefficient_negative_spinbox.setStyleSheet("QDoubleSpinBox {background-color: white;}")
        discharge_coefficient_negative_spinbox.setDecimals(3)
        discharge_coefficient_negative_spinbox.setMinimum(0.0)
        discharge_coefficient_negative_spinbox.setMaximum(maxsize)

        offset_spinbox.setValue(0)
        initial_width_spinbox.setValue(10.0)
        duration_spinbox.setValue(10)
        duration_units_combo.setCurrentText("mins")
        discharge_coefficient_positive_spinbox.setValue(1.0)
        discharge_coefficient_negative_spinbox.setValue(1.0)

        if breach_source_type == BreachSourceType.POTENTIAL_BREACHES:
            id_line_edit.setText(str(breach_feature["content_pk"]))
            code_line_edit.setText(breach_feature["code"])
            display_name_line_edit.setText(breach_feature["display_name"])
            levee_material_combo.setCurrentIndex(breach_feature["levmat"] - 1)
            max_breach_depth_spinbox.setValue(breach_feature["levbr"])
        else:
            id_line_edit.setText(str(breach_feature["id"]))
            max_breach_depth_spinbox.setValue(2.0)

        breach_widgets_list = [
            id_line_edit,
            code_line_edit,
            display_name_line_edit,
            offset_spinbox,
            offset_units_combo,
            initial_width_spinbox,
            duration_spinbox,
            duration_units_combo,
            levee_material_combo,
            max_breach_depth_spinbox,
            discharge_coefficient_positive_spinbox,
            discharge_coefficient_negative_spinbox,
        ]

        breach_widgets = dict(zip(self.breach_parameters.keys(), breach_widgets_list))
        return breach_widgets

    def add_breach(self, breach_source_type, breach_feature):
        """Add breach widgets to the breaches list."""
        breach_fid = breach_feature.id()
        breach_widgets = self.breach_widgets_for_feature(breach_source_type, breach_feature)
        breach_rows_count = self.breaches_model.rowCount()
        row_number = breach_rows_count
        row_items = [QStandardItem("") for _ in breach_widgets]
        self.breaches_model.appendRow(row_items)
        for column_idx, breach_widget in enumerate(breach_widgets.values()):
            self.breaches_tv.setIndexWidget(self.breaches_model.index(row_number, column_idx), breach_widget)
        for i in range(len(breach_widgets)):
            self.breaches_tv.resizeColumnToContents(i)
        breach_key = (breach_source_type, breach_fid)
        self.added_breaches[self.current_simulation_number][breach_key] = breach_widgets

    def remove_breach(self):
        """Remove breach widgets from the breaches list."""
        index = self.breaches_tv.currentIndex()
        if not index.isValid():
            self.parent_page.parent_wizard.plugin_dock.communication.show_warn(
                "No breach row selected - nothing to remove!", self
            )
            return
        row = index.row()
        breach_id_item = self.breaches_model.item(row, 0)
        breach_id_index = breach_id_item.index()
        breach_id_widget = self.breaches_tv.indexWidget(breach_id_index)
        breach_key = breach_id_widget.breach_key
        self.breaches_model.removeRow(row)
        del self.added_breaches[self.current_simulation_number][breach_key]

    def simulation_changed(self):
        """Handle simulation change."""
        row_count = self.breaches_model.rowCount()
        root_model_index = self.breaches_model.invisibleRootItem().index()
        for row in range(row_count):
            breach_id_item = self.breaches_model.item(row, 0)
            breach_id_index = breach_id_item.index()
            breach_id_widget = self.breaches_tv.indexWidget(breach_id_index)
            hide_row = breach_id_widget.simulation_number != self.current_simulation_number
            self.breaches_tv.setRowHidden(row, root_model_index, hide_row)

    def get_breaches_data(self):
        """Getting all needed data for adding breaches to the simulation."""
        potential_breaches, flowlines = [], []
        simulation_breaches = self.added_breaches[self.current_simulation_number]
        for (breach_source_type, breach_fid), breach_widgets in simulation_breaches.items():
            duration_units = breach_widgets["duration_units"].currentText()
            offset_units = breach_widgets["offset_units"].currentText()
            breach_obj = dm.Breach(
                breach_id=int(breach_widgets["breach_id"].text()),
                width=breach_widgets["initial_width"].value(),
                duration_till_max_depth=breach_widgets["duration"].value() * self.SECONDS_MULTIPLIERS[duration_units],
                offset=breach_widgets["offset"].value() * self.SECONDS_MULTIPLIERS[offset_units],
                discharge_coefficient_positive=breach_widgets["discharge_coefficient_positive"].value(),
                discharge_coefficient_negative=breach_widgets["discharge_coefficient_negative"].value(),
                levee_material=breach_widgets["levee_material"].currentText(),
                max_breach_depth=breach_widgets["max_breach_depth"].value(),
            )
            if breach_source_type == BreachSourceType.POTENTIAL_BREACHES:
                potential_breaches.append(breach_obj)
            else:
                flowlines.append(breach_obj)
        breach_data = (potential_breaches, flowlines)
        return breach_data


class PrecipitationWidget(uicls_precipitation_page, basecls_precipitation_page):
    """Widget for the Precipitation page."""

    SECONDS_MULTIPLIERS = {"s": 1, "mins": 60, "hrs": 3600}
    DESIGN_5_MINUTES_TIMESTEP = 300
    DESIGN_HOUR_TIMESTEP = 3600
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

    def __init__(self, parent_page, initial_conditions=None):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        set_widget_background_color(self)
        self.current_units = "hrs"
        self.precipitation_duration = 0
        self.total_precipitation = 0
        self.custom_time_series = defaultdict(list)
        self.design_time_series = defaultdict(list)
        self.cbo_design.addItems([str(i) for i in range(len(self.RAIN_LOOKUP))])
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(None)
        self.plot_widget.setFixedHeight(80)
        self.plot_bar_graph = None
        self.plot_ticks = None
        self.lout_plot.addWidget(self.plot_widget, 0, 0)
        self.widget_constant.hide()
        self.widget_from_csv.hide()
        self.widget_from_netcdf.hide()
        self.widget_design.hide()
        self.widget_radar.hide()
        self.connect_signals()
        # Primarily used for switching simulations
        self.values = dict()
        if initial_conditions.multiple_simulations and initial_conditions.simulations_difference == "precipitation":
            self.simulation_widget.show()
        else:
            self.simulation_widget.hide()
        self.dd_simulation.addItems(initial_conditions.simulations_list)
        self.plot_precipitation()

        self.substance_widgets = {}  # map from substance dict to widget
        self.substances = (
            parent_page.parent_wizard.substances_page.main_widget.substances
            if hasattr(parent_page.parent_wizard, "substances_page")
            else []
        )
        self.update_substance_widgets()

    def connect_signals(self):
        """Connecting widgets signals."""
        self.cbo_prec_type.currentIndexChanged.connect(self.precipitation_changed)
        self.sp_intensity.valueChanged.connect(self.plot_precipitation)
        self.start_after_constant_u.currentIndexChanged.connect(self.sync_units)
        self.stop_after_constant_u.currentIndexChanged.connect(self.sync_units)
        self.sp_start_after_constant.valueChanged.connect(self.plot_precipitation)
        self.sp_stop_after_constant.valueChanged.connect(self.plot_precipitation)
        self.pb_upload_csv.clicked.connect(self.set_csv_time_series)
        self.pb_upload_netcdf.clicked.connect(self.set_netcdf_time_series)
        self.start_after_csv_u.currentIndexChanged.connect(self.sync_units)
        self.sp_start_after_csv.valueChanged.connect(self.plot_precipitation)
        self.cbo_design.currentIndexChanged.connect(self.set_design_time_series)
        self.start_after_design_u.currentIndexChanged.connect(self.sync_units)
        self.sp_start_after_design.valueChanged.connect(self.plot_precipitation)
        self.start_after_radar_u.currentIndexChanged.connect(self.sync_units)
        self.stop_after_radar_u.currentIndexChanged.connect(self.sync_units)
        self.sp_start_after_radar.valueChanged.connect(self.plot_precipitation)
        self.sp_stop_after_radar.valueChanged.connect(self.plot_precipitation)
        self.dd_simulation.currentIndexChanged.connect(self.simulation_changed)
        self.cb_interpolate_rain.stateChanged.connect(self.plot_precipitation)

    def change_time_series_source(self, is_checked):
        """Handling rain time series source change."""
        if is_checked is True:
            self.le_upload_csv.clear()
            self.plot_precipitation()

    def store_cache(self):
        """Store current widget values for a specific simulation."""
        simulation = self.dd_simulation.currentText()
        precipitation_type = self.cbo_prec_type.currentText()
        
        # iterate over the substance values and retrieve the values
        substance_concentrations = []
        if not ((precipitation_type == EventTypes.FROM_NETCDF.value) or (precipitation_type == EventTypes.RADAR.value)):
            for substance in self.substances:
                substance_name = substance["name"]
                assert substance_name in self.substance_widgets
                value = self.substance_widgets[substance_name].get_value()
                substance_concentrations.append({"name": substance_name, "unit": substance.get("unit", ""), "concentration": value})

        if precipitation_type == EventTypes.CONSTANT.value:
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
                "substance_concentration": substance_concentrations,
            }
        elif precipitation_type == EventTypes.FROM_CSV.value:
            start_after = self.sp_start_after_csv.value()
            start_after_units = self.start_after_csv_u.currentText()
            units = self.cbo_units_csv.currentText()
            time_series = self.custom_time_series[simulation]
            csv_path = self.le_upload_csv.text()
            interpolate = self.cb_interpolate_rain.isChecked()
            self.values[simulation] = {
                "precipitation_type": precipitation_type,
                "start_after": start_after,
                "start_after_units": start_after_units,
                "units": units,
                "time_series": time_series,
                "csv_path": csv_path,
                "interpolate": interpolate,
                "substance_concentration": substance_concentrations,
            }
        elif precipitation_type == EventTypes.FROM_NETCDF.value:
            # note that we do not add substance for netcdf rain
            netcdf_path = self.le_upload_netcdf.text()
            netcdf_global = self.rb_global_netcdf.isChecked()
            netcdf_raster = self.rb_raster_netcdf.isChecked()
            self.values[simulation] = {
                "precipitation_type": precipitation_type,
                "netcdf_path": netcdf_path,
                "netcdf_global": netcdf_global,
                "netcdf_raster": netcdf_raster,
            }
        elif precipitation_type == EventTypes.DESIGN.value:
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
                "substance_concentration": substance_concentrations,
            }
        elif precipitation_type == EventTypes.RADAR.value:
            # note that we do not add substance for radar rain
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
            self.le_upload_csv.clear()
            self.cbo_design.setCurrentIndex(0)
            self.plot_precipitation()
            return

        # It could be that substances have been removed from the Substances page, or in a different order
        # and this has not been set in the cached simulation values
        for substance_widget in self.substance_widgets.values():
            self.substance_widget.layout().removeWidget(substance_widget)
            del substance_widget
        self.substance_widgets.clear()
        
        substance_concentrations = vals["substance_concentration"]
        new_substance_concentrations = []
        
        for substance in self.substances:
            substance_name = substance["name"]
            substance_concentration = next((x for x in substance_concentrations if x["name"] == substance["name"]), None)
            if not substance_concentration:  # substance has been added
                substance_concentration = {"name": substance_name, "concentration": None}
            substance_concentration["unit"] = substance.get("unit", "")
            wid = PrecipitationWidget.PrecipationSubstanceWidget(substance_name, substance_concentration["concentration"] or "", substance.get("units", ""), self.substance_widget)
            wid.value_changed.connect(self.store_cache)
            self.substance_widgets[substance_name] = wid  # name is enforced to be unique in UI
            self.substance_widget.layout().addWidget(wid)
            new_substance_concentrations.append(substance_concentration)

        # Update the cached values
        self.values[simulation]["substance_concentration"] = new_substance_concentrations

        precipitation_type = vals.get("precipitation_type")
        if precipitation_type == EventTypes.CONSTANT.value:
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
        elif precipitation_type == EventTypes.FROM_CSV.value:
            # Get simulation values
            self.cbo_prec_type.setCurrentIndex(self.cbo_prec_type.findText(vals.get("precipitation_type")))
            self.sp_start_after_csv.setValue(vals.get("start_after"))
            self.start_after_csv_u.setCurrentIndex(self.start_after_csv_u.findText(vals.get("start_after_units")))
            self.cbo_units_csv.setCurrentIndex(self.cbo_units_csv.findText(vals.get("units")))
            self.le_upload_csv.setText(vals.get("csv_path", ""))
            self.custom_time_series[simulation] = vals.get("time_series", [])
            self.cb_interpolate_rain.setChecked(vals.get("interpolate", False))
        elif precipitation_type == EventTypes.FROM_NETCDF.value:
            self.rb_global_netcdf.setChecked(vals.get("global_netcdf", True))
            self.rb_raster_netcdf.setChecked(vals.get("raster_netcdf", False))
            self.le_upload_netcdf.setText(vals.get("netcdf_path", ""))
        elif precipitation_type == EventTypes.DESIGN.value:
            self.cbo_prec_type.setCurrentIndex(self.cbo_prec_type.findText(vals.get("precipitation_type")))
            self.sp_start_after_design.setValue(vals.get("start_after"))
            self.start_after_design_u.setCurrentIndex(self.start_after_design_u.findText(vals.get("start_after_units")))
            design_number = vals.get("design_number")
            self.cbo_design.setCurrentIndex(self.cbo_design.findText(design_number))
            self.design_time_series[simulation] = vals.get("time_series", [])
        elif precipitation_type == EventTypes.RADAR.value:
            self.cbo_prec_type.setCurrentIndex(self.cbo_prec_type.findText(vals.get("precipitation_type")))
            self.sp_start_after_radar.setValue(vals.get("start_after"))
            self.start_after_radar_u.setCurrentIndex(self.start_after_radar_u.findText(vals.get("start_after_units")))
            self.sp_stop_after_radar.setValue(vals.get("stop_after"))
            self.stop_after_radar_u.setCurrentIndex(self.stop_after_radar_u.findText(vals.get("stop_after_units")))
        self.plot_precipitation()

    def precipitation_changed(self):
        """Changing widgets looks based on currently selected precipitation type."""
        precipitation_type_str = self.cbo_prec_type.currentText()
        try:
            precipitation_type = EventTypes(precipitation_type_str)
        except ValueError:
            precipitation_type = None
        if precipitation_type == EventTypes.CONSTANT:
            self.widget_constant.show()
            self.widget_from_csv.hide()
            self.widget_from_netcdf.hide()
            self.widget_design.hide()
            self.widget_radar.hide()
        elif precipitation_type == EventTypes.FROM_CSV:
            self.widget_constant.hide()
            self.widget_from_csv.show()
            self.widget_from_netcdf.hide()
            self.widget_design.hide()
            self.widget_radar.hide()
        elif precipitation_type == EventTypes.FROM_NETCDF:
            self.widget_constant.hide()
            self.widget_from_csv.hide()
            self.widget_from_netcdf.show()
            self.widget_design.hide()
            self.widget_radar.hide()
        elif precipitation_type == EventTypes.DESIGN:
            self.widget_constant.hide()
            self.widget_from_csv.hide()
            self.widget_from_netcdf.hide()
            self.widget_design.show()
            self.widget_radar.hide()
        elif precipitation_type == EventTypes.RADAR:
            self.widget_constant.hide()
            self.widget_from_csv.hide()
            self.widget_from_netcdf.hide()
            self.widget_design.hide()
            self.widget_radar.show()
        else:
            self.widget_constant.hide()
            self.widget_from_csv.hide()
            self.widget_from_netcdf.hide()
            self.widget_design.hide()
            self.widget_radar.hide()
        self.refresh_current_units()
        self.update_substance_widgets()
        self.plot_precipitation()
        

    def sync_units(self, idx):
        """Syncing units widgets."""
        current_text = self.cbo_prec_type.currentText()
        if current_text == EventTypes.CONSTANT.value:
            if self.start_after_constant_u.currentIndex != idx:
                self.start_after_constant_u.setCurrentIndex(idx)
            if self.stop_after_constant_u.currentIndex != idx:
                self.stop_after_constant_u.setCurrentIndex(idx)
            self.current_units = self.start_after_constant_u.currentText()
        elif current_text == EventTypes.FROM_CSV.value:
            self.current_units = self.start_after_csv_u.currentText()
        elif current_text == EventTypes.DESIGN.value:
            self.current_units = self.start_after_design_u.currentText()
        elif current_text == EventTypes.RADAR.value:
            if self.start_after_radar_u.currentIndex != idx:
                self.start_after_radar_u.setCurrentIndex(idx)
            if self.stop_after_radar_u.currentIndex != idx:
                self.stop_after_radar_u.setCurrentIndex(idx)
            self.current_units = self.start_after_radar_u.currentText()
        self.plot_precipitation()

    def refresh_current_units(self):
        """Refreshing current units value."""
        current_text = self.cbo_prec_type.currentText()
        if current_text == EventTypes.CONSTANT.value:
            self.current_units = self.start_after_constant_u.currentText()
        elif current_text == EventTypes.FROM_CSV.value:
            self.current_units = self.start_after_csv_u.currentText()
        elif current_text == EventTypes.DESIGN.value:
            self.current_units = self.start_after_design_u.currentText()
        elif current_text == EventTypes.RADAR.value:
            self.current_units = self.start_after_radar_u.currentText()
        else:
            pass

    def refresh_duration(self):
        """Refreshing precipitation duration in seconds."""
        self.precipitation_duration = self.get_precipitation_duration()

    def duration_in_units(self):
        """Calculating duration in currently selected units."""
        unit_divider = self.SECONDS_MULTIPLIERS[self.current_units]
        duration_in_units = int(self.precipitation_duration / unit_divider)
        return duration_in_units

    def set_csv_time_series(self):
        """Selecting and setting up rain time series from CSV format."""
        file_filter = "CSV (*.csv);;All Files (*)"
        last_folder = read_3di_settings("last_precipitation_folder", os.path.expanduser("~"))
        filename, __ = QFileDialog.getOpenFileName(self, "Precipitation Time Series", last_folder, file_filter)
        if len(filename) == 0:
            return
        save_3di_settings("last_precipitation_folder", os.path.dirname(filename))
        time_series = []
        simulation = self.dd_simulation.currentText()
        with open(filename, encoding="utf-8-sig") as rain_file:
            rain_reader = csv.reader(rain_file)
            units_multiplier = self.SECONDS_MULTIPLIERS["mins"]
            for rtime, rain in rain_reader:
                # We are assuming that timestep is in minutes, so we are converting it to seconds on the fly.
                try:
                    time_series.append([float(rtime) * units_multiplier, float(rain)])
                except ValueError:
                    continue
        if not intervals_are_even(time_series):
            warn_message = (
                "Time steps in the selected CSV file are not even. "
                "Please adjust your data to fulfill even time steps requirement."
            )
            self.parent_page.parent_wizard.plugin_dock.communication.show_warn(warn_message)
            return
        self.le_upload_csv.setText(filename)
        self.custom_time_series[simulation] = time_series
        self.plot_precipitation()

    def set_netcdf_time_series(self):
        """Selecting and setting up rain time series from NetCDF format."""
        file_filter = "NetCDF (*.nc);;All Files (*)"
        last_folder = QSettings().value("threedi/last_precipitation_folder", os.path.expanduser("~"), type=str)
        filename, __ = QFileDialog.getOpenFileName(self, "Precipitation Time Series", last_folder, file_filter)
        if len(filename) == 0:
            return
        QSettings().setValue("threedi/last_precipitation_folder", os.path.dirname(filename))
        simulation = self.dd_simulation.currentText()
        self.le_upload_netcdf.setText(filename)
        self.custom_time_series[simulation] = []
        self.plot_precipitation()

    def set_design_time_series(self):
        """Setting time series based on selected design number."""
        simulation = self.dd_simulation.currentText()
        design_id = self.cbo_design.currentText()
        # Make copy of the values and add 0.0 value at the end of series
        series = self.AREA_WIDE_RAIN[design_id][:]
        series.append(0.0)
        period_txt, type_txt = self.RAIN_LOOKUP[design_id]
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
        if current_text == EventTypes.CONSTANT.value:
            start = self.sp_start_after_constant.value()
        elif current_text == EventTypes.FROM_CSV.value:
            start = self.sp_start_after_csv.value()
        elif current_text == EventTypes.DESIGN.value:
            start = self.sp_start_after_design.value()
        elif current_text == EventTypes.RADAR.value:
            start = self.sp_start_after_radar.value()
        else:
            return 0.0
        offset = start * to_seconds_multiplier
        return offset

    def get_precipitation_duration(self):
        """Calculating precipitation duration in seconds."""
        simulation = self.dd_simulation.currentText()
        current_text = self.cbo_prec_type.currentText()
        if current_text == EventTypes.CONSTANT.value or current_text == EventTypes.RADAR.value:
            to_seconds_multiplier = self.SECONDS_MULTIPLIERS[self.current_units]
            if current_text == EventTypes.CONSTANT.value:
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
        elif current_text == EventTypes.FROM_CSV.value:
            end_in_seconds = self.custom_time_series[simulation][-1][0] if self.custom_time_series[simulation] else 0
            precipitation_duration = end_in_seconds
        elif current_text == EventTypes.DESIGN.value:
            end_in_seconds = self.design_time_series[simulation][-1][0] if self.design_time_series[simulation] else 0
            precipitation_duration = end_in_seconds
        else:
            precipitation_duration = 0
        return precipitation_duration

    def get_precipitation_values(self):
        """Calculating precipitation values in 'm/s'."""
        simulation = self.dd_simulation.currentText()
        current_text = self.cbo_prec_type.currentText()
        if current_text == EventTypes.CONSTANT.value:
            values = mmh_to_ms(self.get_intensity())
        elif current_text == EventTypes.FROM_CSV.value:
            ts = self.custom_time_series[simulation]
            if self.cbo_units_csv.currentText() == "mm/h":
                values = [[t, mmh_to_ms(v)] for t, v in ts]
            else:
                timestep = ts[1][0] - ts[0][0] if len(ts) > 1 else 1
                values = [[t, mmh_to_ms(mmtimestep_to_mmh(v, timestep))] for t, v in ts]
        elif current_text == EventTypes.DESIGN.value:
            values = [
                [t, mmh_to_ms(mmtimestep_to_mmh(v, self.DESIGN_5_MINUTES_TIMESTEP))]
                for t, v in self.design_time_series[simulation]
            ]
        else:
            values = []
        return values

    def get_precipitation_data(self):
        """Getting all needed data for adding precipitation to the simulation.
        
            Note that the current simulation has just been selected in the combobox, so the substance widgets
            are up to date for this current simulation
        """

        precipitation_type = self.cbo_prec_type.currentText()
        offset = self.get_precipitation_offset()
        duration = self.get_precipitation_duration()
        units = "m/s"
        values = self.get_precipitation_values()
        start, end = self.parent_page.parent_wizard.duration_page.main_widget.to_datetime()
        interpolate = self.cb_interpolate_rain.isChecked()
        csv_filepath = self.le_upload_csv.text()
        netcdf_filepath = self.le_upload_netcdf.text()
        netcdf_global = self.rb_global_netcdf.isChecked()
        netcdf_raster = self.rb_raster_netcdf.isChecked()

        # Retrieve substance data from widgets, these have been properly set in run_new_simulation
        substances = []
        if not ((precipitation_type == EventTypes.FROM_NETCDF.value) or (precipitation_type == EventTypes.RADAR.value) or (precipitation_type == "None")):
            for substance in self.substances:
                substance_name = substance["name"]
                substance_widget = self.substance_widgets[substance_name]
                sub_value = substance_widget.get_value()
                if sub_value is not None:
                    substances.append({"substance": substance_name, "substance_id": None, "substance_name": substance_name, "concentrations": [[0.0, sub_value]]})

        return (
            precipitation_type,
            offset,
            duration,
            units,
            values,
            start,
            interpolate,
            csv_filepath,
            netcdf_filepath,
            netcdf_global,
            netcdf_raster,
            substances,
        )

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

    def from_csv_values(self):
        """Getting plot values for the CSV derived precipitation."""
        simulation = self.dd_simulation.currentText()
        x_values, y_values = [], []
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
    
    class PrecipationSubstanceWidget(QWidget):

        value_changed = pyqtSignal()

        def __init__(self, name:str, value:float, unit:str, parent):
            super().__init__(parent)
            self.setLayout(QHBoxLayout())
            name_label = QLabel(name, self)
            name_label.setFixedWidth(200)
            self.layout().addWidget(name_label)
            self.line_edit = QLineEdit(str(value), self)
            # Connect signal to signal
            self.line_edit.textChanged.connect(self.value_changed)

            # Value can only be numeric
            self.line_edit.setValidator(QDoubleValidator(0, 1000000, 4, self.line_edit))
            self.layout().addWidget(self.line_edit)
            self.unit_label = QLabel(unit, self)
            self.unit_label.setFixedWidth(30)
            self.layout().addWidget(self.unit_label)

        def set_unit_label(self, label:str) -> None:
            self.unit_label.setText(label)

        def get_value(self) -> Optional[float]:
            if self.line_edit.text() == "":
                return None
            
            return float(self.line_edit.text())

        def set_value(self, value: float) -> None:
            self.line_edit.setText(str(value))


    def update_substance_widgets(self):

        # For NetCDF or radar rain, we do not apply substance concentrations        
        precipitation_type_str = self.cbo_prec_type.currentText()
        if precipitation_type_str == "None" or (EventTypes(precipitation_type_str) == EventTypes.FROM_NETCDF) or (EventTypes(precipitation_type_str) == EventTypes.RADAR):
            for substance_widget in self.substance_widgets.values():
                self.substance_widget.layout().removeWidget(substance_widget)
                del substance_widget
            self.substance_widgets.clear()
            self.substance_widget.hide()
            return
        else:
            self.substance_widget.show()

        # Check if we have something to remove
        widgets_to_remove = []
        for name, substance_widget in self.substance_widgets.items():
            if len([item for item in self.substances if item["name"] == name]) == 0:
                # It is in the widgets list, but not in the substances list, remove.
                self.substance_widget.layout().removeWidget(substance_widget)
                del substance_widget
                widgets_to_remove.append(name)
                
        for widget_name in widgets_to_remove:
            del self.substance_widgets[widget_name]

        # Check if we have something to add
        for substance in self.substances:
            substance_name = substance["name"]
            if substance_name not in self.substance_widgets:
                wid = PrecipitationWidget.PrecipationSubstanceWidget(substance_name, "", substance.get("units", ""), self.substance_widget)
                wid.value_changed.connect(self.store_cache)
                self.substance_widgets[substance_name] = wid  # name is enforce to be unique in UI
                self.substance_widget.layout().addWidget(wid)
            else:
                # Set the units, these might have been changed
                self.substance_widgets[substance_name].set_unit_label(substance.get("units", ""))

    
    def plot_precipitation(self):
        """Setting up precipitation plot."""
        self.refresh_duration()
        self.plot_widget.clear()
        self.plot_label.show()
        self.plot_widget.show()
        self.plot_bar_graph = None
        self.plot_ticks = None
        self.label_cet_info.hide()
        current_text = self.cbo_prec_type.currentText()
        if current_text == EventTypes.CONSTANT.value:
            x_values, y_values = self.constant_values()
        elif current_text == EventTypes.FROM_CSV.value:
            x_values, y_values = self.from_csv_values()
        elif current_text == EventTypes.DESIGN.value:
            x_values, y_values = self.design_values()
        elif current_text in {EventTypes.FROM_NETCDF.value, EventTypes.RADAR.value}:
            x_values, y_values = [], []
            self.plot_widget.hide()
            self.plot_label.hide()
            if current_text == EventTypes.RADAR.value:
                self.label_cet_info.show()
        else:
            self.plot_widget.hide()
            self.plot_label.hide()
            return
        self.store_cache()
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
        if current_text == EventTypes.CONSTANT.value:
            precipitation_values = y_values[:-1]
        else:
            precipitation_values = y_values
        if current_text == EventTypes.CONSTANT.value:
            self.total_precipitation = sum(mmh_to_mmtimestep(v, 1, self.current_units) for v in precipitation_values)
        elif current_text == EventTypes.FROM_CSV.value and self.cbo_units_csv.currentText() == "mm/h":
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
        if current_text == EventTypes.CONSTANT.value:
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
        if current_text == EventTypes.CONSTANT.value:
            self.current_units = self.start_wind_constant_u.currentText()
        else:
            self.current_units = self.start_wind_custom_u.currentText()

    def set_custom_wind(self):
        """Selecting and setting up wind time series from CSV format."""
        file_filter = "CSV (*.csv);;All Files (*)"
        last_folder = read_3di_settings("last_wind_folder", os.path.expanduser("~"))
        filename, __ = QFileDialog.getOpenFileName(self, "Wind Time Series", last_folder, file_filter)
        if len(filename) == 0:
            return
        save_3di_settings("last_wind_folder", os.path.dirname(filename))
        time_series = []
        with open(filename, encoding="utf-8-sig") as wind_file:
            wind_reader = csv.reader(wind_file)
            units_multiplier = self.SECONDS_MULTIPLIERS["mins"]
            for timestep, windspeed, direction in wind_reader:
                # We are assuming that timestep is in minutes, so we are converting it to seconds on the fly.
                try:
                    time_series.append([float(timestep) * units_multiplier, float(windspeed), float(direction)])
                except ValueError:
                    continue
        self.le_upload_wind.setText(filename)
        self.custom_wind = time_series

    def get_wind_offset(self):
        """Calculating wind offset in seconds."""
        current_text = self.cbo_wind_type.currentText()
        to_seconds_multiplier = self.SECONDS_MULTIPLIERS[self.current_units]
        if current_text == EventTypes.CONSTANT.value:
            start = self.sp_start_wind_constant.value()
        elif current_text == EventTypes.FROM_CSV.value:
            start = self.sp_start_wind_custom.value()
        else:
            return 0.0
        offset = start * to_seconds_multiplier
        return offset

    def get_wind_duration(self):
        """Calculating wind duration in seconds."""
        current_text = self.cbo_wind_type.currentText()
        if current_text == EventTypes.CONSTANT.value:
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
        elif current_text == EventTypes.FROM_CSV.value:
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
        if current_text == EventTypes.CONSTANT.value:
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


class SavedStateWidget(uicls_saved_state_page, basecls_saved_state_page):
    """Widget for the new saved state page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        set_widget_background_color(self)
        self.connect_signals()
        # Hide stable flow widgets until backend will be able to handle it
        self.rb_stable_flow.hide()
        self.gb_stable_flow.hide()

    def connect_signals(self):
        """Connecting widgets signals."""
        self.rb_end_of_sim.toggled.connect(self.on_creation_options_changed)
        self.rb_after_time.toggled.connect(self.on_creation_options_changed)
        self.rb_stable_flow.toggled.connect(self.on_creation_options_changed)
        self.rb_water_level.toggled.connect(self.on_creation_options_changed)
        self.rb_flow_velocity.toggled.connect(self.on_creation_options_changed)

    def on_creation_options_changed(self):
        """On saved state creation option change"""
        if self.rb_stable_flow.isChecked():
            self.gb_stable_flow.setEnabled(True)
            if self.rb_water_level.isChecked():
                self.sp_threshold.setSuffix(" m")
            if self.rb_flow_velocity.isChecked():
                self.sp_threshold.setSuffix(" m/s")
        else:
            self.gb_stable_flow.setDisabled(True)

    def get_saved_state_data(self):
        """Get saved state data."""
        name = self.le_saved_state_name.text()
        tags_str = self.le_saved_state_tags.text().strip()
        tags = [text.strip() for text in tags_str.split(",")] if tags_str else []
        after_time = -1
        thresholds = []
        if self.rb_after_time.isChecked():
            units = self.cbo_units.currentText()
            if units == "hrs":
                seconds_per_unit = 3600
            elif units == "mins":
                seconds_per_unit = 60
            else:
                seconds_per_unit = 1
            after_time = self.sp_time.value() * seconds_per_unit
        elif self.rb_stable_flow.isChecked():
            threshold = Threshold(
                variable="s1" if self.rb_water_level.isChecked() else "u1", value=self.sp_threshold.value()
            )
            thresholds.append(threshold)
        return name, tags, after_time, thresholds


class LizardPostprocessingWidget(uicls_lizard_post_processing_page, basecls_lizard_post_processing_page):
    """Widget for the Post-processing in Lizard page."""

    COST_TYPES = ["min", "avg", "max"]
    MONTHS = OrderedDict(
        (
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may", "may"),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sep"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        )
    )

    REPAIR_TIME = OrderedDict(
        (
            ("6 hours", 6),
            ("1 day", 24),
            ("2 days", 48),
            ("5 days", 120),
            ("10 days", 240),
        )
    )

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        set_widget_background_color(self)
        self.template_file_structure_controls = None
        self.template_memory_structure_controls = None
        self.template_table_structure_controls = None
        self.template_timed_structure_controls = None
        self.setup_damage_estimation_widgets()
        self.connect_signals()

    def connect_signals(self):
        """Connecting widgets signals."""
        self.cb_damage_estimation.toggled.connect(self.toggle_damage_estimation)

    def setup_damage_estimation_widgets(self):
        """Setup damage estimation values."""
        self.cbo_cost_type.addItems(self.COST_TYPES)
        self.cbo_cost_type.setCurrentText("avg")
        self.cbo_flood_month.addItems(list(self.MONTHS.keys()))
        self.cbo_flood_month.setCurrentText("september")
        self.cbo_repair_infrastructure.addItems(list(self.REPAIR_TIME.keys()))
        self.cbo_repair_infrastructure.setCurrentText("1 day")
        self.cbo_repair_building.addItems(list(self.REPAIR_TIME.keys()))
        self.cbo_repair_building.setCurrentText("6 hours")

    def toggle_damage_estimation(self, checked):
        """Activate/deactivate damage estimation widgets."""
        if checked:
            self.damage_estimation_widget.setEnabled(True)
        else:
            self.damage_estimation_widget.setDisabled(True)

    def get_lizard_postprocessing_data(self):
        """Getting all needed data for setting post-processing in Lizard."""
        arrival_time_map = self.cb_arrival_time_map.isChecked()
        damage_estimation = self.cb_damage_estimation.isChecked()
        cost_type = self.cbo_cost_type.currentText()
        flood_month = self.MONTHS[self.cbo_flood_month.currentText()]
        inundation_period = self.sb_period.value()
        repair_time_infrastructure = self.REPAIR_TIME[self.cbo_repair_infrastructure.currentText()]
        repair_time_buildings = self.REPAIR_TIME[self.cbo_repair_building.currentText()]
        return (
            arrival_time_map,
            damage_estimation,
            cost_type,
            flood_month,
            inundation_period,
            repair_time_infrastructure,
            repair_time_buildings,
        )


class SummaryWidget(uicls_summary_page, basecls_summary_page):
    """Widget for the Summary page."""

    def __init__(self, parent_page, initial_conditions=None):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        set_widget_background_color(self)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(None)
        self.plot_widget.setFixedHeight(80)
        self.lout_plot.addWidget(self.plot_widget, 0, 0)
        self.template_widget.hide()
        self.cb_save_template.stateChanged.connect(self.save_template_state_changed)
        self.dd_simulation.currentIndexChanged.connect(self.simulation_change)
        self.precipitation_widget.hide()
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
                if ptype != EventTypes.RADAR.value:
                    total_prec_val = self.parent_page.parent_wizard.precipitation_page.main_widget.total_precipitation
                    total_prec = f"{total_prec_val:.1f}"
                else:
                    total_prec = "N/A"
                self.sim_prec_type.setText(ptype)
                self.sim_prec_total.setText(total_prec)

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

    STEP_NAME = "Name"

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

    STEP_NAME = "Duration"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = SimulationDurationWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget, 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class SubstancesPage(QWizardPage):
    """Substances definition page."""

    STEP_NAME = "Substances"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = SubstancesWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class BoundaryConditionsPage(QWizardPage):
    """Boundary conditions definition page."""

    STEP_NAME = "Boundary conditions"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = BoundaryConditionsWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()

    def validatePage(self):
        """Overriding page validation logic."""
        if self.main_widget.rb_upload_file.isChecked():
            if not any(
                (
                    self.main_widget.gb_upload_1d.isChecked(),
                    self.main_widget.gb_upload_2d.isChecked(),
                )
            ):
                warn = (
                    "There are no any boundary conditions selected for the upload. "
                    "Please select at least one 1D/2D boundary conditions file."
                )
                self.parent_wizard.plugin_dock.communication.show_warn(warn)
                return False
            else:
                if self.main_widget.gb_upload_1d.isChecked() and not self.main_widget.file_bc_1d_upload.text():
                    warn = "There is no 1D boundary conditions file specified. Please select it before proceeding."
                    self.parent_wizard.plugin_dock.communication.show_warn(warn)
                    return False
                if self.main_widget.gb_upload_2d.isChecked() and not self.main_widget.file_bc_2d_upload.text():
                    warn = "There is no 2D boundary conditions file specified. Please select it before proceeding."
                    self.parent_wizard.plugin_dock.communication.show_warn(warn)
                    return False
        return True


class StructureControlsPage(QWizardPage):
    """Control structures definition page."""

    STEP_NAME = "Structure controls"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = StructureControlsWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class InitialConditionsPage(QWizardPage):
    """Initial condition definition page."""

    STEP_NAME = "Initial conditions"

    def __init__(self, parent=None, initial_conditions=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = InitialConditionsWidget(self, initial_conditions=initial_conditions)
        # Create a scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameStyle(QScrollArea.NoFrame)
        self.scroll_area.setWidget(self.main_widget)
        layout = QGridLayout()
        layout.addWidget(self.scroll_area)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class LateralsPage(QWizardPage):
    """Laterals definition page."""

    STEP_NAME = "Laterals"

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

    STEP_NAME = "Dry weather flow"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = DWFWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.registerField("dwf_upload*", self.main_widget.dwf_upload)
        self.adjustSize()


class BreachesPage(QWizardPage):
    """Breaches definition page."""

    STEP_NAME = "Breaches"

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

    STEP_NAME = "Precipitation"

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

    STEP_NAME = "Wind"

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

    STEP_NAME = "Settings"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = SettingsWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class SavedStatePage(QWizardPage):
    """New saved state definition page."""

    STEP_NAME = "Generate saved state"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = SavedStateWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.registerField("saved_state_name*", self.main_widget.le_saved_state_name)
        self.adjustSize()


class LizardPostProcessingPage(QWizardPage):
    """Post-processing in Lizard definition page."""

    STEP_NAME = "Post-processing in Lizard"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = LizardPostprocessingWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class SummaryPage(QWizardPage):
    """New simulation summary page."""

    STEP_NAME = "Start the simulation"

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
        self.addPage(self.name_page)
        self.duration_page = SimulationDurationPage(self)
        self.addPage(self.duration_page)
        if init_conditions.include_substances:
            self.substances_page = SubstancesPage(self)
            self.addPage(self.substances_page)
        if init_conditions.include_boundary_conditions:
            self.boundary_conditions_page = BoundaryConditionsPage(self)
            self.addPage(self.boundary_conditions_page)
        if init_conditions.include_structure_controls:
            self.structure_controls_page = StructureControlsPage(self)
            self.addPage(self.structure_controls_page)
        if init_conditions.include_initial_conditions:
            self.init_conditions_page = InitialConditionsPage(self, initial_conditions=init_conditions)
            self.addPage(self.init_conditions_page)
        if init_conditions.include_laterals:
            self.laterals_page = LateralsPage(self)
            self.addPage(self.laterals_page)
        if init_conditions.include_dwf:
            self.dwf_page = DWFPage(self)
            self.addPage(self.dwf_page)
        if init_conditions.include_breaches:
            self.model_selection_dlg.load_breach_layers()
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
        if init_conditions.generate_saved_state:
            self.generate_saved_state_page = SavedStatePage(self)
            self.addPage(self.generate_saved_state_page)
        if init_conditions.include_lizard_post_processing:
            self.lizard_post_processing_page = LizardPostProcessingPage(self)
            self.addPage(self.lizard_post_processing_page)
        self.summary_page = SummaryPage(self, initial_conditions=init_conditions)
        self.addPage(self.summary_page)
        self.currentIdChanged.connect(self.page_changed)
        self.setButtonText(QWizard.FinishButton, "Add to queue")
        self.finish_btn = self.button(QWizard.FinishButton)
        self.finish_btn.clicked.connect(self.run_new_simulation)
        self.cancel_btn = self.button(QWizard.CancelButton)
        self.cancel_btn.clicked.connect(self.cancel_wizard)
        self.new_simulations = []
        self.setWindowTitle("New simulation")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.resize(self.settings.value("threedi/wizard_size", QSize(1000, 750)))
        self.first_simulation = init_conditions.simulations_list[0]
        self.init_conditions = init_conditions
        self.setup_step_labels()

    @property
    def wizard_pages_mapping(self):
        """Mapping of the page ids with their associated page objects."""
        pages_mapping = OrderedDict((page_id, self.page(page_id)) for page_id in self.pageIds())
        return pages_mapping

    def setup_step_labels(self):
        """Setup wizard steps labels."""
        font = QFont("Segoe UI", 10)
        for page_id, page in self.wizard_pages_mapping.items():
            page_step_labels = []
            wizard_steps_layout = page.main_widget.wizard_steps_widget.layout()
            for other_page_id, other_page in self.wizard_pages_mapping.items():
                label = QLabel()
                label.setFont(font)
                label.setTextFormat(Qt.RichText)
                if page_id > other_page_id:
                    label.setText(f"✓ {other_page.STEP_NAME}")
                elif page_id < other_page_id:
                    label.setText(other_page.STEP_NAME)
                    label.setStyleSheet("color: #6e6e6e")
                else:
                    label.setText(other_page.STEP_NAME)
                    label.setStyleSheet("font-weight: bold")
                page_step_labels.append(label)
            for page_label in page_step_labels:
                wizard_steps_layout.addWidget(page_label)
            spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
            wizard_steps_layout.addItem(spacer)

    def page_changed(self):
        """Extra pre-processing triggered by changes of the wizard pages."""
        current_page = self.currentPage()
        if isinstance(current_page, PrecipitationPage):
            # this order matters
            self.precipitation_page.main_widget.update_substance_widgets()
            self.precipitation_page.main_widget.plot_precipitation()
        elif isinstance(current_page, SummaryPage):
            self.set_overview_name()
            self.set_overview_database()
            self.set_overview_duration()
            if self.init_conditions.include_precipitations:
                self.summary_page.main_widget.plot_overview_precipitation()
                self.set_overview_precipitation()
        elif isinstance(current_page, LateralsPage):
            laterals_widget = self.laterals_page.main_widget
            laterals_widget.il_1d_upload.setText(laterals_widget.last_upload_1d_filepath)
            laterals_widget.il_2d_upload.setText(laterals_widget.last_upload_2d_filepath)
        elif isinstance(current_page, DWFPage):
            dwf_widget = self.dwf_page.main_widget
            dwf_widget.dwf_upload.setText(dwf_widget.last_upload_filepath)

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
            if precipitation_type != EventTypes.RADAR.value:
                total_precipitation_text = f"{total_precipitation:.0f} mm"
            else:
                total_precipitation_text = "N/A"
            self.summary_page.main_widget.sim_prec_total.setText(total_precipitation_text)

    def load_template_parameters(self, simulation, settings_overview, events, lizard_post_processing_overview):
        """Loading simulation parameters from the simulation template data."""
        # Simulation attributes
        from_template_placeholder = "<FROM TEMPLATE>"
        project_name, tags_list = "", []
        for tag in simulation.tags:
            if tag.startswith("project:"):
                project_name = tag.split(":", 1)[-1].strip()
            else:
                tags_list.append(tag)
        tags = ", ".join(tags_list)
        name_params = {"le_sim_name": simulation.name, "le_tags": tags, "le_project": project_name}
        set_widgets_parameters(self.name_page.main_widget, **name_params)
        temp_simulation_id = simulation.id
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
        if init_conditions.include_substances:

            substances = [{"name": item.name, "units": item.units or "", "decay_coefficient": item.decay_coefficient or "", "diffusion_coefficient": item.diffusion_coefficient or ""} for item in events.substances]
            if substances:
                self.substances_page.main_widget.prepopulate_substances_table(substances)
        if init_conditions.include_boundary_conditions:
            bc_widget = self.boundary_conditions_page.main_widget
            bc_file = events.fileboundaryconditions if events.fileboundaryconditions else None
            self.boundary_conditions_page.main_widget.set_template_boundary_conditions(bc_file)
            # Download file and set template boundary conditions timeseries
            if bc_file:
                tc = ThreediCalls(self.plugin_dock.threedi_api)
                bc_file_name = bc_file.file.filename
                bc_file_download = tc.fetch_boundarycondition_file_download(temp_simulation_id, bc_file.id)
                bc_temp_filepath = os.path.join(TEMPDIR, bc_file_name)
                get_download_file(bc_file_download, bc_temp_filepath)
                bc_timeseries = read_json_data(bc_temp_filepath)
                bc_timeseries_1d = [ts for ts in bc_timeseries if ts["type"] == "1D"]
                bc_timeseries_2d = [ts for ts in bc_timeseries if ts["type"] == "2D"]
                bc_widget.template_boundary_conditions_1d_timeseries = bc_timeseries_1d
                bc_widget.template_boundary_conditions_2d_timeseries = bc_timeseries_2d
        if init_conditions.include_structure_controls:
            temp_file_sc = events.filestructurecontrols[0] if events.filestructurecontrols else None
            temp_memory_sc = events.memorystructurecontrols[0] if events.memorystructurecontrols else None
            temp_table_sc = events.tablestructurecontrols[0] if events.tablestructurecontrols else None
            temp_timed_sc = events.timedstructurecontrols[0] if events.timedstructurecontrols else None
            self.structure_controls_page.main_widget.set_template_structure_controls(
                temp_file_sc, temp_memory_sc, temp_table_sc, temp_timed_sc
            )
        if init_conditions.include_initial_conditions:
            init_conditions_widget = self.init_conditions_page.main_widget
            if any(
                [
                    events.initial_onedwaterlevel,
                    events.initial_onedwaterlevelpredefined,
                    events.initial_onedwaterlevelfile,
                ]
            ):
                init_conditions_widget.gb_1d.setChecked(True)
                if events.initial_onedwaterlevel:
                    init_conditions_widget.rb_d1_gv.setChecked(True)
                    init_conditions_widget.sp_1d_global_value.setValue(events.initial_onedwaterlevel.value)
                else:
                    init_conditions_widget.rb_d1_dd.setChecked(True)
            if any([events.initial_twodwaterlevel, events.initial_twodwaterraster]):
                init_conditions_widget.gb_2d.setChecked(True)
                if events.initial_twodwaterlevel:
                    init_conditions_widget.sp_2d_global_value.setValue(events.initial_twodwaterlevel.value)
                elif events.initial_twodwaterraster:
                    for raster_filename, iw in init_conditions_widget.initial_waterlevels.items():
                        if iw.url == events.initial_twodwaterraster.initial_waterlevel:
                            init_conditions_widget.cbo_2d_online_raster.setCurrentText(raster_filename)
                            init_conditions_widget.cb_2d_aggregation.setCurrentText(
                                events.initial_twodwaterraster.aggregation_method
                            )
                            break
            if any([events.initial_groundwaterlevel, events.initial_groundwaterraster]):
                init_conditions_widget.gb_groundwater.setChecked(True)
                if events.initial_groundwaterlevel:
                    init_conditions_widget.sp_gwater_global_value.setValue(events.initial_groundwaterlevel.value)
                elif events.initial_groundwaterraster:
                    for raster_filename, iw in init_conditions_widget.initial_waterlevels.items():
                        if iw.url == events.initial_groundwaterraster.initial_waterlevel:
                            init_conditions_widget.cbo_gw_online_raster.setCurrentText(raster_filename)
                            init_conditions_widget.cb_gwater_aggregation.setCurrentText(
                                events.initial_groundwaterraster.aggregation_method
                            )
                            break
        if init_conditions.include_laterals:
            laterals_widget = self.laterals_page.main_widget
            laterals = events.laterals
            file_laterals = [filelateral for filelateral in events.filelaterals if filelateral.periodic != "daily"]
            if laterals:
                laterals_1d = []
                laterals_2d = []
                for lateral in laterals:
                    if hasattr(lateral, "point"):
                        laterals_2d.append(lateral)
                    else:
                        laterals_1d.append(lateral)
                if laterals_1d:
                    laterals_widget.cb_use_1d_laterals.setChecked(True)
                    laterals_widget.cb_upload_1d_laterals.setChecked(False)
                    laterals_widget.laterals_1d = laterals_1d
                if laterals_2d:
                    laterals_widget.cb_use_2d_laterals.setChecked(True)
                    laterals_widget.cb_upload_2d_laterals.setChecked(False)
                    laterals_widget.laterals_2d = laterals_2d
            if file_laterals:
                tc = ThreediCalls(self.plugin_dock.threedi_api)
                lateral_file = file_laterals[0]
                lateral_file_name = lateral_file.file.filename
                lateral_file_download = tc.fetch_lateral_file_download(temp_simulation_id, lateral_file.id)
                lateral_temp_filepath = os.path.join(TEMPDIR, lateral_file_name)
                get_download_file(lateral_file_download, lateral_temp_filepath)
                laterals_timeseries = read_json_data(lateral_temp_filepath)
                laterals_1d_timeseries = []
                laterals_2d_timeseries = []
                for ts in laterals_timeseries:
                    if "point" in ts:
                        # 2D laterals if point is present
                        laterals_2d_timeseries.append(ts)
                    else:
                        # 1D laterals if point is not present
                        laterals_1d_timeseries.append(ts)
                if laterals_1d_timeseries:
                    laterals_widget.cb_use_1d_laterals.setChecked(True)
                    laterals_widget.cb_upload_1d_laterals.setChecked(False)
                    try:
                        laterals_widget.laterals_1d_timeseries_template = {
                            str(lat["id"]): lat for lat in laterals_1d_timeseries
                        }
                    except KeyError:
                        laterals_widget.laterals_1d_timeseries_template = {
                            str(i): lat for i, lat in enumerate(laterals_1d_timeseries, 1)
                        }
                if laterals_2d_timeseries:
                    laterals_widget.cb_use_2d_laterals.setChecked(True)
                    laterals_widget.cb_upload_2d_laterals.setChecked(False)
                    try:
                        laterals_widget.laterals_2d_timeseries_template = {
                            str(lat["id"]): lat for lat in laterals_2d_timeseries
                        }
                    except KeyError:
                        laterals_widget.laterals_2d_timeseries_template = {
                            str(i): lat for i, lat in enumerate(laterals_2d_timeseries, 1)
                        }
                os.remove(lateral_temp_filepath)
            if not laterals and not file_laterals:
                laterals_widget.cb_use_1d_laterals.setEnabled(False)
                laterals_widget.cb_use_2d_laterals.setEnabled(False)
        if init_conditions.include_dwf:
            dwf_events = [filelateral for filelateral in events.filelaterals if filelateral.periodic == "daily"]
            if dwf_events:
                dwf_widget = self.dwf_page.main_widget
                tc = ThreediCalls(self.plugin_dock.threedi_api)
                dwf_file = dwf_events[0]
                dwf_file_name = dwf_file.file.filename
                dwf_file_download = tc.fetch_lateral_file_download(temp_simulation_id, dwf_file.id)
                dwf_temp_filepath = os.path.join(TEMPDIR, dwf_file_name)
                get_download_file(dwf_file_download, dwf_temp_filepath)
                dwf_timeseries = read_json_data(dwf_temp_filepath)
                last_dwf = dwf_timeseries[-1]
                dwf_widget.dwf_upload.setText(from_template_placeholder)
                dwf_widget.last_upload_filepath = from_template_placeholder
                dwf_widget.cb_interpolate_dwf.setChecked(last_dwf["interpolate"])
                try:
                    dwf_widget.dwf_timeseries = {str(dwf["id"]): dwf for dwf in dwf_timeseries}
                except KeyError:
                    dwf_widget.dwf_timeseries = {str(i): dwf for i, dwf in enumerate(dwf_timeseries)}
                dwf_widget.last_uploaded_dwf = dwf_timeseries[-1]
                os.remove(dwf_temp_filepath)
        if init_conditions.include_breaches:
            breaches_widget = self.breaches_page.main_widget
            if events.breach:
                tc = ThreediCalls(self.plugin_dock.threedi_api)
                threedimodel_id_str = str(self.model_selection_dlg.current_model.id)
                content_pks = set()
                for breach in events.breach:
                    potential_breach_url = breach.potential_breach.rstrip("/")
                    potential_breach_id = int(potential_breach_url.split("/")[-1])
                    potential_breach = tc.fetch_3di_model_potential_breach(threedimodel_id_str, potential_breach_id)
                    content_pks.add(str(potential_breach.connected_pnt_id))
                content_pks_str = ",".join(content_pks)
                exp = f'"content_pk" in ({content_pks_str})'
                self.model_selection_dlg.potential_breaches_layer.selectByExpression(exp)
                for breach_feat in self.model_selection_dlg.potential_breaches_layer.selectedFeatures():
                    breaches_widget.on_potential_breach_feature_identified(breach_feat)
        if init_conditions.include_precipitations:
            precipitation_widget = self.precipitation_page.main_widget
            # Check whether we have a constant substance value
            if events.timeseriesrain:
                rain = events.timeseriesrain[0]
                if rain.substances:
                    for substance in rain.substances:
                        initial_value = substance.concentrations[0][1]
                        for _, value in substance.concentrations:
                            assert initial_value == value

            if events.timeseriesrain:
                if rain.constant:
                    precipitation_widget.cbo_prec_type.setCurrentText(EventTypes.CONSTANT.value)
                    rain_constant_start_after = rain.offset // 3600
                    rain_constant_duration = rain.duration // 3600
                    rain_constant_stop_after = rain_constant_start_after + rain_constant_duration
                    precipitation_widget.sp_start_after_constant.setValue(rain_constant_start_after)
                    if rain.duration <= simulation_duration:
                        precipitation_widget.sp_stop_after_constant.setValue(rain_constant_stop_after)
                    intensity_ms = rain.values[0][-1]
                    intensity_mmh = ms_to_mmh(intensity_ms)
                    precipitation_widget.sp_intensity.setValue(intensity_mmh)
                    # As template parameters are always a single simulation, we can just build the widgets
                    precipitation_widget.update_substance_widgets()
                else:
                    simulation = precipitation_widget.dd_simulation.currentText()
                    precipitation_widget.cbo_prec_type.setCurrentText(EventTypes.FROM_CSV.value)
                    precipitation_widget.le_upload_csv.setText(from_template_placeholder)
                    precipitation_widget.sp_start_after_csv.setValue(rain.offset // 3600)
                    precipitation_widget.cb_interpolate_rain.setChecked(rain.interpolate)
                    rain_values = rain.values
                    timestep = rain_values[1][0] - rain_values[0][0]
                    mm_timestep = [[t, mmh_to_mmtimestep(ms_to_mmh(v), timestep)] for t, v in rain_values]
                    precipitation_widget.custom_time_series[simulation] = mm_timestep
                    precipitation_widget.update_substance_widgets()
                    precipitation_widget.plot_precipitation()

                # We now know all substance widgets are in place, we can set the template value
                for substance in rain.substances:
                    precipitation_widget.substance_widgets[substance.substance_name].set_value(substance.concentrations[0][1])

            if events.lizardrasterrain:
                rain = events.lizardrasterrain[0]
                precipitation_widget.cbo_prec_type.setCurrentText(EventTypes.RADAR.value)
                rain_radar_start_after = rain.offset // 3600
                rain_radar_duration = rain.duration // 3600
                rain_radar_stop_after = rain_radar_start_after + rain_radar_duration
                precipitation_widget.sp_start_after_radar.setValue(rain_radar_start_after)
                if rain.duration <= simulation_duration:
                    precipitation_widget.sp_stop_after_radar.setValue(rain_radar_stop_after)
                precipitation_widget.update_substance_widgets()

        if init_conditions.include_wind:
            wind_widget = self.wind_page.main_widget
            if events.wind:
                wind = events.wind[0]
                initial_winddragcoefficient = events.initial_winddragcoefficient
                if wind.speed_constant and wind.direction_constant:
                    wind_widget.cbo_wind_type.setCurrentText(EventTypes.CONSTANT.value)
                    wind_widget.sp_start_wind_constant.setValue(wind.offset // 3600)
                    wind_widget.cbo_windspeed_u.setCurrentText(wind.units)
                    timestep, speed, direction = wind.values[0]
                    wind_widget.sp_windspeed.setValue(speed)
                    wind_widget.sp_direction.setValue(direction)
                    if initial_winddragcoefficient:
                        wind_widget.sp_dc_constant.setValue(initial_winddragcoefficient.value)
                else:
                    wind_widget.cbo_wind_type.setCurrentText(EventTypes.FROM_CSV.value)
                    wind_widget.le_upload_wind.setText(from_template_placeholder)
                    wind_widget.sp_start_wind_custom.setValue(wind.offset // 3600)
                    wind_widget.cb_interpolate_speed.setChecked(wind.speed_interpolate)
                    wind_widget.cb_interpolate_direction.setChecked(wind.direction_interpolate)
                    wind_timeseries = wind.values
                    wind_timeseries_minutes = [
                        [timestep // 60, speed, direction] for timestep, speed, direction in wind_timeseries
                    ]
                    wind_widget.custom_wind = wind_timeseries_minutes
                    if initial_winddragcoefficient:
                        wind_widget.sp_dc_custom.setValue(initial_winddragcoefficient.value)
        if init_conditions.include_lizard_post_processing and lizard_post_processing_overview:
            post_processing_widget = self.lizard_post_processing_page.main_widget
            post_processing_results = lizard_post_processing_overview.results
            post_processing_settings = lizard_post_processing_overview.settings
            arrival_time = post_processing_results.arrival_time
            damage_estimation = post_processing_results.damage_estimation
            if arrival_time:
                post_processing_widget.cb_arrival_time_map.setChecked(True)
            if damage_estimation:
                damage_estimation_settings = post_processing_settings.damage_estimation
                repair_time_seconds_map = {int(v * 3600): k for k, v in post_processing_widget.REPAIR_TIME.items()}
                post_processing_widget.cb_damage_estimation.setChecked(True)
                cost_type = damage_estimation_settings.cost_type
                flood_month = damage_estimation_settings.flood_month
                inundation_period = damage_estimation_settings.inundation_period
                repair_time_infrastructure = damage_estimation_settings.repair_time_infrastructure
                repair_time_buildings = damage_estimation_settings.repair_time_buildings
                if cost_type:
                    post_processing_widget.cbo_cost_type.setCurrentIndex(cost_type - 1)
                if flood_month:
                    post_processing_widget.cbo_flood_month.setCurrentIndex(flood_month - 1)
                if inundation_period:
                    post_processing_widget.sb_period.setValue(inundation_period / 3600)
                if repair_time_infrastructure in repair_time_seconds_map:
                    post_processing_widget.cbo_repair_infrastructure.setCurrentText(
                        repair_time_seconds_map[repair_time_infrastructure]
                    )
                if repair_time_buildings in repair_time_seconds_map:
                    post_processing_widget.cbo_repair_building.setCurrentText(
                        repair_time_seconds_map[repair_time_buildings]
                    )

    def run_new_simulation(self):
        """Getting data from the wizard and running new simulation."""
        self.settings.setValue("threedi/wizard_size", self.size())
        events = self.init_conditions_dlg.events
        name = self.name_page.main_widget.le_sim_name.text().strip()
        project_name = self.name_page.main_widget.le_project.text().strip()
        tags = [tag.strip() for tag in self.name_page.main_widget.le_tags.text().split(",")]
        if project_name:
            project_name_tag = f"project: {project_name}"
            tags.append(project_name_tag)
        threedimodel_id = self.model_selection_dlg.current_model.id
        organisation_uuid = self.model_selection_dlg.organisation.unique_id
        start_datetime, end_datetime = self.duration_page.main_widget.to_datetime()
        duration = self.duration_page.main_widget.calculate_simulation_duration()
        # Initialization options
        init_options = dm.InitOptions()
        init_options.generate_saved_state = self.init_conditions.generate_saved_state
        if self.init_conditions.include_raster_edits:
            init_options.raster_edits = events.rasteredits[0]
        if self.init_conditions.include_leakage:
            leakage = dm.Leakage()
            if events.leakage:
                leakage.timeseries_leakage_overview = events.leakage[0]
            if events.filetimeseriesleakage:
                leakage.file_timeseries_leakage = events.filetimeseriesleakage[0]
            if events.filerasterleakage:
                leakage.file_raster_leakage = events.filerasterleakage[0]
            init_options.leakage = leakage
        if self.init_conditions.include_sources_sinks:
            sources_sinks = dm.SourcesSinks()
            if events.lizardrastersourcessinks:
                sources_sinks.lizard_raster_sources_sinks = events.lizardrastersourcessinks[0]
            if events.lizardtimeseriessourcessinks:
                sources_sinks.lizard_timeseries_sources_sinks = events.lizardtimeseriessourcessinks[0]
            if events.filerastersourcessinks:
                sources_sinks.file_raster_sources_sinks = events.filerastersourcessinks[0]
            if events.filetimeseriessourcessinks:
                sources_sinks.file_timeseries_sources_sinks = events.filetimeseriessourcessinks[0]
            if events.timeseriessourcessinks:
                sources_sinks.timeseries_sources_sinks = events.timeseriessourcessinks[0]
            init_options.sources_sinks = sources_sinks
        if self.init_conditions.include_local_ts_rain:
            local_ts_rain = dm.LocalTimeseriesRain()
            if events.lizardtimeseriesrain:
                local_ts_rain.lizard_timeseries_rain = events.lizardtimeseriesrain[0]
            if events.filetimeseriesrain:
                local_ts_rain.file_timeseries_rain = events.filetimeseriesrain[0]
            if events.localrain:
                local_ts_rain.local_rain = events.localrain[0]
            init_options.local_timeseries_rain = local_ts_rain
        if self.init_conditions.include_obstacle_edits:
            init_options.obstacle_edits = events.obstacleedits[0]
        # Boundary conditions page attributes
        boundary_conditions = dm.BoundaryConditions()
        if self.init_conditions.include_boundary_conditions:
            (
                temp_file_boundary_conditions,
                boundary_conditions_data,
            ) = self.boundary_conditions_page.main_widget.get_boundary_conditions_data(timesteps_in_seconds=True)
            if self.boundary_conditions_page.main_widget.rb_from_template.isChecked():
                boundary_conditions.file_boundary_conditions = temp_file_boundary_conditions
            else:
                boundary_conditions.data = boundary_conditions_data
        # Structure controls page attributes
        structure_controls = dm.StructureControls()
        if self.init_conditions.include_structure_controls:
            (
                temp_file_structure_controls,
                temp_memory_structure_controls,
                temp_table_structure_controls,
                temp_timed_structure_controls,
                local_file_structure_controls,
            ) = self.structure_controls_page.main_widget.get_structure_control_data()
            if self.structure_controls_page.main_widget.gb_from_template.isChecked():
                if self.structure_controls_page.main_widget.cb_file_sc.isChecked():
                    structure_controls.file_structure_controls = temp_file_structure_controls
                if self.structure_controls_page.main_widget.cb_memory_sc.isChecked():
                    structure_controls.memory_structure_controls = temp_memory_structure_controls
                if self.structure_controls_page.main_widget.cb_table_sc.isChecked():
                    structure_controls.table_structure_controls = temp_table_structure_controls
                if self.structure_controls_page.main_widget.cb_timed_sc.isChecked():
                    structure_controls.timed_structure_controls = temp_timed_structure_controls
            if self.structure_controls_page.main_widget.gb_upload_file.isChecked():
                structure_controls.local_file_structure_controls = local_file_structure_controls

        # Initial conditions page attributes
        initial_conditions = dm.InitialConditions()
        if self.init_conditions.include_initial_conditions:
            # 1D
            if self.init_conditions_page.main_widget.gb_1d.isChecked():
                if self.init_conditions_page.main_widget.rb_d1_gv.isChecked():
                    initial_conditions.global_value_1d = (
                        self.init_conditions_page.main_widget.sp_1d_global_value.value()
                    )
                elif self.init_conditions_page.main_widget.rb_1d_upload_csv.isChecked():
                    initial_conditions.initial_waterlevels_1d = (
                        self.init_conditions_page.main_widget.initial_waterlevels_1d
                    )
                else:
                    initial_conditions.from_spatialite_1d = True
            # 2D
            if self.init_conditions_page.main_widget.gb_2d.isChecked():
                if self.init_conditions_page.main_widget.rb_2d_global_value.isChecked():
                    initial_conditions.global_value_2d = (
                        self.init_conditions_page.main_widget.sp_2d_global_value.value()
                    )
                elif self.init_conditions_page.main_widget.rb_2d_online_raster.isChecked():
                    initial_conditions.online_raster_2d = self.init_conditions_page.main_widget.initial_waterlevels.get(
                        self.init_conditions_page.main_widget.cbo_2d_online_raster.currentText()
                    )
                else:
                    initial_conditions.local_raster_2d = qgis_layers_cbo_get_layer_uri(
                        self.init_conditions_page.main_widget.cbo_2d_local_raster
                    )
                initial_conditions.aggregation_method_2d = (
                    self.init_conditions_page.main_widget.cb_2d_aggregation.currentText()
                )
            # Groundwater
            if self.init_conditions_page.main_widget.gb_groundwater.isChecked():
                if self.init_conditions_page.main_widget.rb_gw_global_value.isChecked():
                    initial_conditions.global_value_groundwater = (
                        self.init_conditions_page.main_widget.sp_gwater_global_value.value()
                    )
                elif self.init_conditions_page.main_widget.rb_gw_online_raster.isChecked():
                    initial_conditions.online_raster_groundwater = (
                        self.init_conditions_page.main_widget.initial_waterlevels.get(
                            self.init_conditions_page.main_widget.cbo_gw_online_raster.currentText()
                        )
                    )
                else:
                    initial_conditions.local_raster_groundwater = qgis_layers_cbo_get_layer_uri(
                        self.init_conditions_page.main_widget.cbo_gw_local_raster
                    )
                initial_conditions.aggregation_method_groundwater = (
                    self.init_conditions_page.main_widget.cb_gwater_aggregation.currentText()
                )

            # Saved state
            if self.init_conditions_page.main_widget.gb_saved_state.isChecked():
                initial_conditions.saved_state = self.init_conditions_page.main_widget.saved_states.get(
                    self.init_conditions_page.main_widget.cbo_saved_states.currentText()
                )

            # Initial concentrations 2D for substances
            widget = self.init_conditions_page.main_widget.initial_concentrations_widget
            rasters = self.init_conditions_page.main_widget.rasters
            substances = self.init_conditions_page.main_widget.substances
            initial_concentrations_2d = {}
            for substance in substances:
                substance_name = substance.get("name")
                aggregation_method = widget.findChild(QComboBox, f"cbo_aggregation_{substance_name}").currentText()
                groupbox_ic = widget.findChild(QGroupBox, f"gb_initial_concentrations_2d_{substance_name}")
                rb_local_raster = widget.findChild(QRadioButton, f"rb_local_raster_{substance_name}")
                rb_online_raster = widget.findChild(QRadioButton, f"rb_online_raster_{substance_name}")
                cbo_local_raster = widget.findChild(QComboBox, f"cbo_local_raster_{substance_name}")
                cbo_online_raster = widget.findChild(QComboBox, f"cbo_online_raster_{substance_name}").currentText()
                if groupbox_ic and groupbox_ic.isChecked():
                    if rb_local_raster and rb_local_raster.isChecked() and cbo_local_raster:
                        layer_uri = qgis_layers_cbo_get_layer_uri(cbo_local_raster)
                        initial_concentrations = {
                            "local_raster_path": layer_uri,
                            "online_raster": None,
                            "aggregation_method": aggregation_method,
                        }
                        initial_concentrations_2d[substance_name] = initial_concentrations
                    if rb_online_raster and rb_online_raster.isChecked() and cbo_online_raster:
                        for raster in rasters:
                            if raster.name == cbo_online_raster:
                                initial_concentrations = {
                                    "local_raster_path": None,
                                    "online_raster": raster.id,
                                    "aggregation_method": aggregation_method,
                                }
                                initial_concentrations_2d[substance_name] = initial_concentrations
                                break
            if initial_concentrations_2d:
                initial_conditions.initial_concentrations_2d = initial_concentrations_2d

            widget = self.init_conditions_page.main_widget.initial_concentrations_widget_1D
            online_files = self.init_conditions_page.main_widget.online_files
            local_data = self.init_conditions_page.main_widget.local_data

            initial_concentrations_1d = {}
            for substance in substances:
                substance_name = substance.get("name")
                groupbox_ic_1d = widget.findChild(QGroupBox, f"gb_initial_concentrations_1d_{substance_name}")
                rb_local_file = widget.findChild(QRadioButton, f"rb_local_file_{substance_name}")
                rb_online_file = widget.findChild(QRadioButton, f"rb_online_file_1d_{substance_name}")
                cbo_online_file = widget.findChild(QComboBox, f"cbo_online_file_1d_{substance_name}")
                if groupbox_ic_1d.isChecked():
                    if rb_local_file.isChecked():
                        initial_concentrations = {
                            "local_data": local_data[substance_name],
                            "online_file": None,
                        }
                        initial_concentrations_1d[substance_name] = initial_concentrations
                    elif rb_online_file.isChecked():
                        for file in online_files:
                             if file.filename == cbo_online_file.currentText():
                                initial_concentrations = {
                                    "local_data": None,
                                    "online_file": file,
                                }
                                initial_concentrations_1d[substance_name] = initial_concentrations
                                break
                    assert initial_concentrations_1d[substance_name]
            if initial_concentrations_1d:
                initial_conditions.initial_concentrations_1d = initial_concentrations_1d

        # Laterals
        if self.init_conditions.include_laterals:
            constant_laterals, file_laterals_1d, file_laterals_2d = self.laterals_page.main_widget.get_laterals_data(
                timesteps_in_seconds=True
            )
            laterals = dm.Laterals(constant_laterals, file_laterals_1d, file_laterals_2d)
        else:
            laterals = dm.Laterals()
        # DWF
        if self.init_conditions.include_dwf:
            dwf_data = self.dwf_page.main_widget.get_dwf_data(timeseries24=True)
            dwf = dm.DWF(dwf_data)
        else:
            dwf = dm.DWF()
        # Wind
        if self.init_conditions.include_wind:
            wind_data = self.wind_page.main_widget.get_wind_data()
            wind = dm.Wind(*wind_data)
        else:
            wind = dm.Wind()
        # Substances
        if self.init_conditions.include_substances:
            substances = dm.Substances(self.substances_page.main_widget.substances)
        else:
            substances = dm.Substances()

        # Settings page attributes
        main_settings = self.settings_page.main_widget.collect_single_settings()
        physical_settings, numerical_settings, time_step_settings = main_settings
        aggregation_settings_list = self.settings_page.main_widget.collect_aggregation_settings()
        settings = dm.Settings(physical_settings, numerical_settings, time_step_settings, aggregation_settings_list)
        # Post-processing in Lizard
        lizard_post_processing = dm.LizardPostProcessing()
        if self.init_conditions.include_lizard_post_processing:
            lizard_post_processing.basic_post_processing = True
            (
                arrival_time_map_checked,
                damage_estimation_checked,
                cost_type,
                flood_month,
                inundation_period,
                repair_time_infrastructure,
                repair_time_buildings,
            ) = self.lizard_post_processing_page.main_widget.get_lizard_postprocessing_data()
            if arrival_time_map_checked:
                lizard_post_processing.arrival_time_map = True
            if damage_estimation_checked:
                damage_estimation = dm.DamageEstimation(
                    cost_type,
                    flood_month,
                    inundation_period,
                    repair_time_infrastructure,
                    repair_time_buildings,
                )
                lizard_post_processing.damage_estimation = damage_estimation
        # Generate saved state
        if self.init_conditions.generate_saved_state:
            new_saved_state_data = self.generate_saved_state_page.main_widget.get_saved_state_data()
            new_saved_state = dm.SavedState(*new_saved_state_data)
        else:
            new_saved_state = dm.SavedState()
        simulation_template = self.init_conditions_dlg.simulation_template
        sim_temp_id = simulation_template.simulation.id
        simulation_difference = self.init_conditions.simulations_difference
        for i, simulation in enumerate(self.init_conditions.simulations_list, start=1):
            sim_name = f"{name}_{i}" if self.init_conditions.multiple_simulations is True else name
            new_simulation = dm.NewSimulation(
                sim_temp_id, sim_name, tags, threedimodel_id, organisation_uuid, start_datetime, end_datetime, duration
            )
            new_simulation.init_options = init_options
            new_simulation.substances = substances
            new_simulation.boundary_conditions = boundary_conditions
            new_simulation.structure_controls = structure_controls
            new_simulation.initial_conditions = initial_conditions
            new_simulation.laterals = laterals
            new_simulation.dwf = dwf
            if self.init_conditions.include_breaches:
                self.breaches_page.main_widget.dd_simulation.setCurrentText(simulation)
                breach_data = self.breaches_page.main_widget.get_breaches_data()
                if simulation_difference == "breaches" or i == 1:
                    new_simulation.breaches = dm.Breaches(*breach_data)
                else:
                    new_simulation.breaches = dm.Breaches()
            if self.init_conditions.include_precipitations:
                logger.error(simulation)
                self.precipitation_page.main_widget.dd_simulation.setCurrentText(simulation)
                precipitation_data = self.precipitation_page.main_widget.get_precipitation_data()
                if simulation_difference == "precipitation" or i == 1:
                    new_simulation.precipitation = dm.Precipitation(*precipitation_data)
                else:
                    new_simulation.precipitation = dm.Precipitation()
            new_simulation.wind = wind
            new_simulation.settings = settings
            new_simulation.lizard_post_processing = lizard_post_processing
            new_simulation.new_saved_state = new_saved_state
            if self.summary_page.main_widget.cb_save_template.isChecked():
                template_name = self.summary_page.main_widget.template_name.text()
                new_simulation.template_name = template_name + f"_{i}"
            self.new_simulations.append(new_simulation)
        self.model_selection_dlg.unload_breach_layers()
        self.plugin_dock.simulation_overview_dlg.start_simulations(self.new_simulations)

    def cancel_wizard(self):
        """Handling canceling wizard action."""
        self.settings.setValue("threedi/wizard_size", self.size())
        self.model_selection_dlg.unload_breach_layers()
        self.reject()
