# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
from dataclasses import dataclass
from datetime import datetime
from threedi_api_client.openapi import (
    Simulation,
    InitialWaterlevel,
    FileStructureControl,
    MemoryStructureControl,
    TableStructureControl,
    TimedStructureControl,
    FileBoundaryCondition,
)


@dataclass
class SimulationElement:
    def __bool__(self):
        for field in self.__dataclass_fields__:
            field_value = getattr(self, field)
            if field_value is not None:
                return True
        return False


@dataclass
class DamageEstimation(SimulationElement):
    cost_type: str = None
    flood_month: str = None
    inundation_period: float = None
    repair_time_infrastructure: int = None
    repair_time_buildings: int = None


@dataclass
class InitOptions(SimulationElement):
    boundary_conditions_file: FileBoundaryCondition = None
    basic_processed_results: bool = None
    arrival_time_map: bool = None
    damage_estimation: DamageEstimation = None
    generate_saved_state: bool = None


@dataclass
class StructureControls(SimulationElement):
    file_structure_controls: FileStructureControl = None
    memory_structure_controls: MemoryStructureControl = None
    table_structure_controls: TableStructureControl = None
    timed_structure_controls: TimedStructureControl = None
    local_file_structure_controls: str = None


@dataclass
class InitialConditions(SimulationElement):
    global_value_1d: float = None
    from_spatialite_1d: bool = None
    global_value_2d: float = None
    online_raster_2d: InitialWaterlevel = None
    local_raster_2d: str = None
    aggregation_method_2d: str = None
    global_value_groundwater: str = None
    online_raster_groundwater: InitialWaterlevel = None
    local_raster_groundwater: str = None
    aggregation_method_groundwater: str = None
    saved_state: str = None


@dataclass
class Laterals(SimulationElement):
    data: dict = None


@dataclass
class DWF(SimulationElement):
    data: dict = None


@dataclass
class Breach(SimulationElement):
    breach_id: str = None
    width: float = None
    duration_in_units: float = None
    offset: float = None
    discharge_coefficient_positive: float = None
    discharge_coefficient_negative: float = None
    max_breach_depth: float = None


@dataclass
class Precipitation(SimulationElement):
    precipitation_type: str = None
    offset: float = None
    duration: int = None
    units: str = None
    values: list = None
    start: datetime = None
    interpolate: bool = None
    filepath: str = None
    from_csv: bool = None
    from_netcdf: bool = None


@dataclass
class Wind(SimulationElement):
    wind_type: str = None
    offset: float = None
    duration: int = None
    speed: int = None
    direction: int = None
    units: str = None
    drag_coefficient: float = None
    interpolate_speed: bool = None
    interpolate_direction: bool = None
    values: list = None


@dataclass
class Settings(SimulationElement):
    physical_settings: dict = None
    numerical_settings: dict = None
    time_step_settings: dict = None
    aggregation_settings_list: list = None


@dataclass
class NewSimulation:
    simulation_template_id: str
    name: str
    tags: str
    threedimodel_id: str
    organisation_uuid: str
    start_datetime: datetime
    end_datetime: datetime
    duration: float
    init_options: InitOptions = None
    structure_controls: StructureControls = None
    initial_conditions: InitialConditions = None
    laterals: Laterals = None
    dwf: DWF = None
    breach: Breach = None
    precipitation: Precipitation = None
    wind: Wind = None
    settings: Settings = None
    template_name: str = None
    # Last two attributes will be added after new simulation initialization
    simulation: Simulation = None
    initial_status: str = None
