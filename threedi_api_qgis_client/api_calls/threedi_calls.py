import os
import datetime
from typing import List, Dict
from threedi_api_client import ThreediApiClient
from openapi_client.exceptions import ApiException
from openapi_client import (ApiClient, RepositoriesApi, Repository, SimulationsApi, Simulation, UsageApi, Usage, Action,
                            Progress, RevisionsApi, Revision, ThreediModel, ConstantRain, TimeseriesRain)


def get_api_client(api_host: str, api_username: str, api_password: str, testing: bool = False) -> ApiClient:
    """Setup open_api client using username and password."""
    os.environ["API_HOST"] = api_host
    os.environ["API_USERNAME"] = api_username
    os.environ["API_PASSWORD"] = api_password
    if testing is True:
        api_client = ApiClient()
    else:
        api_client = ThreediApiClient()
    return api_client


class ThreediCalls:
    """Class to do all the communication with the 3Di API."""
    def __init__(self, api_client: ApiClient) -> None:
        self.api_client = api_client

    def fetch_repositories(self) -> List[Repository]:
        """Fetch all repositories available for current user."""
        api = RepositoriesApi(self.api_client)
        repositories_list = api.repositories_list().results
        return repositories_list

    def fetch_simulations(self) -> List[Simulation]:
        """Fetch all simulations available for current user."""
        api = SimulationsApi(self.api_client)
        simulations_list = api.simulations_list().results
        return simulations_list

    def fetch_revisions(self) -> List[Revision]:
        """Fetch all Revisions available for current user."""
        api = RevisionsApi(self.api_client)
        revisions_list = api.revisions_list().results
        return revisions_list

    def fetch_revision_3di_models(self, rev_id: int) -> List[ThreediModel]:
        """Fetch all 3Di models belonging to given Revision."""
        api = RevisionsApi(self.api_client)
        revision_models_list = api.revisions_threedimodels(rev_id)
        return revision_models_list

    def fetch_usage(self) -> List[Usage]:
        """Fetch overview of ran simulations."""
        api = UsageApi(self.api_client)
        usage_list = api.usage_list().results
        return usage_list

    def new_simulation(self, **simulation_data) -> Simulation:
        """Create a new Simulation."""
        api = SimulationsApi(self.api_client)
        sim = Simulation(**simulation_data)
        new_sim = api.simulations_create(sim)
        return new_sim

    def make_action_on_simulation(self, simulation_pk: int, **action_data) -> Action:
        """Make an action on 'simulation_pk' simulation."""
        api = SimulationsApi(self.api_client)
        action = api.simulations_actions_create(str(simulation_pk), action_data)
        return action

    def add_constant_precipitation(self, simulation_pk: int, **rain_data) -> ConstantRain:
        """Add ConstantRain to the given simulation."""
        api = SimulationsApi(self.api_client)
        constant_rain = api.simulations_events_rain_constant_create(str(simulation_pk), rain_data)
        return constant_rain

    def add_custom_precipitation(self, simulation_pk: int, **rain_data) -> TimeseriesRain:
        """Add TimeseriesRain to the given simulation."""
        api = SimulationsApi(self.api_client)
        time_series_rain = api.simulations_events_rain_timeseries_create((str(simulation_pk)), rain_data)
        return time_series_rain

    def simulations_progress(self, simulation_pk: int) -> Progress:
        """Get a given simulation progress. Available only if simulation was already started."""
        api = SimulationsApi(self.api_client)
        simulations_progress = api.simulations_progress_list(str(simulation_pk))
        return simulations_progress

    def all_simulations_progress(self) -> Dict[str, Dict[str, int]]:
        """Get all simulations progresses."""
        api = SimulationsApi(self.api_client)
        progresses = {}
        for sim in self.fetch_simulations():
            spk = str(sim.id)
            try:
                sim_progress = api.simulations_progress_list(spk)
            except ApiException:
                sim_progress = {'percentage': 0, 'time': 0}
            progresses[spk] = sim_progress
        return progresses


if __name__ == "__main__":
    import sys
    API_HOST = "https://api.3di.live/v3.0"
    API_USERNAME = sys.argv[1]
    API_PASSWORD = sys.argv[2]
    aclient = get_api_client(API_HOST, API_USERNAME, API_PASSWORD)
    tc = ThreediCalls(aclient)
    repos = tc.fetch_repositories()
    sims = tc.fetch_simulations()
    print(repos)
    print(sims)
    #print(tc.make_action_on_simulation(1203, name="start"))
    sim_data = {
        "name": "qgis client test run 4",
        "threedimodel": "14",
        "organisation": "cb0347bf57f7450984c4b1d27271c90f",
        "start_datetime":  datetime.datetime.utcnow(),
        "duration": 72000
    }
    #print(tc.new_simulation(**sim_data))
    print(tc.all_simulations_progress())
    print(tc.fetch_revisions())
    print(tc.fetch_revision_3di_models(8))
    constant_rain_data = {
        'durationnn': 5000,
        'offset': 60,
        'units': 'm/s',
        'value': 0.0006}
    print(tc.add_constant_precipitation(1203, **constant_rain_data))
