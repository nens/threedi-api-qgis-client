from sqlalchemy import Boolean, Column, Float, Integer, String, Text
from sqlalchemy.orm import declarative_base

from . import constants
from .custom_types import CSVTable, CSVText, Geometry, IntegerEnum, VarcharEnum

Base = declarative_base()  # automap_base()


class Lateral2D(Base):
    __tablename__ = "lateral_2d"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(Text)
    display_name = Column(Text)
    type = Column(IntegerEnum(constants.Later2dType))
    timeseries = Column(CSVText)
    time_units = Column(Text)
    interpolate = Column(Boolean)
    offset = Column(Integer)
    units = Column(Text)
    tags = Column(CSVText)
    geom = Column(Geometry("POINT"), nullable=False)


class BoundaryConditions2D(Base):
    __tablename__ = "boundary_condition_2d"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(Text)
    display_name = Column(Text)
    type = Column(IntegerEnum(constants.BoundaryType))
    timeseries = Column(CSVText)
    time_units = Column(Text)
    interpolate = Column(Boolean)
    tags = Column(CSVText)
    geom = Column(Geometry("LINESTRING"), nullable=False)


class MeasureLocation(Base):
    __tablename__ = "measure_location"
    id = Column(Integer, primary_key=True, autoincrement=True)
    connection_node_id = Column(Integer)
    measure_variable = Column(VarcharEnum(constants.MeasureVariables))
    display_name = Column(Text)
    code = Column(Text)
    geom = Column(Geometry("POINT"), nullable=False)
    tags = Column(CSVText)


class MeasureMap(Base):
    __tablename__ = "measure_map"
    id = Column(Integer, primary_key=True, autoincrement=True)
    measure_location_id = Column(Integer)
    control_type = Column(VarcharEnum(constants.ControlType), nullable=False)
    control_id = Column(Integer)
    weight = Column(Float)
    display_name = Column(Text)
    code = Column(Text)
    geom = Column(Geometry("LINESTRING"), nullable=False)
    tags = Column(CSVText)


class MemoryControl(Base):
    __tablename__ = "memory_control"
    id = Column(Integer, primary_key=True, autoincrement=True)
    upper_threshold = Column(Float)
    lower_threshold = Column(Float)
    action_type = Column(VarcharEnum(constants.TableControlActionTypes))
    action_value_1 = Column(Float)
    action_value_2 = Column(Float)
    target_type = Column(VarcharEnum(constants.StructureControlTypes))
    target_id = Column(Integer)
    is_active = Column(Boolean)
    is_inverse = Column(Boolean)
    display_name = Column(Text)
    code = Column(Text)
    geom = Column(Geometry("POINT"), nullable=False)
    tags = Column(CSVText)


class TableControl(Base):
    __tablename__ = "table_control"
    id = Column(Integer, primary_key=True, autoincrement=True)
    action_table = Column(CSVTable)
    action_type = Column(VarcharEnum(constants.TableControlActionTypes))
    measure_operator = Column(VarcharEnum(constants.MeasureOperators))
    target_type = Column(VarcharEnum(constants.StructureControlTypes))
    target_id = Column(Integer, nullable=False)
    display_name = Column(Text)
    code = Column(Text)
    geom = Column(Geometry("POINT"), nullable=False)
    tags = Column(CSVText)


class Interflow(Base):
    __tablename__ = "interflow"
    id = Column(Integer, primary_key=True, autoincrement=True)
    interflow_type = Column(IntegerEnum(constants.InterflowType))
    porosity = Column(Float)
    porosity_file = Column(String(255))
    porosity_layer_thickness = Column(Float)
    impervious_layer_elevation = Column(Float)
    hydraulic_conductivity = Column(Float)
    hydraulic_conductivity_file = Column(String(255))


class SimpleInfiltration(Base):
    __tablename__ = "simple_infiltration"
    id = Column(Integer, primary_key=True, autoincrement=True)
    infiltration_rate = Column(Float)
    infiltration_rate_file = Column(String(255))
    infiltration_surface_option = Column(
        IntegerEnum(constants.InfiltrationSurfaceOption)
    )
    max_infiltration_volume = Column(Float)
    max_infiltration_volume_file = Column(Text)

    # Alias needed for API compatibility
    @property
    def max_infiltration_capacity_file(self):
        return self.max_infiltration_volume_file


class SurfaceParameters(Base):
    __tablename__ = "surface_parameters"
    id = Column(Integer, primary_key=True, autoincrement=True)
    outflow_delay = Column(Float, nullable=False)
    surface_layer_thickness = Column(Float, nullable=False)
    infiltration = Column(Boolean, nullable=False)
    max_infiltration_capacity = Column(Float, nullable=False)
    min_infiltration_capacity = Column(Float, nullable=False)
    infiltration_decay_constant = Column(Float, nullable=False)
    infiltration_recovery_constant = Column(Float, nullable=False)
    tags = Column(CSVText)
    description = Column(Text)


class Surface(Base):
    __tablename__ = "surface"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(100))
    display_name = Column(String(255))
    area = Column(Float)
    surface_parameters_id = Column(Integer)
    geom = Column(
        Geometry("POLYGON"),
        nullable=True,
    )
    tags = Column(CSVText)


class DryWeatherFlow(Base):
    __tablename__ = "dry_weather_flow"
    id = Column(Integer, primary_key=True, autoincrement=True)
    multiplier = Column(Float)
    dry_weather_flow_distribution_id = Column(Integer)
    daily_total = Column(Float)
    interpolate = Column(Boolean)
    display_name = Column(String(255))
    code = Column(String(100))
    geom = Column(
        Geometry("POLYGON"),
        nullable=False,
    )
    tags = Column(CSVText)


class DryWeatherFlowMap(Base):
    __tablename__ = "dry_weather_flow_map"
    id = Column(Integer, primary_key=True, autoincrement=True)
    connection_node_id = Column(Integer)
    dry_weather_flow_id = Column(Integer)
    display_name = Column(String(255))
    code = Column(String(100))
    geom = Column(
        Geometry("LINESTRING"),
        nullable=False,
    )
    percentage = Column(Float)
    tags = Column(CSVText)


class DryWeatherFlowDistribution(Base):
    __tablename__ = "dry_weather_flow_distribution"
    id = Column(Integer, primary_key=True, autoincrement=True)
    description = Column(Text)
    tags = Column(CSVText)
    distribution = Column(CSVText)


class GroundWater(Base):
    __tablename__ = "groundwater"
    id = Column(Integer, primary_key=True, autoincrement=True)

    groundwater_impervious_layer_level = Column(Float)
    groundwater_impervious_layer_level_file = Column(String(255))
    groundwater_impervious_layer_level_aggregation = Column(
        IntegerEnum(constants.InitializationType)
    )
    phreatic_storage_capacity = Column(Float)
    phreatic_storage_capacity_file = Column(String(255))
    phreatic_storage_capacity_aggregation = Column(
        IntegerEnum(constants.InitializationType)
    )
    equilibrium_infiltration_rate = Column(Float)
    equilibrium_infiltration_rate_file = Column(String(255))
    equilibrium_infiltration_rate_aggregation = Column(
        IntegerEnum(constants.InitializationType)
    )
    initial_infiltration_rate = Column(Float)
    initial_infiltration_rate_file = Column(String(255))
    initial_infiltration_rate_aggregation = Column(
        IntegerEnum(constants.InitializationType)
    )
    infiltration_decay_period = Column(Float)
    infiltration_decay_period_file = Column(String(255))
    infiltration_decay_period_aggregation = Column(
        IntegerEnum(constants.InitializationType)
    )
    groundwater_hydraulic_conductivity = Column(Float)
    groundwater_hydraulic_conductivity_file = Column(String(255))
    groundwater_hydraulic_conductivity_aggregation = Column(
        IntegerEnum(constants.InitializationType)
    )
    leakage = Column(Float)
    leakage_file = Column(String(255))

    # Alias needed for API compatibility
    @property
    def groundwater_hydro_connectivity_file(self):
        return self.groundwater_hydraulic_conductivity_file


class GridRefinementLine(Base):
    __tablename__ = "grid_refinement_line"
    id = Column(Integer, primary_key=True, autoincrement=True)
    display_name = Column(String(255))
    grid_level = Column(Integer)
    geom = Column(Geometry("LINESTRING"), nullable=False)
    code = Column(String(100))
    tags = Column(CSVText)


class GridRefinementArea(Base):
    __tablename__ = "grid_refinement_area"
    id = Column(Integer, primary_key=True, autoincrement=True)
    display_name = Column(String(255))
    grid_level = Column(Integer)
    code = Column(String(100))
    geom = Column(Geometry("POLYGON"), nullable=False)
    tags = Column(CSVText)


class ConnectionNode(Base):
    __tablename__ = "connection_node"
    id = Column(Integer, primary_key=True, autoincrement=True)
    geom = Column(Geometry("POINT"), nullable=False)
    code = Column(String(100))
    tags = Column(CSVText)
    display_name = Column(Text)
    storage_area = Column(Float)
    initial_water_level = Column(Float)
    visualisation = Column(Integer)
    manhole_surface_level = Column(Float)
    bottom_level = Column(Float)
    exchange_level = Column(Float)
    exchange_type = Column(IntegerEnum(constants.CalculationTypeNode))
    exchange_thickness = Column(Float)
    hydraulic_conductivity_in = Column(Float)
    hydraulic_conductivity_out = Column(Float)


class Lateral1D(Base):
    __tablename__ = "lateral_1d"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(Text)
    display_name = Column(Text)
    timeseries = Column(CSVText)
    time_units = Column(Text)
    interpolate = Column(Boolean)
    offset = Column(Integer)
    units = Column(Text)
    tags = Column(CSVText)
    geom = Column(Geometry("POINT"), nullable=False)

    connection_node_id = Column(Integer)


class NumericalSettings(Base):
    __tablename__ = "numerical_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cfl_strictness_factor_1d = Column(Float)
    cfl_strictness_factor_2d = Column(Float)
    convergence_cg = Column(Float)
    convergence_eps = Column(Float)
    flow_direction_threshold = Column(Float)
    friction_shallow_water_depth_correction = Column(
        IntegerEnum(constants.FrictionShallowWaterDepthCorrection)
    )
    general_numerical_threshold = Column(Float)
    time_integration_method = Column(IntegerEnum(constants.IntegrationMethod))
    limiter_waterlevel_gradient_1d = Column(IntegerEnum(constants.OffOrStandard))
    limiter_waterlevel_gradient_2d = Column(IntegerEnum(constants.OffOrStandard))
    limiter_slope_crossectional_area_2d = Column(
        IntegerEnum(constants.LimiterSlopeXArea)
    )
    limiter_slope_friction_2d = Column(IntegerEnum(constants.OffOrStandard))
    max_non_linear_newton_iterations = Column(Integer)
    max_degree_gauss_seidel = Column(Integer)
    min_friction_velocity = Column(Float)
    min_surface_area = Column(Float)
    use_preconditioner_cg = Column(IntegerEnum(constants.OffOrStandard))
    preissmann_slot = Column(Float)
    pump_implicit_ratio = Column(Float)
    limiter_slope_thin_water_layer = Column(Float)
    use_of_cg = Column(Integer)
    use_nested_newton = Column(IntegerEnum(constants.OffOrStandard))
    flooding_threshold = Column(Float)


class VegetationDrag2D(Base):
    __tablename__ = "vegetation_drag_2d"
    id = Column(Integer, primary_key=True, autoincrement=True)

    vegetation_height = Column(Float)
    vegetation_height_file = Column(String(255))

    vegetation_stem_count = Column(Float)
    vegetation_stem_count_file = Column(String(255))

    vegetation_stem_diameter = Column(Float)
    vegetation_stem_diameter_file = Column(String(255))

    vegetation_drag_coefficient = Column(Float)
    vegetation_drag_coefficient_file = Column(String(255))


class ModelSettings(Base):
    __tablename__ = "model_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    use_2d_flow = Column(Boolean)
    use_1d_flow = Column(Boolean)
    manhole_aboveground_storage_area = Column(Float)
    minimum_cell_size = Column(Float)
    calculation_point_distance_1d = Column(Float)
    nr_grid_levels = Column(Integer)
    minimum_table_step_size = Column(Float)
    maximum_table_step_size = Column(Float)
    dem_file = Column(String(255))
    friction_type = Column(IntegerEnum(constants.FrictionType))
    friction_coefficient = Column(Float)
    friction_coefficient_file = Column(String(255))
    embedded_cutoff_threshold = Column(Float)
    max_angle_1d_advection = Column(Float)
    friction_averaging = Column(Boolean)
    table_step_size_1d = Column(Float)
    use_2d_rain = Column(Boolean)
    use_interflow = Column(Boolean)
    use_interception = Column(Boolean)
    use_simple_infiltration = Column(Boolean)
    use_groundwater_flow = Column(Boolean)
    use_groundwater_storage = Column(Boolean)
    use_vegetation_drag_2d = Column(Boolean)
    node_open_water_detection = Column(IntegerEnum(constants.NodeOpenWaterDetection))

    # Alias needed for API compatibility
    @property
    def frict_coef_file(self):
        return self.friction_coefficient_file


class InitialConditions(Base):
    __tablename__ = "initial_conditions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    initial_groundwater_level = Column(Float)
    initial_groundwater_level_file = Column(String(255))
    initial_groundwater_level_aggregation = Column(
        IntegerEnum(constants.InitializationType)
    )
    initial_water_level = Column(Float)
    initial_water_level_aggregation = Column(IntegerEnum(constants.InitializationType))
    initial_water_level_file = Column(String(255))

    # Alias needed for API compatibility
    @property
    def initial_waterlevel_file(self):
        return self.initial_water_level_file


class Interception(Base):
    __tablename__ = "interception"
    id = Column(Integer, primary_key=True, autoincrement=True)
    interception = Column(Float)
    interception_file = Column(String(255))


# class PhysicalSettings
class AggregationSettings(Base):
    __tablename__ = "aggregation_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    flow_variable = Column(VarcharEnum(constants.FlowVariable))
    aggregation_method = Column(VarcharEnum(constants.AggregationMethod))
    interval = Column(Integer)


class PhysicalSettings(Base):
    __tablename__ = "physical_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    use_advection_1d = Column(IntegerEnum(constants.AdvectionTypes1D))
    use_advection_2d = Column(Boolean)


class SimulationTemplateSettings(Base):
    __tablename__ = "simulation_template_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128))
    use_0d_inflow = Column(IntegerEnum(constants.InflowType))
    use_structure_control = Column(Boolean)


class TimeStepSettings(Base):
    __tablename__ = "time_step_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    time_step = Column(Float)
    min_time_step = Column(Float)
    max_time_step = Column(Float)
    output_time_step = Column(Float)
    use_time_step_stretch = Column(Boolean)


class BoundaryCondition1D(Base):
    __tablename__ = "boundary_condition_1d"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(Text)
    display_name = Column(Text)
    type = Column(IntegerEnum(constants.BoundaryType))
    timeseries = Column(CSVText)
    time_units = Column(Text)
    interpolate = Column(Boolean)
    tags = Column(CSVText)
    geom = Column(Geometry("POINT"), nullable=False)

    connection_node_id = Column(Integer)


class SurfaceMap(Base):
    __tablename__ = "surface_map"
    id = Column(Integer, primary_key=True, autoincrement=True)
    surface_id = Column(Integer, nullable=False)
    connection_node_id = Column(Integer)
    percentage = Column(Float)
    geom = Column(Geometry("LINESTRING"), nullable=False)
    tags = Column(CSVText)
    code = Column(String(100))
    display_name = Column(String(255))


class Channel(Base):
    __tablename__ = "channel"
    id = Column(Integer, primary_key=True, autoincrement=True)
    display_name = Column(String(255))
    code = Column(String(100))
    tags = Column(CSVText)
    exchange_type = Column(IntegerEnum(constants.CalculationType))
    calculation_point_distance = Column(Float)
    geom = Column(Geometry("LINESTRING"), nullable=False)
    connection_node_id_start = Column(Integer)
    connection_node_id_end = Column(Integer)
    exchange_thickness = Column(Float)
    hydraulic_conductivity_in = Column(Float)
    hydraulic_conductivity_out = Column(Float)


class Windshielding1D(Base):
    __tablename__ = "windshielding_1d"
    id = Column(Integer, primary_key=True, autoincrement=True)
    north = Column(Float)
    northeast = Column(Float)
    east = Column(Float)
    southeast = Column(Float)
    south = Column(Float)
    southwest = Column(Float)
    west = Column(Float)
    northwest = Column(Float)
    geom = Column(Geometry("POINT"), nullable=False)
    channel_id = Column(Integer)
    tags = Column(CSVText)
    code = Column(String(100))
    display_name = Column(String(255))


class CrossSectionLocation(Base):
    __tablename__ = "cross_section_location"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(100))
    tags = Column(CSVText)
    reference_level = Column(Float)
    friction_type = Column(IntegerEnum(constants.FrictionType))
    friction_value = Column(Float)
    bank_level = Column(Float)
    cross_section_shape = Column(IntegerEnum(constants.CrossSectionShape))
    cross_section_width = Column(Float)
    cross_section_height = Column(Float)
    cross_section_friction_values = Column(CSVText)
    cross_section_vegetation_table = Column(CSVTable)
    cross_section_table = Column(CSVTable)
    vegetation_stem_density = Column(Float)
    vegetation_stem_diameter = Column(Float)
    vegetation_height = Column(Float)
    vegetation_drag_coefficient = Column(Float)
    geom = Column(Geometry("POINT"), nullable=False)
    channel_id = Column(Integer)
    display_name = Column(String(255))


class Pipe(Base):
    __tablename__ = "pipe"
    id = Column(Integer, primary_key=True, autoincrement=True)
    display_name = Column(String(255))
    code = Column(String(100))
    tags = Column(CSVText)
    geom = Column(Geometry("LINESTRING"), nullable=False)
    sewerage_type = Column(IntegerEnum(constants.SewerageType))
    exchange_type = Column(IntegerEnum(constants.PipeCalculationType))
    invert_level_start = Column(Float)
    invert_level_end = Column(Float)
    friction_value = Column(Float)
    friction_type = Column(IntegerEnum(constants.FrictionType))
    calculation_point_distance = Column(Float)
    material_id = Column(Integer)
    connection_node_id_start = Column(Integer)
    connection_node_id_end = Column(Integer)
    cross_section_shape = Column(IntegerEnum(constants.CrossSectionShape))
    cross_section_width = Column(Float)
    cross_section_height = Column(Float)
    cross_section_table = Column(CSVTable)
    exchange_thickness = Column(Float)
    hydraulic_conductivity_in = Column(Float)
    hydraulic_conductivity_out = Column(Float)


class Culvert(Base):
    __tablename__ = "culvert"
    id = Column(Integer, primary_key=True, autoincrement=True)
    display_name = Column(String(255))
    code = Column(String(100))
    tags = Column(CSVText)
    exchange_type = Column(IntegerEnum(constants.CalculationTypeCulvert))
    friction_value = Column(Float)
    friction_type = Column(IntegerEnum(constants.FrictionType))
    calculation_point_distance = Column(Float)
    discharge_coefficient_positive = Column(Float)
    discharge_coefficient_negative = Column(Float)
    invert_level_start = Column(Float)
    invert_level_end = Column(Float)
    geom = Column(Geometry("LINESTRING"), nullable=False)
    material_id = Column(Integer)
    connection_node_id_start = Column(Integer)
    connection_node_id_end = Column(Integer)
    cross_section_shape = Column(IntegerEnum(constants.CrossSectionShape))
    cross_section_width = Column(Float)
    cross_section_height = Column(Float)
    cross_section_table = Column(CSVTable)


class DemAverageArea(Base):
    __tablename__ = "dem_average_area"
    id = Column(Integer, primary_key=True, autoincrement=True)
    geom = Column(Geometry("POLYGON"), nullable=False)
    display_name = Column(Text)
    code = Column(Text)
    tags = Column(CSVText)


class Weir(Base):
    __tablename__ = "weir"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(100))
    display_name = Column(String(255))
    geom = Column(Geometry("LINESTRING"), nullable=False)
    tags = Column(CSVText)
    crest_level = Column(Float)
    crest_type = Column(IntegerEnum(constants.CrestType))
    friction_value = Column(Float)
    friction_type = Column(IntegerEnum(constants.FrictionType))
    discharge_coefficient_positive = Column(Float)
    discharge_coefficient_negative = Column(Float)
    material_id = Column(Integer)
    sewerage = Column(Boolean)
    external = Column(Boolean)
    connection_node_id_start = Column(Integer)
    connection_node_id_end = Column(Integer)
    cross_section_shape = Column(IntegerEnum(constants.CrossSectionShape))
    cross_section_width = Column(Float)
    cross_section_height = Column(Float)
    cross_section_table = Column(CSVTable)


class Orifice(Base):
    __tablename__ = "orifice"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(100))
    display_name = Column(String(255))
    tags = Column(CSVText)
    geom = Column(Geometry("LINESTRING"), nullable=False)
    crest_type = Column(IntegerEnum(constants.CrestType))
    crest_level = Column(Float)
    material_id = Column(Integer)
    friction_value = Column(Float)
    friction_type = Column(IntegerEnum(constants.FrictionType))
    discharge_coefficient_positive = Column(Float)
    discharge_coefficient_negative = Column(Float)
    sewerage = Column(Boolean)
    connection_node_id_start = Column(Integer)
    connection_node_id_end = Column(Integer)
    cross_section_shape = Column(IntegerEnum(constants.CrossSectionShape))
    cross_section_width = Column(Float)
    cross_section_height = Column(Float)
    cross_section_table = Column(CSVTable)


class Pump(Base):
    __tablename__ = "pump"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(100))
    display_name = Column(String(255))
    start_level = Column(Float)
    lower_stop_level = Column(Float)
    upper_stop_level = Column(Float)
    capacity = Column(Float)
    type_ = Column(
        IntegerEnum(constants.PumpType), name="type", key="type_"
    )  # type: ignore[call-overload]
    sewerage = Column(Boolean)
    connection_node_id = Column(Integer)
    geom = Column(Geometry("POINT"), nullable=False)
    tags = Column(CSVText)


class PumpMap(Base):
    __tablename__ = "pump_map"
    id = Column(Integer, primary_key=True, autoincrement=True)
    pump_id = Column(Integer)
    connection_node_id_end = Column(Integer)
    geom = Column(Geometry("LINESTRING"), nullable=False)
    tags = Column(CSVText)
    code = Column(String(100))
    display_name = Column(String(255))


class Obstacle(Base):
    __tablename__ = "obstacle"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(100))
    crest_level = Column(Float)
    geom = Column(Geometry("LINESTRING"), nullable=False)
    tags = Column(CSVText)
    display_name = Column(String(255))
    affects_2d = Column(Boolean)
    affects_1d2d_open_water = Column(Boolean)
    affects_1d2d_closed = Column(Boolean)


class PotentialBreach(Base):
    __tablename__ = "potential_breach"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(100))
    display_name = Column(String(255))
    tags = Column(CSVText)
    initial_exchange_level = Column(Float)
    final_exchange_level = Column(Float)
    levee_material = Column(IntegerEnum(constants.Material))
    geom = Column(Geometry("LINESTRING"), nullable=False)
    channel_id = Column(Integer)


class ExchangeLine(Base):
    __tablename__ = "exchange_line"
    id = Column(Integer, primary_key=True, autoincrement=True)
    geom = Column(Geometry("LINESTRING"), nullable=False)
    channel_id = Column(Integer)
    exchange_level = Column(Float)
    display_name = Column(Text)
    code = Column(Text)
    tags = Column(CSVText)


class Tags(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, autoincrement=True)
    description = Column(Text)


class Material(Base):
    __tablename__ = "material"
    id = Column(Integer, primary_key=True, autoincrement=True)
    description = Column(Text)
    friction_type = Column(IntegerEnum(constants.FrictionType))
    friction_coefficient = Column(Float)


DECLARED_MODELS = [
    AggregationSettings,
    BoundaryCondition1D,
    BoundaryConditions2D,
    Channel,
    ConnectionNode,
    MeasureLocation,
    MeasureMap,
    MemoryControl,
    TableControl,
    CrossSectionLocation,
    Culvert,
    DemAverageArea,
    DryWeatherFlow,
    DryWeatherFlowMap,
    DryWeatherFlowDistribution,
    ExchangeLine,
    GridRefinementLine,
    GridRefinementArea,
    GroundWater,
    InitialConditions,
    Interception,
    Interflow,
    Lateral1D,
    Lateral2D,
    Material,
    ModelSettings,
    NumericalSettings,
    Obstacle,
    Orifice,
    PhysicalSettings,
    Pipe,
    PotentialBreach,
    Pump,
    PumpMap,
    SimpleInfiltration,
    SimulationTemplateSettings,
    Surface,
    SurfaceMap,
    SurfaceParameters,
    Tags,
    TimeStepSettings,
    VegetationDrag2D,
    Weir,
    Windshielding1D,
]
