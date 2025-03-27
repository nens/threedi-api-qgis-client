"""Upgrade settings in schema

Revision ID: 0222
Revises:
Create Date: 2024-03-04 10:06

"""
import uuid

from typing import Dict, List, Tuple
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Boolean, Column, Float, Integer, String
from sqlalchemy.orm import declarative_base

from threedi_schema.migrations.utils import drop_conflicting

# revision identifiers, used by Alembic.
revision = "0222"
down_revision = "0221"
branch_labels = None
depends_on = None

Base = declarative_base()

data_dir = Path(__file__).parent / "data"


# (source table, destination table)
RENAME_TABLES = [
    ("v2_aggregation_settings", "aggregation_settings"),
    ("v2_groundwater", "groundwater"),
    ("v2_interflow", "interflow"),
    ("v2_numerical_settings", "numerical_settings"),
    ("v2_simple_infiltration", "simple_infiltration"),
    ("v2_vegetation_drag", "vegetation_drag_2d"),
    ("v2_global_settings", "model_settings")
]

# (old name, new name)
RENAME_COLUMNS = {
    "aggregation_settings":
        [
            ("timestep", "interval"),
        ],
    "groundwater":
        [
            ("groundwater_hydro_connectivity", "groundwater_hydraulic_conductivity"),
            ("groundwater_hydro_connectivity_file", "groundwater_hydraulic_conductivity_file"),
            ("groundwater_hydro_connectivity_type", "groundwater_hydraulic_conductivity_aggregation"),
            ("groundwater_impervious_layer_level_type", "groundwater_impervious_layer_level_aggregation"),
            ("infiltration_decay_period_type", "infiltration_decay_period_aggregation"),
            ("initial_infiltration_rate_type", "initial_infiltration_rate_aggregation"),
            ("phreatic_storage_capacity_type", "phreatic_storage_capacity_aggregation"),
            ("equilibrium_infiltration_rate_type", "equilibrium_infiltration_rate_aggregation"),
        ],
    "numerical_settings":
        [
            ("frict_shallow_water_correction", "friction_shallow_water_depth_correction"),
            ("thin_water_layer_definition", "limiter_slope_thin_water_layer"),
            ("limiter_grad_1d", "limiter_waterlevel_gradient_1d"),
            ("limiter_grad_2d", "limiter_waterlevel_gradient_2d"),
            ("max_degree", "max_degree_gauss_seidel"),
            ("max_nonlin_iterations", "max_non_linear_newton_iterations"),
            ("minimum_friction_velocity", "min_friction_velocity"),
            ("minimum_surface_area", "min_surface_area"),
            ("integration_method", "time_integration_method"),
            ("use_of_nested_newton", "use_nested_newton"),
            ("precon_cg", "use_preconditioner_cg"),
        ],
    "simple_infiltration":
        [
            ("max_infiltration_capacity", "max_infiltration_volume"),
            ("max_infiltration_capacity_file", "max_infiltration_volume_file"),
            ("infiltration_rate", "infiltration_rate")
        ],
    "model_settings":
        [
            ("dist_calc_points", "calculation_point_distance_1d"),
            ("frict_avg", "friction_averaging"),
            ("frict_coef", "friction_coefficient"),
            ("frict_coef_file", "friction_coefficient_file"),
            ("frict_type", "friction_type"),
            ("manhole_storage_area", "manhole_aboveground_storage_area"),
            ("grid_space", "minimum_cell_size"),
            ("kmax", "nr_grid_levels"),
            ("table_step_size", "minimum_table_step_size"),
        ],
}

ADD_COLUMNS = [
    ("numerical_settings", Column("flooding_threshold", Float)),
    ("model_settings", Column("use_groundwater_flow", Boolean)),
    ("model_settings", Column("use_groundwater_storage", Boolean)),
    ("model_settings", Column("use_structure_control", Boolean)),
    ("model_settings", Column("use_simple_infiltration", Boolean)),
    ("model_settings", Column("use_vegetation_drag_2d", Boolean)),
    ("model_settings", Column("use_interflow", Boolean)),
    ("model_settings", Column("use_interception", Boolean)),
]


ADD_TABLES = {
    "initial_conditions":
        [Column("initial_groundwater_level", Float),
         Column("initial_groundwater_level_aggregation", Integer),
         Column("initial_groundwater_level_file", String),
         Column("initial_water_level", Float),
         Column("initial_water_level_aggregation", Integer),
         Column("initial_water_level_file", String)],
    "interception":
        [Column("interception", Float),
         Column("interception_file", String)],
    "physical_settings":
        [Column("use_advection_1d", Integer),
         Column("use_advection_2d", Integer)],
    "simulation_template_settings":
        [Column("name", String), Column("use_0d_inflow", Integer)],
    "time_step_settings":
        [Column("max_time_step", Float),
         Column("min_time_step", Float),
         Column("output_time_step", Float),
         Column("time_step", Float),
         Column("use_time_step_stretch", Boolean)],
}

REMOVE_COLUMNS = [
    ("aggregation_settings", ["global_settings_id", "var_name"]),
    ("groundwater", ["display_name"]),
    ("interflow", ["display_name"]),
    ("model_settings", ["nr_timesteps",
                        "start_time",
                        "start_date",
                        "guess_dams",
                        "dem_obstacle_detection",
                        "dem_obstacle_height",
                        "wind_shielding_file"]),
    ("simple_infiltration", ["display_name"]),
    ("vegetation_drag_2d", ["display_name"]),
]

COPY_FROM_GLOBAL = {
    "simulation_template_settings": [
        ("name", "name"),
        ("use_0d_inflow", "use_0d_inflow")
    ],
    "time_step_settings": [
        ("maximum_sim_time_step", "max_time_step"),
        ("minimum_sim_time_step", "min_time_step"),
        ("output_time_step", "output_time_step"),
        ("sim_time_step", "time_step"),
        ("timestep_plus", "use_time_step_stretch"),
    ],
    "initial_conditions": [
        ("initial_groundwater_level", "initial_groundwater_level"),
        ("initial_groundwater_level_type", "initial_groundwater_level_aggregation"),
        ("initial_groundwater_level_file", "initial_groundwater_level_file"),
        ("initial_waterlevel", "initial_water_level"),
        ("water_level_ini_type", "initial_water_level_aggregation"),
        ("initial_waterlevel_file", "initial_water_level_file"),
    ],
    "physical_settings": [
        ("advection_1d", "use_advection_1d"),
        ("advection_2d", "use_advection_2d"),
    ],
    "interception": [
        ("interception_global", "interception"),
        ("interception_file", "interception_file"),
    ],
}

# Columns set to True if a mapping between use_* and settings table exists
# (boolean column, setting id, setting table)
GLOBAL_SETTINGS_ID_TO_BOOL = [
    ("use_groundwater_storage", "groundwater_settings_id", "groundwater"),
    ("use_interflow", "interflow_settings_id", "interflow"),
    ("use_structure_control", "control_group_id", "v2_control_group"),
    ("use_simple_infiltration", "simple_infiltration_settings_id", "simple_infiltration"),
    ("use_vegetation_drag_2d", "vegetation_drag_settings_id", "vegetation_drag_2d"),
]


def rename_tables(table_sets: List[Tuple[str, str]]):
    # no checks for existence are done, this will fail if a source table doesn't exist
    for src_name, dst_name in table_sets:
        op.rename_table(src_name, dst_name)


def rename_columns(table_name: str, columns: List[Tuple[str, str]]):
    # no checks for existence are done, this will fail if table or any source column doesn't exist
    with op.batch_alter_table(table_name) as batch_op:
        for src_name, dst_name in columns:
            batch_op.alter_column(src_name, new_column_name=dst_name)


def make_all_columns_nullable(table_name, id_name: str = 'id'):
    # no checks for existence are done, this will fail if table doesn't exist
    connection = op.get_bind()
    table = sa.Table(table_name, sa.MetaData(), autoload_with=connection)
    with op.batch_alter_table(table_name) as batch_op:
        for column in table.columns:
            if column.name == id_name:
                continue
            batch_op.alter_column(column_name=column.name, nullable=True)


def create_new_tables(new_tables: Dict[str, sa.Column]):
    # no checks for existence are done, this will fail if any table already exists
    for table_name, columns in new_tables.items():
        op.create_table(table_name, sa.Column("id", sa.Integer(), primary_key=True),
                        *columns)


def add_columns_to_tables(table_columns: List[Tuple[str, Column]]):
    # no checks for existence are done, this will fail if any column already exists
    for dst_table, col in table_columns:
        with op.batch_alter_table(dst_table) as batch_op:
            batch_op.add_column(col)


def move_multiple_values_to_empty_table(src_table: str, dst_table: str, columns: List[str]):
    # move values from one table to another
    # no checks for existence are done, this will fail if any table or column doesn't exist
    dst_cols = ', '.join(f'"{dst}"' for _, dst in columns)
    src_cols = ', '.join(src for src, _ in columns)
    op.execute(sa.text(f'INSERT INTO {dst_table} ({dst_cols}) SELECT {src_cols} FROM {src_table}'))
    remove_columns_from_table(src_table, [src for src, _ in columns])


def move_values_to_table(src_table: str, src_col: str, dst_table: str, dst_col: str):
    op.execute(f'UPDATE {dst_table} SET {dst_col} = (SELECT {src_col} FROM {src_table} ORDER BY id LIMIT 1)')
    remove_columns_from_table(src_table, [src_col])


def remove_columns_from_table(table_name: str, columns: List[str]):
    # no checks for existence are done, this will fail if any table or column doesn't exist
    with op.batch_alter_table(table_name) as batch_op:
        for column in columns:
            batch_op.drop_column(column)


def set_use_from_settings_id():
    for settings_col, settings_id, settings_table in GLOBAL_SETTINGS_ID_TO_BOOL:
        if settings_col != '':
            # set boolean 'use_*' in model_settings if a relationship exists
            op.execute(f"UPDATE model_settings SET {settings_col} = TRUE WHERE {settings_id} IS NOT NULL;")
        # remove all settings rows, exact for the one matching
        # delete_all_but_matching_id(settings_table, settings_id)
        op.execute(
            f"DELETE FROM {settings_table} WHERE NOT EXISTS "
            f"(SELECT 1 FROM model_settings WHERE model_settings.{settings_id} IS NOT NULL);")
        # command above doesn't catch id = None, so an extra command is needed for those cases
        op.execute(
            f"DELETE FROM {settings_table} WHERE id != "
            f"(SELECT {settings_id} FROM model_settings);")

    # set use_groundwater_flow
    sql = """
        UPDATE model_settings
        SET use_groundwater_flow = CASE
            WHEN (SELECT groundwater_hydraulic_conductivity FROM groundwater LIMIT 1) IS NOT NULL OR (SELECT groundwater_hydraulic_conductivity_file FROM groundwater LIMIT 1) IS NOT NULL THEN 1
            ELSE 0
        END;
        """
    op.execute(sql)


def drop_columns(table, columns):
    with op.batch_alter_table(table) as batch_op:
        for column in columns:
            batch_op.drop_column(column)


def set_use_inteception():
    # Set use_interception based on interception and interception_file values
    op.execute(sa.text("""
    UPDATE model_settings
    SET use_interception = (
        SELECT 
            CASE WHEN
                interception.interception IS NOT NULL  
                OR 
                (interception.interception_file IS NOT NULL 
                AND interception.interception_file != '') 
                THEN 1
                ELSE 0
            END
        FROM interception
    );    
    """))

    op.execute(sa.text("""
    DELETE FROM interception 
    WHERE (interception IS NULL OR interception = '')
    AND (interception_file IS NULL OR interception_file = '');    
    """))


def delete_all_but_matching_id(table, settings_id):
    op.execute(f"DELETE FROM {table} WHERE id NOT IN (SELECT {settings_id} FROM model_settings);")


def delete_all_but_first_row(table):
    op.execute(f"DELETE FROM {table} WHERE id NOT IN ("
               f"SELECT id FROM "
               f"(SELECT id FROM {table} ORDER BY id LIMIT 1) AS subquery);")


def correct_raster_paths():
    # Replace paths to raster files with only the file name
    raster_paths = [
        ("model_settings", "dem_file"),
        ("model_settings", "friction_coefficient_file"),
        ("interception", "interception_file"),
        ("interflow", "porosity_file"),
        ("interflow", "hydraulic_conductivity_file"),
        ("simple_infiltration", "infiltration_rate_file"),
        ("simple_infiltration", "max_infiltration_volume_file"),
        ("groundwater", "groundwater_impervious_layer_level_file"),
        ("groundwater", "phreatic_storage_capacity_file"),
        ("groundwater", "initial_infiltration_rate_file"),
        ("groundwater", "equilibrium_infiltration_rate_file"),
        ("groundwater", "infiltration_decay_period_file"),
        ("groundwater", "groundwater_hydraulic_conductivity_file"),
        ("initial_conditions", "initial_water_level_file"),
        ("initial_conditions", "initial_groundwater_level_file"),
        ("vegetation_drag_2d", "vegetation_height_file"),
        ("vegetation_drag_2d", "vegetation_stem_count_file"),
        ("vegetation_drag_2d", "vegetation_stem_diameter_file"),
        ("vegetation_drag_2d", "vegetation_drag_coefficient_file"),
    ]
    conn = op.get_bind()
    for table, col in raster_paths:
        result = conn.execute(sa.text(f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL;")).fetchall()
        # model_settings only has one row, so we can just grab that one
        if len(result) == 1:
            id, file_path = result[0]
            if isinstance(file_path, str) and len(file_path) > 0:
                # replace backslash in windows paths because pathlib doesn't handle relative windows paths
                file_path = file_path.replace('\\', '/')
                file = Path(file_path).name
                op.execute(
                    sa.text(f"UPDATE {table} SET {col} = :new_value WHERE id = :row_id")
                    .bindparams(new_value=file, row_id=id)
                )


def remove_columns_from_copied_tables(table_name: str, rem_columns: List[str]):
    # sqlite 3.27 doesn't support `ALTER TABLE ... DROP COLUMN`
    # So we create a temp table, copy the columns we want to keep and remove the old table
    # Retrieve columns
    connection = op.get_bind()
    all_columns = connection.execute(sa.text(f"PRAGMA table_info('{table_name}')")).fetchall()
    col_names = [col[1] for col in all_columns if col[1] not in rem_columns]
    col_types = [col[2] for col in all_columns if col[1] not in rem_columns]
    cols = (['id INTEGER PRIMARY KEY NOT NULL'] +
            [f'{cname} {ctype}' for cname, ctype in zip(col_names, col_types) if cname != 'id'])
    # Create new table, insert data, drop original and rename to table_name
    temp_name = f'_temp_222_{uuid.uuid4().hex}'
    op.execute(sa.text(f"CREATE TABLE {temp_name} ({','.join(cols)});"))
    op.execute(sa.text(f"INSERT INTO {temp_name} ({','.join(col_names)}) SELECT {','.join(col_names)} FROM {table_name}"))
    op.execute(sa.text(f"DROP TABLE {table_name};"))
    op.execute(sa.text(f"ALTER TABLE {temp_name} RENAME TO {table_name};"))


def set_flow_variable_values():
    flow_var_dict = {'wet_cross-section': 'wet_cross_section',
                     'waterlevel': 'water_level'}
    cases = '\n'.join([f"WHEN '{key}' THEN '{val}'" for key, val in flow_var_dict.items()])
    query = f"""
    UPDATE aggregation_settings SET flow_variable = CASE flow_variable
    {cases} 
    ELSE flow_variable
    END"""
    op.execute(sa.text(query))


def upgrade():
    op.get_bind()
    # Only use first row of global settings
    delete_all_but_first_row("v2_global_settings")
    # Remove existing tables (outside of the specs) that conflict with new table names
    drop_conflicting(op, list(ADD_TABLES.keys()) + [new_name for _, new_name in RENAME_TABLES])
    rename_tables(RENAME_TABLES)
    # rename columns in renamed tables
    for table_name, columns in RENAME_COLUMNS.items():
        rename_columns(table_name, columns)
    # make all columns in renamed tables, except id, nullable
    for _, table_name in RENAME_TABLES:
        make_all_columns_nullable(table_name)
    # create new tables
    create_new_tables(ADD_TABLES)
    # add empty columns to tables
    add_columns_to_tables(ADD_COLUMNS)
    # copy data from model_settings to new tables and columns
    for dst_table, columns in COPY_FROM_GLOBAL.items():
        move_multiple_values_to_empty_table("model_settings", dst_table, columns)
    # copy data from model_settings to existing table
    move_values_to_table('model_settings', 'flooding_threshold', 'numerical_settings', 'flooding_threshold')
    # set several 'use' columns based on other settings
    set_use_from_settings_id()
    set_use_inteception()
    # keep first row of settings tables that have no explicit mapping
    delete_all_but_matching_id("numerical_settings", "numerical_settings_id")
    # drop unused id columns in model_settings
    unused_cols = [settings_id for _, settings_id, _ in GLOBAL_SETTINGS_ID_TO_BOOL] + ["numerical_settings_id"]
    drop_columns('model_settings', unused_cols)
    # remove relative path prefix from raster paths
    correct_raster_paths()
    # change flow_variable values to new naming scheme
    set_flow_variable_values()
    # remove columns from tables that are copied
    for table, columns in REMOVE_COLUMNS:
        remove_columns_from_copied_tables(table, columns)


def downgrade():
    # Not implemented on purpose
    raise NotImplementedError("Downgrade back from 0.3xx is not supported")
