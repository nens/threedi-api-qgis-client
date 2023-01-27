# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import os
import csv
import pyqtgraph as pg
from dateutil.relativedelta import relativedelta
from datetime import datetime
from copy import deepcopy
from collections import defaultdict, OrderedDict
from functools import partial
from operator import attrgetter
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
    QLabel,
    QSpacerItem,
)
from qgis.core import QgsMapLayerProxyModel, NULL
from threedi_api_client.openapi import ApiException
from .custom_items import FilteredComboBox
from ..api_calls.threedi_calls import ThreediCalls
from ..data_models import simulation_data_models as dm
from ..utils import (
    apply_24h_timeseries,
    extract_error_message,
    mmh_to_ms,
    ms_to_mmh,
    mmh_to_mmtimestep,
    mmtimestep_to_mmh,
    get_download_file,
    read_json_data,
    intervals_are_even,
    TEMPDIR,
    EventTypes,
)
from ..utils_ui import (
    get_filepath,
    qgis_layers_cbo_get_layer_uri,
    set_widget_background_color,
    scan_widgets_parameters,
    set_widgets_parameters,
)


base_dir = os.path.dirname(os.path.dirname(__file__))
uicls_name_page, basecls_name_page = uic.loadUiType(os.path.join(base_dir, "ui", "simulation_wizard", "page_name.ui"))
uicls_duration_page, basecls_duration_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "simulation_wizard", "page_duration.ui")
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
uicls_summary_page, basecls_summary_page = uic.loadUiType(
    os.path.join(base_dir, "ui", "simulation_wizard", "page_initiation.ui")
)


class NameWidget(uicls_name_page, basecls_name_page):
    """Widget for the Name page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        set_widget_background_color(self)


class SimulationDurationWidget(uicls_duration_page, basecls_duration_page):
    """Widget for the Simulation Duration page."""

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
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
        """Updating label with simulation duration showed in the human-readable format."""
        try:
            start, end = self.to_datetime()
            if start > end:
                start = end
            rel_delta = relativedelta(end, start)
            duration = (rel_delta.years, rel_delta.months, rel_delta.days, rel_delta.hours, rel_delta.minutes)
            self.label_total_time.setText("{} years, {} months, {} days, {} hours, {} minutes".format(*duration))
        except ValueError:
            self.label_total_time.setText("Invalid datetime format!")


class BoundaryConditionsWidget(uicls_boundary_conditions, basecls_boundary_conditions):
    """Widget for the Boundary Conditions page."""

    TYPE_1D = "1D"
    TYPE_2D = "2D"

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        set_widget_background_color(self)
        self.template_boundary_conditions = None
        self.boundary_conditions_1d_timeseries = {}
        self.boundary_conditions_2d_timeseries = {}
        self.connect_signals()

    def connect_signals(self):
        """Connecting widgets signals."""
        self.rb_from_template.toggled.connect(self.change_boundary_conditions_source)
        self.rb_upload_file.toggled.connect(self.change_boundary_conditions_source)
        self.pb_upload_file_bc_1d.clicked.connect(partial(self.load_csv, self.TYPE_1D))
        self.pb_upload_file_bc_2d.clicked.connect(partial(self.load_csv, self.TYPE_2D))
        self.cb_interpolate_bc_1d.stateChanged.connect(partial(self.interpolate_changed, self.TYPE_1D))
        self.cb_interpolate_bc_2d.stateChanged.connect(partial(self.interpolate_changed, self.TYPE_2D))

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

    def handle_boundary_conditions_header(self, boundary_conditions_list, log_error=True):
        """
        Fetch first boundary conditions file row and handle potential header.
        Return None if fetch successful or error message if file is empty or have invalid structure.
        """
        error_message = None
        if not boundary_conditions_list:
            error_message = "Boundary conditions list is empty!"
            if log_error:
                self.parent_page.parent_wizard.plugin_dock.communication.show_warn(error_message)
            return error_message
        header = boundary_conditions_list[0]
        if len(header) != 2:
            error_message = "Wrong timeseries format for boundary conditions!"
        if error_message is None:
            try:
                timeseries_candidate = header[-1]
                [[float(f) for f in line.split(",")] for line in timeseries_candidate.split("\n")]
            except ValueError:
                boundary_conditions_list.pop(0)
        else:
            if log_error:
                self.parent_page.parent_wizard.plugin_dock.communication.show_warn(error_message)
        return error_message

    def open_upload_dialog(self, boundary_conditions_type):
        """Open dialog for selecting CSV file with boundary conditions."""
        last_folder = QSettings().value("threedi/last_boundary_conditions_folder", os.path.expanduser("~"), type=str)
        file_filter = "CSV (*.csv );;All Files (*)"
        filename, __ = QFileDialog.getOpenFileName(self, "Boundary Conditions Time Series", last_folder, file_filter)
        if len(filename) == 0:
            return None, None
        QSettings().setValue("threedi/last_boundary_conditions_folder", os.path.dirname(filename))
        values = {}
        boundary_conditions_list = []
        with open(filename, encoding="utf-8-sig") as boundary_conditions_file:
            boundary_conditions_reader = csv.reader(boundary_conditions_file)
            boundary_conditions_list += list(boundary_conditions_reader)
        error_msg = self.handle_boundary_conditions_header(boundary_conditions_list)
        if error_msg is not None:
            return None, None
        interpolate = (
            self.cb_interpolate_bc_1d.isChecked()
            if boundary_conditions_type == self.TYPE_1D
            else self.cb_interpolate_bc_2d.isChecked()
        )
        for bc_id, timeseries in boundary_conditions_list:
            try:
                vals = [[float(f) for f in line.split(",")] for line in timeseries.split("\n")]
                boundary_condition = {
                    "id": int(bc_id),
                    "type": boundary_conditions_type,
                    "interpolate": interpolate,
                    "values": vals,
                }
                values[bc_id] = boundary_condition
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
        for val in boundary_conditions_timeseries.values():
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
        if units == "hrs":
            seconds_per_unit = 3600
        elif units == "mins":
            seconds_per_unit = 60
        else:
            seconds_per_unit = 1
        for val in boundary_conditions_data.values():
            val["values"] = [[t * seconds_per_unit, v] for (t, v) in val["values"]]
        return boundary_conditions_data

    def get_boundary_conditions_data(self, timesteps_in_seconds=False):
        """Get boundary conditions data."""
        boundary_conditions_data = self.recalculate_boundary_conditions_timeseries(self.TYPE_1D, timesteps_in_seconds)
        boundary_conditions_data.update(
            self.recalculate_boundary_conditions_timeseries(self.TYPE_2D, timesteps_in_seconds)
        )
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

    def __init__(self, parent_page, load_conditions=False):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        set_widget_background_color(self)
        self.initial_waterlevels = {}
        self.saved_states = {}
        self.gb_1d.setChecked(False)
        self.gb_2d.setChecked(False)
        self.gb_groundwater.setChecked(False)
        self.cbo_2d_local_raster.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.cbo_gw_local_raster.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.btn_browse_2d_local_raster.clicked.connect(partial(self.browse_for_local_raster, self.cbo_2d_local_raster))
        self.btn_browse_gw_local_raster.clicked.connect(partial(self.browse_for_local_raster, self.cbo_gw_local_raster))

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
            tc = ThreediCalls(self.parent_page.parent_wizard.plugin_dock.threedi_api)
            model_id = self.parent_page.parent_wizard.model_selection_dlg.current_model.id
            initial_waterlevels = tc.fetch_3di_model_initial_waterlevels(model_id) or []
            if initial_waterlevels:
                self.rb_2d_online_raster.setChecked(True)
                self.rb_gw_online_raster.setChecked(True)
            for iw in sorted(initial_waterlevels, key=attrgetter("id")):
                if iw.dimension != "two_d":
                    continue
                raster = tc.fetch_3di_model_raster(model_id, iw.source_raster_id)
                raster_filename = raster.file.filename
                self.initial_waterlevels[raster_filename] = iw
                self.cbo_2d_online_raster.addItem(raster_filename)
                self.cbo_gw_online_raster.addItem(raster_filename)

            states = tc.fetch_3di_model_saved_states(
                self.parent_page.parent_wizard.model_selection_dlg.current_model.id
            )
            for state in states or []:
                state_name = state.name
                self.saved_states[state_name] = state
                self.cb_saved_states.addItem(state_name)
        except ApiException as e:
            error_msg = extract_error_message(e)
            self.parent_page.parent_wizard.plugin_dock.communication.bar_error(error_msg, log_text_color=QColor(Qt.red))
        except Exception as e:
            error_msg = f"Error: {e}"
            self.parent_page.parent_wizard.plugin_dock.communication.bar_error(error_msg, log_text_color=QColor(Qt.red))

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

    def __init__(self, parent_page):
        super().__init__()
        self.setupUi(self)
        self.parent_page = parent_page
        set_widget_background_color(self)
        self.laterals_timeseries = {}
        self.last_upload_filepath = ""
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
        self.last_upload_filepath = filename
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
        set_widget_background_color(self)
        self.values = dict()
        self.potential_breaches = dict()
        self.breaches_layer = parent_page.parent_wizard.model_selection_dlg.breaches_layer
        self.dd_breach_id = FilteredComboBox(self)
        self.breach_lout.addWidget(self.dd_breach_id)
        self.dd_simulation.currentIndexChanged.connect(self.simulation_changed)
        self.dd_breach_id.currentIndexChanged.connect(self.potential_breach_changed)
        self.dd_units.currentIndexChanged.connect(self.write_values_into_dict)
        self.sb_duration.valueChanged.connect(self.write_values_into_dict)
        self.sb_width.valueChanged.connect(self.write_values_into_dict)
        self.sp_start_after.valueChanged.connect(self.write_values_into_dict)
        self.sb_discharge_coefficient_positive.valueChanged.connect(self.write_values_into_dict)
        self.sb_discharge_coefficient_negative.valueChanged.connect(self.write_values_into_dict)
        self.sb_max_breach_depth.valueChanged.connect(self.write_values_into_dict)
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
            field_names = [field.name() for field in self.breaches_layer.fields()]
            if self.breaches_layer.selectedFeatureCount() > 0:
                first_id = [str(feat["content_pk"]) for feat in self.breaches_layer.selectedFeatures()][0]
            else:
                first_id = None
            breaches_ids = []
            for feat in self.breaches_layer.getFeatures():
                breach_id = str(feat["content_pk"])
                breaches_ids.append(breach_id)
                self.potential_breaches[breach_id] = {field_name: feat[field_name] for field_name in field_names}
            breaches_ids.sort(key=lambda i: int(i))
            self.dd_breach_id.addItems(breaches_ids)
            if first_id is not None:
                self.dd_breach_id.setCurrentText(first_id)
                self.set_values_from_feature()
        self.write_values_into_dict()

    def set_values_from_feature(self):
        """Set potential breach parameters to the widgets."""
        breach_id = self.dd_breach_id.currentText()
        try:
            breach_attributes = self.potential_breaches[breach_id]
            max_breach_depth = breach_attributes["levbr"]
            if max_breach_depth not in (None, NULL):
                self.sb_max_breach_depth.setValue(max_breach_depth)
        except KeyError:
            pass

    def write_values_into_dict(self):
        """Store current widget values."""
        simulation = self.dd_simulation.currentText()
        breach_id = self.dd_breach_id.currentText()
        duration = self.sb_duration.value()
        width = self.sb_width.value()
        units = self.dd_units.currentText()
        offset = self.sp_start_after.value()
        discharge_coefficient_positive = self.sb_discharge_coefficient_positive.value()
        discharge_coefficient_negative = self.sb_discharge_coefficient_negative.value()
        max_breach_depth = self.sb_max_breach_depth.value()
        self.values[simulation] = {
            "breach_id": breach_id,
            "width": width,
            "duration": duration,
            "units": units,
            "offset": offset,
            "discharge_coefficient_positive": discharge_coefficient_positive,
            "discharge_coefficient_negative": discharge_coefficient_negative,
            "max_breach_depth": max_breach_depth,
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
            self.sb_discharge_coefficient_positive.setValue(vals.get("discharge_coefficient_positive"))
            self.sb_discharge_coefficient_negative.setValue(vals.get("discharge_coefficient_negative"))
            self.sb_max_breach_depth.setValue(vals.get("max_breach_depth"))
        else:
            self.dd_breach_id.setCurrentIndex(0)
            self.sb_duration.setValue(0.1)
            self.sb_width.setValue(10)
            self.dd_units.setCurrentIndex(0)
            self.sp_start_after.setValue(0)
            self.sb_discharge_coefficient_positive.setValue(1.0)
            self.sb_discharge_coefficient_negative.setValue(1.0)
            self.sb_max_breach_depth.setValue(0)
            self.set_values_from_feature()

    def potential_breach_changed(self):
        """Handle potential breach ID change."""
        self.set_values_from_feature()
        self.write_values_into_dict()

    def get_breaches_data(self):
        """Getting all needed data for adding breaches to the simulation."""
        breach_id = self.dd_breach_id.currentText()
        width = self.sb_width.value()
        duration = self.sb_duration.value()
        units = self.dd_units.currentText()
        offset = self.sp_start_after.value()
        duration_in_units = duration * self.SECONDS_MULTIPLIERS[units]
        discharge_coefficient_positive = self.sb_discharge_coefficient_positive.value()
        discharge_coefficient_negative = self.sb_discharge_coefficient_negative.value()
        max_breach_depth = self.sb_max_breach_depth.value()
        breach_data = (
            breach_id,
            width,
            duration_in_units,
            offset,
            discharge_coefficient_positive,
            discharge_coefficient_negative,
            max_breach_depth,
        )
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
            }
        elif precipitation_type == EventTypes.CUSTOM.value:
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
            }
        elif precipitation_type == EventTypes.RADAR.value:
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
        if vals.get("precipitation_type") == EventTypes.CONSTANT.value:
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
        elif vals.get("precipitation_type") == EventTypes.CUSTOM.value:
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
        elif vals.get("precipitation_type") == EventTypes.DESIGN.value:
            self.cbo_prec_type.setCurrentIndex(self.cbo_prec_type.findText(vals.get("precipitation_type")))
            self.sp_start_after_design.setValue(vals.get("start_after"))
            self.start_after_design_u.setCurrentIndex(self.start_after_design_u.findText(vals.get("start_after_units")))
            design_number = vals.get("design_number")
            self.cbo_design.setCurrentIndex(self.cbo_design.findText(design_number))
            self.design_time_series[simulation] = vals.get("time_series", [])
        elif vals.get("precipitation_type") == EventTypes.RADAR.value:
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
        if current_text == EventTypes.CONSTANT.value:
            if self.start_after_constant_u.currentIndex != idx:
                self.start_after_constant_u.setCurrentIndex(idx)
            if self.stop_after_constant_u.currentIndex != idx:
                self.stop_after_constant_u.setCurrentIndex(idx)
            self.current_units = self.start_after_constant_u.currentText()
        elif current_text == EventTypes.CUSTOM.value:
            self.current_units = self.start_after_custom_u.currentText()
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
        elif current_text == EventTypes.CUSTOM.value:
            self.current_units = self.start_after_custom_u.currentText()
        elif current_text == EventTypes.DESIGN.value:
            self.current_units = self.start_after_design_u.currentText()
        elif current_text == EventTypes.RADAR.value:
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
        if not intervals_are_even(time_series):
            warn_message = (
                "Time steps in the selected CSV file are not even. "
                "Please adjust your data to fulfill even time steps requirement."
            )
            self.parent_page.parent_wizard.plugin_dock.communication.show_warn(warn_message)
            return
        self.le_upload_rain.setText(filename)
        self.custom_time_series[simulation] = time_series
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
        elif current_text == EventTypes.CUSTOM.value:
            start = self.sp_start_after_custom.value()
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
        elif current_text == EventTypes.CUSTOM.value:
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
        elif current_text == EventTypes.CUSTOM.value:
            ts = self.custom_time_series[simulation]
            if self.cbo_units.currentText() == "mm/h":
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
        if current_text == EventTypes.CONSTANT.value:
            x_values, y_values = self.constant_values()
        elif current_text == EventTypes.CUSTOM.value:
            x_values, y_values = self.custom_values()
        elif current_text == EventTypes.DESIGN.value:
            x_values, y_values = self.design_values()
        elif current_text == EventTypes.RADAR.value:
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
        if current_text == EventTypes.CONSTANT.value:
            precipitation_values = y_values[:-1]
        else:
            precipitation_values = y_values
        if current_text == EventTypes.CONSTANT.value:
            self.total_precipitation = sum(mmh_to_mmtimestep(v, 1, self.current_units) for v in precipitation_values)
        elif current_text == EventTypes.CUSTOM.value and self.cbo_units.currentText() == "mm/h":
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
        last_folder = QSettings().value("threedi/last_wind_folder", os.path.expanduser("~"), type=str)
        filename, __ = QFileDialog.getOpenFileName(self, "Wind Time Series", last_folder, file_filter)
        if len(filename) == 0:
            return
        QSettings().setValue("threedi/last_wind_folder", os.path.dirname(filename))
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
        elif current_text == EventTypes.CUSTOM.value:
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
        elif current_text == EventTypes.CUSTOM.value:
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
                if ptype != EventTypes.RADAR.value:
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

    STEP_NAME = "Laterals"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = LateralsWidget(self)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.registerField("laterals_upload*", self.main_widget.il_upload)
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
        if init_conditions.include_boundary_conditions:
            self.boundary_conditions_page = BoundaryConditionsPage(self)
            self.addPage(self.boundary_conditions_page)
        if init_conditions.include_structure_controls:
            self.structure_controls_page = StructureControlsPage(self)
            self.addPage(self.structure_controls_page)
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
            self.precipitation_page.main_widget.plot_precipitation()
        elif isinstance(current_page, SummaryPage):
            self.set_overview_name()
            self.set_overview_database()
            self.set_overview_duration()
            if self.init_conditions.include_precipitations:
                self.summary_page.main_widget.plot_overview_precipitation()
                self.set_overview_precipitation()
            if self.init_conditions.include_breaches:
                self.set_overview_breaches()
        elif isinstance(current_page, LateralsPage):
            laterals_widget = self.laterals_page.main_widget
            laterals_widget.il_upload.setText(laterals_widget.last_upload_filepath)
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
        from_template_placeholder = "<FROM TEMPLATE>"
        name_params = {"le_sim_name": simulation.name, "le_tags": ", ".join(simulation.tags)}
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
        if init_conditions.include_boundary_conditions:
            temp_file_bc = events.fileboundaryconditions if events.fileboundaryconditions else None
            self.boundary_conditions_page.main_widget.set_template_boundary_conditions(temp_file_bc)
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
            laterals_events = [filelateral for filelateral in events.filelaterals if filelateral.periodic != "daily"]
            if laterals_events:
                laterals_widget = self.laterals_page.main_widget
                tc = ThreediCalls(self.plugin_dock.threedi_api)
                lateral_file = laterals_events[0]
                lateral_file_name = lateral_file.file.filename
                lateral_file_download = tc.fetch_lateral_file_download(temp_simulation_id, lateral_file.id)
                lateral_temp_filepath = os.path.join(TEMPDIR, lateral_file_name)
                get_download_file(lateral_file_download, lateral_temp_filepath)
                laterals_timeseries = read_json_data(lateral_temp_filepath)
                last_lateral = laterals_timeseries[-1]
                if "point" in last_lateral:
                    laterals_widget.cb_type.setCurrentText("2D")
                else:
                    laterals_widget.cb_type.setCurrentText("1D")
                laterals_widget.il_upload.setText(from_template_placeholder)
                laterals_widget.last_upload_filepath = from_template_placeholder
                laterals_widget.cbo_lateral_units.setCurrentText("s")
                laterals_widget.cb_interpolate_laterals.setChecked(last_lateral["interpolate"])
                try:
                    laterals_widget.laterals_timeseries = {str(lat["id"]): lat for lat in laterals_timeseries}
                except KeyError:
                    laterals_widget.laterals_timeseries = {str(i): lat for i, lat in enumerate(laterals_timeseries, 1)}
                laterals_widget.last_uploaded_laterals = laterals_timeseries[-1]
                for lat_id in laterals_widget.laterals_timeseries.keys():
                    laterals_widget.cb_laterals.addItem(lat_id)
                os.remove(lateral_temp_filepath)
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
                breaches_widget.sb_discharge_coefficient_positive.setValue(breach.discharge_coefficient_positive or 1)
                breaches_widget.sb_discharge_coefficient_negative.setValue(breach.discharge_coefficient_negative or 1)
                breaches_widget.sb_max_breach_depth.setValue(breach.maximum_breach_depth)
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
                    precipitation_widget.le_upload_rain.setText(from_template_placeholder)
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
            wind_widget = self.wind_page.main_widget
            if events.wind:
                wind = events.wind[0]
                initial_winddragcoefficient = events.initial_winddragcoefficient
                if wind.speed_constant and wind.direction_constant:
                    wind_widget.cbo_wind_type.setCurrentText("Constant")
                    wind_widget.sp_start_wind_constant.setValue(wind.offset // 3600)
                    wind_widget.cbo_windspeed_u.setCurrentText(wind.units)
                    timestep, speed, direction = wind.values[0]
                    wind_widget.sp_windspeed.setValue(speed)
                    wind_widget.sp_direction.setValue(direction)
                    if initial_winddragcoefficient:
                        wind_widget.sp_dc_constant.setValue(initial_winddragcoefficient.value)
                else:
                    wind_widget.cbo_wind_type.setCurrentText("Custom")
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

    def run_new_simulation(self):
        """Getting data from the wizard and running new simulation."""
        self.settings.setValue("threedi/wizard_size", self.size())
        events = self.init_conditions_dlg.events
        name = self.name_page.main_widget.le_sim_name.text()
        tags = self.name_page.main_widget.le_tags.text()
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
            initial_conditions.saved_state = self.init_conditions_page.main_widget.saved_states.get(
                self.init_conditions_page.main_widget.cb_saved_states.currentText()
            )

        # Laterals
        if self.init_conditions.include_laterals:
            laterals_data = self.laterals_page.main_widget.get_laterals_data(timesteps_in_seconds=True)
            laterals = dm.Laterals(laterals_data)
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

        # Settings page attributes
        main_settings = self.settings_page.main_widget.collect_single_settings()
        physical_settings, numerical_settings, time_step_settings = main_settings
        aggregation_settings_list = self.settings_page.main_widget.collect_aggregation_settings()
        settings = dm.Settings(physical_settings, numerical_settings, time_step_settings, aggregation_settings_list)
        # Post-processing in Lizard
        lizard_post_processing = dm.LizardPostProcessing()
        if self.init_conditions.include_lizard_post_processing:
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
        simulation_template = self.init_conditions_dlg.simulation_template
        sim_temp_id = simulation_template.simulation.id
        simulation_difference = self.init_conditions.simulations_difference
        for i, simulation in enumerate(self.init_conditions.simulations_list, start=1):
            sim_name = f"{name}_{i}" if self.init_conditions.multiple_simulations is True else name
            new_simulation = dm.NewSimulation(
                sim_temp_id, sim_name, tags, threedimodel_id, organisation_uuid, start_datetime, end_datetime, duration
            )
            new_simulation.init_options = init_options
            new_simulation.boundary_conditions = boundary_conditions
            new_simulation.structure_controls = structure_controls
            new_simulation.initial_conditions = initial_conditions
            new_simulation.laterals = laterals
            new_simulation.dwf = dwf
            if self.init_conditions.include_breaches:
                self.breaches_page.main_widget.dd_simulation.setCurrentText(simulation)
                breach_data = self.breaches_page.main_widget.get_breaches_data()
                if simulation_difference == "breaches" or i == 1:
                    new_simulation.breach = dm.Breach(*breach_data)
                else:
                    new_simulation.breach = dm.Breach()
            if self.init_conditions.include_precipitations:
                self.precipitation_page.main_widget.dd_simulation.setCurrentText(simulation)
                precipitation_data = self.precipitation_page.main_widget.get_precipitation_data()
                if simulation_difference == "precipitation" or i == 1:
                    new_simulation.precipitation = dm.Precipitation(*precipitation_data)
                else:
                    new_simulation.precipitation = dm.Precipitation()
            new_simulation.wind = wind
            new_simulation.settings = settings
            new_simulation.lizard_post_processing = lizard_post_processing
            self.new_simulations.append(new_simulation)

    def cancel_wizard(self):
        """Handling canceling wizard action."""
        self.settings.setValue("threedi/wizard_size", self.size())
        self.reject()
