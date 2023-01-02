# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2022 by Lutra Consulting for 3Di Water Management
import os
from collections import OrderedDict
from qgis.PyQt import uic

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, "ui", "simulation_wizard", "init_dialog.ui"))


class SimulationInit(uicls, basecls):
    """Dialog with methods for handling running simulations."""

    PROGRESS_COLUMN_IDX = 2
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
            ("0 hours", 0),
            ("6 hours", 6),
            ("1 day", 24),
            ("2 days", 48),
            ("5 days", 120),
            ("10 days", 240),
        )
    )

    def __init__(self, simulation_template, settings_overview, events, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.simulation_template = simulation_template
        self.settings_overview = settings_overview
        self.events = events
        self.open_wizard = False
        self.initial_conditions = None
        self.multiple_simulations_widget.setVisible(False)
        self.load_state_widget.setVisible(False)
        self.damage_estimation_widget.setVisible(False)
        self.postprocessing_widget.setVisible(False)
        self.cb_multiple_simulations.stateChanged.connect(self.multiple_simulations_changed)
        self.cb_conditions.stateChanged.connect(self.load_saved_state_changed)
        self.cb_postprocess.stateChanged.connect(self.postprocessing_state_changed)
        self.cb_damage_estimation.stateChanged.connect(self.damage_estimation_changed)
        self.cb_breaches.stateChanged.connect(self.toggle_breaches)
        self.cb_precipitation.stateChanged.connect(self.toggle_precipitation)
        self.pb_next.clicked.connect(self.start_wizard)
        self.pb_cancel.clicked.connect(self.close)
        self.setup_initial_options()
        self.check_template_events()

    def setup_initial_options(self):
        """Setup initial options dialog."""
        self.dd_cost_type.addItems(self.COST_TYPES)
        self.dd_cost_type.setCurrentText("avg")
        self.dd_flood_month.addItems(list(self.MONTHS.keys()))
        self.dd_flood_month.setCurrentText("september")
        self.dd_repair_infrastructure.addItems(list(self.REPAIR_TIME.keys()))
        self.dd_repair_building.addItems(list(self.REPAIR_TIME.keys()))
        self.dd_number_of_simulation.addItems([str(i) for i in range(2, 10)])

    def check_template_events(self):
        """Check events that are available for the simulation template."""
        if any(
            (
                self.events.filestructurecontrols,
                self.events.memorystructurecontrols,
                self.events.tablestructurecontrols,
                self.events.timedstructurecontrols,
            )
        ):
            self.cb_structure_controls.setChecked(True)
        if self.events.fileboundaryconditions:
            self.cb_boundary.setChecked(True)
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
                self.cb_load_saved_state.setChecked(True)
        if self.events.filelaterals:
            filelaterals = self.events.filelaterals
            laterals_events = [filelateral for filelateral in filelaterals if filelateral.periodic != "daily"]
            dwf_events = [filelateral for filelateral in filelaterals if filelateral.periodic == "daily"]
            if laterals_events:
                self.cb_laterals.setChecked(True)
            if dwf_events:
                self.cb_dwf.setChecked(True)
        if self.events.breach:
            self.cb_breaches.setChecked(True)
        rain_events = [
            "lizardrasterrain",
            "lizardtimeseriesrain",
            "localrain",
            "timeseriesrain",
            "filerasterrain",
            "filetimeseriesrain",
        ]
        if any(getattr(self.events, rain_event_name) for rain_event_name in rain_events):
            self.cb_precipitation.setChecked(True)
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

    def postprocessing_state_changed(self, i):
        """Handle postprocessing checkboxes state changes."""
        if i:
            self.postprocessing_widget.show()
            self.cb_basec_results.setChecked(True)
        else:
            self.postprocessing_widget.hide()
            self.cb_basec_results.setChecked(False)

    def damage_estimation_changed(self, i):
        """Handle damage estimation checkboxes state changes."""
        if i:
            self.damage_estimation_widget.show()
        else:
            self.damage_estimation_widget.hide()

    def start_wizard(self):
        """Start new simulation wizard based on selected options."""
        self.initial_conditions = SimulationInitObject()
        self.initial_conditions.include_structure_controls = self.cb_structure_controls.isChecked()
        self.initial_conditions.include_boundary_conditions = self.cb_boundary.isChecked()
        self.initial_conditions.include_initial_conditions = self.cb_conditions.isChecked()
        self.initial_conditions.load_from_saved_state = self.cb_load_saved_state.isChecked()
        self.initial_conditions.include_laterals = self.cb_laterals.isChecked()
        self.initial_conditions.include_dwf = self.cb_dwf.isChecked()
        self.initial_conditions.include_breaches = self.cb_breaches.isChecked()
        self.initial_conditions.include_precipitations = self.cb_precipitation.isChecked()
        self.initial_conditions.include_wind = self.cb_wind.isChecked()
        self.initial_conditions.multiple_simulations = self.cb_multiple_simulations.isChecked()
        if self.initial_conditions.multiple_simulations:
            self.initial_conditions.number_of_simulations = int(self.dd_number_of_simulation.currentText())
        nos = self.initial_conditions.number_of_simulations + 1
        self.initial_conditions.simulations_list = [f"Simulation{i}" for i in range(1, nos)]
        self.initial_conditions.simulations_difference = self.dd_simulation_difference.currentText()
        self.initial_conditions.generate_saved_state = self.cb_generate.isChecked()
        self.initial_conditions.postprocessing = self.cb_postprocess.isChecked()
        self.initial_conditions.basic_processed_results = self.cb_basec_results.isChecked()
        self.initial_conditions.arrival_time_map = self.cb_arrival_time_map.isChecked()
        self.initial_conditions.damage_estimation = self.cb_damage_estimation.isChecked()
        self.initial_conditions.cost_type = self.dd_cost_type.currentText()
        self.initial_conditions.flood_month = self.MONTHS[self.dd_flood_month.currentText()]
        self.initial_conditions.period = self.sb_period.value()
        self.initial_conditions.repair_time_infrastructure = self.REPAIR_TIME[
            self.dd_repair_infrastructure.currentText()
        ]
        self.initial_conditions.repair_time_buildings = self.REPAIR_TIME[self.dd_repair_building.currentText()]
        self.open_wizard = True
        self.close()


class SimulationInitObject:
    """Object for storing init options."""

    def __init__(self):
        self.include_structure_controls = False
        self.include_boundary_conditions = False
        self.include_initial_conditions = False
        self.load_from_saved_state = False
        self.include_laterals = False
        self.include_dwf = False
        self.include_breaches = False
        self.include_precipitations = False
        self.include_wind = False
        self.multiple_simulations = False
        self.number_of_simulations = 1
        self.simulations_list = []
        self.simulations_difference = None

        self.generate_saved_state = False
        self.postprocessing = False
        self.basic_processed_results = False
        self.arrival_time_map = False
        self.damage_estimation = False
        self.cost_type = None
        self.flood_month = None
        self.period = None
        self.repair_time_infrastructure = None
        self.repair_time_buildings = None
