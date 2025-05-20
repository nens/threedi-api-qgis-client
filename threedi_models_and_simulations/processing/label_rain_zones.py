from datetime import datetime
from typing import Dict

from threedi_api_client.api import ThreediApi


class MockFeedback:
    def pushInfo(self, message):
        pass


def label_rain_zones(
    api_host: str,
    api_key: str,
    simulation_template_id: int,
    simulation_name: str,
    zones: Dict[str, str],
    feedback=None
):
    """
    Creates a simulation from a template, adds rain zones to the rain event(s) and add the simulation to the queue
    The simulation is owned by the same organisation that owns the simulation from which the template was made
    Feedback (e.g. a QgsProcessingFeedback) should have the following methods:
    - pushInfo()
    """
    feedback = feedback or MockFeedback()

    config = {
        "THREEDI_API_HOST": api_host,
        "THREEDI_API_PERSONAL_API_TOKEN": api_key
    }

    api_client = ThreediApi(config=config, version='v3-beta')

    simulation_template = api_client.simulation_templates_read(simulation_template_id)
    feedback.pushInfo(f"Found simulation template '{simulation_template.name}' with id {simulation_template.id}")

    original_simulation_id = simulation_template.simulation.id
    original_time_series_rain_events = api_client.simulations_events(original_simulation_id).timeseriesrain
    if len(original_time_series_rain_events) == 0:
        feedback.pushInfo(f"Simulation template does not have any constant or time series rain events")
        return

    # Create new simulation from template
    simulation = api_client.simulations_from_template(
        data={
            "template": simulation_template.id,
            "name": simulation_name,
            "organisation": simulation_template.simulation.organisation,
            "start_datetime": datetime.now(),
            "duration": simulation_template.simulation.duration
        }
    )

    feedback.pushInfo(f"Created simulation '{simulation.name}' with id {simulation.id}")
    substances = []
    for i, zone_name in enumerate(zones.keys()):
        substances.append(
            api_client.simulations_substances_create(
                simulation.id,
                {
                    "name": zone_name,
                    "units": "%",
                }
            )
        )
        feedback.pushInfo(f"Created substance '{substances[i].name}' with id {substances[i].id}")

    # Delete existing rain events
    time_series_rain_events = api_client.simulations_events(simulation.id).timeseriesrain
    for rain_event in time_series_rain_events:
        api_client.simulations_events_rain_timeseries_delete(simulation.id, rain_event.id)

    # Re-add rain events, but now with zone and substance concentrations
    for rain_event in original_time_series_rain_events:
        concentration_time_series = [[row[0], 100] for row in rain_event.values]
        concentration_data = []
        for substance in substances:
            concentration_data_entry = {
                'substance': substance.id,
                'concentrations': concentration_time_series,
                'zone': zones[substance.name],
            }
            concentration_data.append(concentration_data_entry)

        rain = api_client.simulations_events_rain_timeseries_create(
            simulation_pk=simulation.id, data={
                'offset': rain_event.offset,
                'values': rain_event.values,
                'units': rain_event.units,
                'interpolate': rain_event.interpolate,
                'substances': concentration_data
            }
        )

        feedback.pushInfo(f"Created time series rain event with id {rain.id} ")

    api_client.simulations_actions_create(simulation.id, data={"name": "queue"})
    feedback.pushInfo(f"Added simulation '{simulation.name}' with id {simulation.id} to queue")
