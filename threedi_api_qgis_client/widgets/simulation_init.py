import os
from qgis.PyQt import uic

base_dir = os.path.dirname(os.path.dirname(__file__))
uicls, basecls = uic.loadUiType(os.path.join(base_dir, 'ui', 'init_dialog.ui'))


class SimulationInit(uicls, basecls):
    """Dialog with methods for handling running simulations."""
    PROGRESS_COLUMN_IDX = 2
    COST_TYPES = ["min", "avg", "max"]
    MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

    def __init__(self, parent_dock, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.parent_dock = parent_dock

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
        self.pb_next.clicked.connect(self.start_wizard)
        self.pb_cancel.clicked.connect(self.close)
        self.fill_comboboxes()

    def fill_comboboxes(self):
        self.dd_cost_type.addItems(self.COST_TYPES)
        self.dd_flood_month.addItems(self.MONTHS)
        self.dd_number_of_simulation.addItems([str(i) for i in range(2, 10)])
        self.dd_simulation_difference.addItems(["precipitation", "breaches"])

    def multiple_simulations_changed(self, i):
        if i:
            self.multiple_simulations_widget.show()
        else:
            self.multiple_simulations_widget.hide()

    def load_saved_state_changed(self, i):
        if i:
            self.load_state_widget.show()
        else:
            self.load_state_widget.hide()

    def postprocessing_state_changed(self, i):
        if i:
            self.postprocessing_widget.show()
            self.cb_basec_results.setChecked(True)
        else:
            self.postprocessing_widget.hide()
            self.cb_basec_results.setChecked(False)

    def damage_estimation_changed(self, i):
        if i:
            self.damage_estimation_widget.show()
        else:
            self.damage_estimation_widget.hide()

    def start_wizard(self):
        self.initial_conditions = SimulationInitObject()
        self.initial_conditions.include_boundary_conditions = self.cb_boundary.isChecked()
        self.initial_conditions.include_initial_conditions = self.cb_conditions.isChecked()
        self.initial_conditions.load_from_saved_state = self.cb_load_saved_state.isChecked()
        self.initial_conditions.include_laterals = self.cb_laterals.isChecked()
        self.initial_conditions.include_breaches = self.cb_breanches.isChecked()
        self.initial_conditions.include_precipitations = self.cb_precipitation.isChecked()
        self.initial_conditions.multiple_simulations = self.cb_multiple_simulations.isChecked()
        if self.initial_conditions.multiple_simulations:
            self.initial_conditions.number_of_simulations = int(self.dd_number_of_simulation.currentText())
        self.initial_conditions.simulations_difference = self.dd_simulation_difference.currentText()

        self.initial_conditions.generate_saved_state = self.cb_generate.isChecked()
        self.initial_conditions.postprocessing = self.cb_postprocess.isChecked()
        self.initial_conditions.basic_processed_results = self.cb_basec_results.isChecked()
        self.initial_conditions.arrival_time_map = self.cb_arrival_time_map.isChecked()
        self.initial_conditions.damage_estimation = self.cb_damage_estimation.isChecked()
        self.initial_conditions.cost_type = self.dd_cost_type.currentText()
        self.initial_conditions.flood_month = self.dd_flood_month.currentText()
        self.initial_conditions.period = self.sb_period.value()
        self.initial_conditions.repair_time_infrastructure = self.sb_repair_infrastructure.value()
        self.initial_conditions.repair_time_buildings = self.sb_repair_building.value()
        self.open_wizard = True
        self.close()


class SimulationInitObject:
    def __init__(self):
        self.include_boundary_conditions = False
        self.include_initial_conditions = False
        self.load_from_saved_state = False
        self.include_laterals = False
        self.include_breaches = False
        self.include_precipitations = False
        self.multiple_simulations = False
        self.number_of_simulations = 1
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
