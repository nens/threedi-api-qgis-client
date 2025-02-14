"""make settings nullable

Revision ID: 0205
Revises: 0204
Create Date: 2021-11-15 16:41:43.316599

"""
from alembic import op

from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "0205"
down_revision = "0204"
branch_labels = None
depends_on = None


MIGRATION_QUERIES = """
UPDATE v2_global_settings SET frict_type = 2 WHERE frict_type IS NULL;

UPDATE v2_global_settings SET use_0d_inflow = 0 WHERE use_0d_inflow IS NULL;

UPDATE v2_global_settings SET minimum_sim_time_step = min(0.01, sim_time_step)
  WHERE minimum_sim_time_step IS NULL
    OR minimum_sim_time_step <= 0
    OR minimum_sim_time_step > sim_time_step;

UPDATE v2_global_settings SET maximum_sim_time_step = sim_time_step
  WHERE (maximum_sim_time_step IS NULL OR maximum_sim_time_step < sim_time_step);

UPDATE v2_global_settings SET output_time_step = max(1, sim_time_step)
  WHERE output_time_step IS NULL OR output_time_step < sim_time_step;

UPDATE v2_global_settings SET flooding_threshold = 1e-6
  WHERE flooding_threshold IS NULL OR flooding_threshold < 0;

UPDATE v2_global_settings SET frict_avg = 1 WHERE frict_avg NOT IN (0, 1);

UPDATE v2_global_settings SET max_angle_1d_advection = 1.256637 WHERE max_angle_1d_advection = 90;

UPDATE v2_global_settings SET dem_obstacle_detection = 0 WHERE dem_obstacle_detection = '';

UPDATE v2_global_settings SET table_step_size_1d = NULL WHERE table_step_size_1d <= 0;

UPDATE v2_global_settings SET table_step_size_volume_2d = NULL WHERE table_step_size_volume_2d <= 0;

UPDATE v2_interflow SET interflow_type = 0
  WHERE (interflow_type != 0)
    AND ((porosity IS NULL AND (porosity_file IS NULL OR porosity_file == ''))
      OR (impervious_layer_elevation IS NULL)
      OR (hydraulic_conductivity IS NULL AND (hydraulic_conductivity_file IS NULL OR hydraulic_conductivity_file == '')));

UPDATE v2_simple_infiltration SET infiltration_rate = 0 WHERE infiltration_rate < 0;

UPDATE v2_numerical_settings SET precon_cg = 1 WHERE precon_cg > 1;

UPDATE v2_numerical_settings SET cfl_strictness_factor_1d = NULL WHERE cfl_strictness_factor_1d = 0;

UPDATE v2_numerical_settings SET convergence_eps = 1e-7 WHERE convergence_eps = 0;

UPDATE v2_numerical_settings SET convergence_cg = NULL WHERE convergence_cg = 0;

UPDATE v2_numerical_settings SET flow_direction_threshold = NULL WHERE flow_direction_threshold = 0;

UPDATE v2_numerical_settings SET general_numerical_threshold = NULL WHERE general_numerical_threshold = 0;

UPDATE v2_numerical_settings SET minimum_surface_area = NULL WHERE minimum_surface_area = 0;

UPDATE v2_numerical_settings SET limiter_slope_friction_2d = 1 WHERE limiter_slope_friction_2d = 3;

UPDATE v2_numerical_settings SET integration_method = NULL WHERE integration_method = 1;

DELETE FROM v2_aggregation_settings WHERE aggregation_method = 'med' OR aggregation_method IS NULL;

UPDATE v2_aggregation_settings SET flow_variable = 'discharge'
  WHERE (flow_variable = 'discharge_negative' AND aggregation_method = 'cum_negative')
    OR (flow_variable = 'discharge_positive' AND aggregation_method = 'cum_positive');
"""


def upgrade():
    for q in MIGRATION_QUERIES.split(";"):
        op.execute(text(q))

    with op.batch_alter_table("v2_global_settings") as batch_op:
        batch_op.alter_column("output_time_step", nullable=False)
        batch_op.alter_column("nr_timesteps", nullable=True)
        batch_op.alter_column("start_date", nullable=True)
        batch_op.alter_column("frict_type", nullable=False)
        batch_op.alter_column("minimum_sim_time_step", nullable=False)
        batch_op.alter_column("frict_avg", nullable=False)
        batch_op.alter_column("use_0d_inflow", nullable=False)

    with op.batch_alter_table("v2_numerical_settings") as batch_op:
        batch_op.alter_column("max_degree", nullable=True)
        batch_op.alter_column("use_of_cg", nullable=True)
        batch_op.alter_column("use_of_nested_newton", nullable=True)

    with op.batch_alter_table("v2_aggregation_settings") as batch_op:
        batch_op.alter_column("aggregation_method", nullable=False)


def downgrade():
    pass
