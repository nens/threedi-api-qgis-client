# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2022 by Lutra Consulting for 3Di Water Management
from dataclasses import dataclass
from datetime import datetime
from threedi_api_client.openapi import (
    Simulation,
    InitialWaterlevel,
    FileStructureControl,
    FileBoundaryCondition,
)


@dataclass
class DamageEstimation:
    cost_type: str
    flood_month: str
    inundation_period: float
    repair_time_infrastructure: int
    repair_time_buildings: int


@dataclass
class InitOptions:
    filestructure_controls_file: FileStructureControl = None
    boundary_conditions_file: FileBoundaryCondition = None
    basic_processed_results: bool = False
    arrival_time_map: bool = False
    damage_estimation: DamageEstimation = None
    generate_saved_state: bool = False


@dataclass
class InitialConditions:
    # 1D
    global_value_1d: float = None
    from_spatialite_1d: bool = False
    # 2D
    global_value_2d: float = None
    online_raster_2d: InitialWaterlevel = None
    local_raster_2d: str = None
    aggregation_method_2d: str = None
    # Groundwater
    global_value_groundwater: str = None
    online_raster_groundwater: InitialWaterlevel = None
    local_raster_groundwater: str = None
    aggregation_method_groundwater: str = None
    # Saved state
    saved_state: str = None


@dataclass
class Laterals:
    data: dict


@dataclass
class DWF:
    data: dict


@dataclass
class Breach:
    breach_id: str = None
    width: float = None
    duration_in_units: float = None
    offset: float = None
    discharge_coefficient_positive: float = None
    discharge_coefficient_negative: float = None
    max_breach_depth: float = None


@dataclass
class Precipitation:
    precipitation_type: str = None
    offset: float = None
    duration: int = None
    units: str = None
    values: list = None
    start: datetime = None
    end: datetime = None
    interpolate: bool = None
    filepath: str = None
    from_csv: bool = None
    from_netcdf: bool = None


@dataclass
class Wind:
    wind_type: str
    offset: float
    duration: int
    speed: int
    direction: int
    units: str
    drag_coefficient: float
    interpolate_speed: bool
    interpolate_direction: bool
    values: list


@dataclass
class Settings:
    physical_settings: dict
    numerical_settings: dict
    time_step_settings: dict
    aggregation_settings_list: list


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
