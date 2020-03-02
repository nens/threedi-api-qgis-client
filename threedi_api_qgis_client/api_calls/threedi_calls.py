import os
import datetime
from threedi_api_client import ThreediApiClient
from openapi_client.exceptions import ApiException
from openapi_client import (RepositoriesApi, SimulationsApi, UsageApi, Simulation, Action, Progress, InpyVersionsApi,
                            RevisionsApi, InlineResponse20050, InlineResponse2008, InlineResponse2002,
                            InlineResponse2006, InlineResponse2005)


class ThreediCalls:
    """Class to do all the communication with the 3Di API."""

    def __init__(self, api_host, api_username, api_password):
        """
        Setup open_api client using username and password.
        """
        os.environ["API_HOST"] = api_host
        os.environ["API_USERNAME"] = api_username
        os.environ["API_PASSWORD"] = api_password
        self.api_host = api_host
        self.api_username = api_username
        self.api_client = ThreediApiClient()
        self._config = self.api_client.configuration
        self._token = self._config.access_token

    def fetch_repositories(self) -> InlineResponse2005:
        """Fetch all repositories available for current user."""
        api = RepositoriesApi(self.api_client)
        repositories_list = api.repositories_list()
        return repositories_list

    def fetch_simulations(self) -> InlineResponse2008:
        """Fetch all simulations available for current user."""
        api = SimulationsApi(self.api_client)
        simulations_list = api.simulations_list()
        return simulations_list

    def fetch_inpy_versions(self) -> InlineResponse2002:
        """Fetch all Inpy Versions available for current user."""
        api = InpyVersionsApi(self.api_client)
        inpy_versions_list = api.inpy_versions_list()
        return inpy_versions_list

    def fetch_revisions(self) -> InlineResponse2006:
        """Fetch all Revisions available for current user."""
        api = RevisionsApi(self.api_client)
        revisions_list = api.revisions_list()
        return revisions_list

    def fetch_revision_3di_models(self, rev_id) -> list:
        """Fetch all 3Di models belonging to given Revision."""
        api = RevisionsApi(self.api_client)
        revision_models_list = api.revisions_threedimodels(rev_id)
        return revision_models_list

    def fetch_usage(self) -> InlineResponse20050:
        """Fetch overview of ran simulations."""
        api = UsageApi(self.api_client)
        usage_list = api.usage_list()
        return usage_list

    def new_simulation(self, **simulation_data) -> Simulation:
        """Create a new Simulation."""
        api = SimulationsApi(self.api_client)
        sim = Simulation(**simulation_data)
        res = api.simulations_create(sim)
        return res

    def make_action_on_simulation(self, simulation_pk, **action_data) -> Action:
        """Make an action on 'simulation_pk' simulation."""
        api = SimulationsApi(self.api_client)
        res = api.simulations_actions_create(str(simulation_pk), action_data)
        return res

    def simulations_progress(self, simulation_pk) -> Progress:
        """Get a given simulation progress. Available only if simulation was already started."""
        api = SimulationsApi(self.api_client)
        simulations_progress = api.simulations_progress_list(str(simulation_pk))
        return simulations_progress

    def all_simulations_progress(self) -> dict:
        """Get all simulations progresses."""
        api = SimulationsApi(self.api_client)
        progresses = {}
        for sim in self.fetch_simulations().results:
            spk = sim.id
            try:
                sim_progress = api.simulations_progress_list(str(spk))
            except ApiException:
                sim_progress = {'percentage': 0, 'time': 0}
            progresses[spk] = sim_progress
        return progresses


if __name__ == "__main__":
    import sys
    API_HOST = "https://api.3di.live/v3.0"
    API_USERNAME = sys.argv[1]
    API_PASSWORD = sys.argv[2]
    tc = ThreediCalls(API_HOST, API_USERNAME, API_PASSWORD)
    repos = tc.fetch_repositories()
    sims = tc.fetch_simulations()
    print(repos)
    print(sims)
    #print(tc.make_action_on_simulation(1203, name="start"))

    data = {
        "name": "qgis client test run 4",
        "threedimodel": "14",
        "organisation": "cb0347bf57f7450984c4b1d27271c90f",
        "start_datetime":  datetime.datetime.utcnow(),
        "duration": 72000
    }
    #print(tc.new_simulation(**data))
    print(tc.all_simulations_progress())
    print(tc.fetch_revisions())
    print(tc.fetch_revision_3di_models(8))
