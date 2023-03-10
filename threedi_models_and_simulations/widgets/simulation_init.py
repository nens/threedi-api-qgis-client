# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import os

from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "simulation_wizard", "init_dialog.ui"))


class SimulationInit(uicls, basecls):
    """Dialog with methods for handling running simulations."""

    PROGRESS_COLUMN_IDX = 2

    def __init__(self, current_model, simulation_template, settings_overview, events, parent):
        super().__init__(parent)
        self.setupUi(self)
        self.current_model = current_model
        self.simulation_template = simulation_template
        self.settings_overview = settings_overview
        self.events = events
        self.open_wizard = False
        self.initial_conditions = None
        self.multiple_simulations_widget.setVisible(False)
        self.load_state_widget.setVisible(False)
        self.cb_multiple_simulations.stateChanged.connect(self.multiple_simulations_changed)
        self.cb_conditions.stateChanged.connect(self.load_saved_state_changed)
        self.cb_breaches.stateChanged.connect(self.toggle_breaches)
        self.cb_precipitation.stateChanged.connect(self.toggle_precipitation)
        self.pb_next.clicked.connect(self.start_wizard)
        self.pb_cancel.clicked.connect(self.close)
        self.setup_initial_options()
        self.check_template_events()

    def setup_initial_options(self):
        """Setup initial options dialog."""
        self.dd_number_of_simulation.addItems([str(i) for i in range(2, 10)])
        self.cb_boundary.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.cb_boundary.setFocusPolicy(Qt.NoFocus)

    def check_template_events(self):
        """Check events that are available for the simulation template."""
        # Check raster edits
        if self.events.rasteredits:
            self.cb_raster_edits.setChecked(True)
        else:
            self.cb_raster_edits.setDisabled(True)
        # Check leakage
        leakage_events = []  # TODO: add "leakage", "filetimeseriesleakage", "filerasterleakage"
        if any(getattr(self.events, event_name) for event_name in leakage_events):
            self.cb_leakage.setChecked(True)
        else:
            self.cb_leakage.setDisabled(True)
        # Check sources and sinks
        sources_sinks_events = [
            "lizardrastersourcessinks",
            "lizardtimeseriessourcessinks",
            "timeseriessourcessinks",
        ]  # TODO: add "filerastersourcessinks", "filetimeseriessourcessinks"
        if any(getattr(self.events, event_name) for event_name in sources_sinks_events):
            self.cb_sources_sinks.setChecked(True)
        else:
            self.cb_sources_sinks.setDisabled(True)
        # Check local/timeseries rain
        local_ts_rain_events = ["lizardtimeseriesrain", "localrain"]  # TODO: add "filetimeseriesrain"
        if any(getattr(self.events, event_name) for event_name in local_ts_rain_events):
            self.cb_local_or_ts_rain.setChecked(True)
        else:
            self.cb_local_or_ts_rain.setDisabled(True)
        # Check obstacle edits
        if self.events.obstacleedits:
            self.cb_obstacle_edits.setChecked(True)
        else:
            self.cb_obstacle_edits.setDisabled(True)
        # Check boundary conditions
        if self.events.fileboundaryconditions:
            self.cb_boundary.setChecked(True)
        else:
            self.cb_boundary.setDisabled(True)
        # Check structure controls
        if self.current_model.extent_one_d is None:
            self.cb_structure_controls.setDisabled(True)
        if any(
            (
                self.events.filestructurecontrols,
                self.events.memorystructurecontrols,
                self.events.tablestructurecontrols,
                self.events.timedstructurecontrols,
            )
        ):
            self.cb_structure_controls.setChecked(True)
        # Check initial conditions
        initial_events = [
            "initial_onedwaterlevel",
            "initial_onedwaterlevelpredefined",
            "initial_onedwaterlevelfile",
            "initial_twodwaterlevel",
            "initial_twodwaterraster",
            "initial_groundwaterlevel",
            "initial_groundwaterraster",
            "initial_savedstate",
        ]
        if any(getattr(self.events, event_name) for event_name in initial_events):
            self.cb_conditions.setChecked(True)
            if self.events.initial_savedstate:
                self.cb_load_saved_state.setEnabled(True)
                self.cb_load_saved_state.setChecked(True)
        # Check laterals and DWF
        if self.current_model.extent_one_d is None:
            self.cb_dwf.setDisabled(True)
        if self.events.filelaterals:
            filelaterals = self.events.filelaterals
            laterals_events = [filelateral for filelateral in filelaterals if filelateral.periodic != "daily"]
            dwf_events = [filelateral for filelateral in filelaterals if filelateral.periodic == "daily"]
            if laterals_events:
                self.cb_laterals.setChecked(True)
            if dwf_events:
                self.cb_dwf.setChecked(True)
        # Check breaches
        if int(self.current_model.breach_count or 0) == 0:
            self.cb_breaches.setDisabled(True)
        if self.events.breach:
            self.cb_breaches.setChecked(True)
        # Check precipitation
        rain_events = ["lizardrasterrain", "timeseriesrain", "filerasterrain"]
        if any(getattr(self.events, rain_event_name) for rain_event_name in rain_events):
            self.cb_precipitation.setChecked(True)
        # Check wind
        if self.events.initial_winddragcoefficient or self.events.wind:
            self.cb_wind.setChecked(True)

    def toggle_breaches(self):
        """Handle breaches checkboxes state changes."""
        if self.cb_breaches.isChecked():
            self.dd_simulation_difference.addItem("breaches")
            self.cb_multiple_simulations.setEnabled(True)
        else:
            idx = self.dd_simulation_difference.findText("breaches")
            self.dd_simulation_difference.removeItem(idx)
            if not self.cb_precipitation.isChecked():
                self.cb_multiple_simulations.setChecked(False)
                self.cb_multiple_simulations.setDisabled(True)

    def toggle_precipitation(self):
        """Handle precipitation checkboxes state changes."""
        if self.cb_precipitation.isChecked():
            self.dd_simulation_difference.addItem("precipitation")
            self.cb_multiple_simulations.setEnabled(True)
        else:
            idx = self.dd_simulation_difference.findText("precipitation")
            self.dd_simulation_difference.removeItem(idx)
            if not self.cb_breaches.isChecked():
                self.cb_multiple_simulations.setChecked(False)
                self.cb_multiple_simulations.setDisabled(True)

    def multiple_simulations_changed(self, i):
        """Handle multiple simulations checkboxes state changes."""
        if i:
            self.multiple_simulations_widget.show()
        else:
            self.multiple_simulations_widget.hide()

    def load_saved_state_changed(self, i):
        """Handle saved states checkboxes state changes."""
        if i:
            self.load_state_widget.show()
        else:
            self.load_state_widget.hide()

    def start_wizard(self):
        """Start new simulation wizard based on selected options."""
        self.initial_conditions = SimulationInitObject()
        self.initial_conditions.include_boundary_conditions = self.cb_boundary.isChecked()
        self.initial_conditions.include_structure_controls = self.cb_structure_controls.isChecked()
        self.initial_conditions.include_initial_conditions = self.cb_conditions.isChecked()
        self.initial_conditions.load_from_saved_state = self.cb_load_saved_state.isChecked()
        self.initial_conditions.include_laterals = self.cb_laterals.isChecked()
        self.initial_conditions.include_dwf = self.cb_dwf.isChecked()
        self.initial_conditions.include_breaches = self.cb_breaches.isChecked()
        self.initial_conditions.include_precipitations = self.cb_precipitation.isChecked()
        self.initial_conditions.include_wind = self.cb_wind.isChecked()
        self.initial_conditions.include_lizard_post_processing = self.cb_postprocess.isChecked()
        self.initial_conditions.multiple_simulations = self.cb_multiple_simulations.isChecked()
        if self.initial_conditions.multiple_simulations:
            self.initial_conditions.number_of_simulations = int(self.dd_number_of_simulation.currentText())
        nos = self.initial_conditions.number_of_simulations + 1
        self.initial_conditions.simulations_list = [f"Simulation{i}" for i in range(1, nos)]
        self.initial_conditions.simulations_difference = self.dd_simulation_difference.currentText()
        self.initial_conditions.generate_saved_state = self.cb_generate.isChecked()
        self.initial_conditions.include_raster_edits = self.cb_raster_edits.isChecked()
        self.initial_conditions.include_leakage = self.cb_leakage.isChecked()
        self.initial_conditions.include_sources_sinks = self.cb_sources_sinks.isChecked()
        self.initial_conditions.include_local_ts_rain = self.cb_local_or_ts_rain.isChecked()
        self.initial_conditions.include_obstacle_edits = self.cb_obstacle_edits.isChecked()
        self.open_wizard = True
        self.close()


class SimulationInitObject:
    """Object for storing init options."""

    def __init__(self):
        self.include_boundary_conditions = False
        self.include_structure_controls = False
        self.include_initial_conditions = False
        self.load_from_saved_state = False
        self.include_laterals = False
        self.include_dwf = False
        self.include_breaches = False
        self.include_precipitations = False
        self.include_wind = False
        self.include_lizard_post_processing = False
        self.multiple_simulations = False
        self.number_of_simulations = 1
        self.simulations_list = []
        self.simulations_difference = None
        self.generate_saved_state = False
        self.include_raster_edits = False
        self.include_leakage = False
        self.include_sources_sinks = False
        self.include_local_ts_rain = False
        self.include_obstacle_edits = False
