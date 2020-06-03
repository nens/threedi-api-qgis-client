# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple
from threedi_api_client import ThreediApiClient
from openapi_client import (ApiClient, RepositoriesApi, SimulationsApi, RevisionsApi, OrganisationsApi,
                            ThreedimodelsApi, Repository, Simulation, Action, Progress, Revision, ThreediModel,
                            ConstantRain, TimeseriesRain, Organisation, CurrentStatus, ResultFile, Download, Breach,
                            TimeseriesLateral, ArrivalTimePostProcessing, BasicPostProcessing, DamagePostProcessing)


def get_api_client(api_username: str, api_password: str, api_host: str = "https://api.3di.live/v3.0") -> ApiClient:
    """Setup open_api client using username and password."""
    os.environ["API_HOST"] = api_host
    os.environ["API_USERNAME"] = api_username
    os.environ["API_PASSWORD"] = api_password
    api_client = ThreediApiClient()
    return api_client


class ThreediCalls:
    """Class with methods used for the communication with the 3Di API."""
    FETCH_LIMIT = 100
    EXPIRATION_TIME = datetime.now(timezone.utc) - timedelta(days=7)

    def __init__(self, api_client: ApiClient) -> None:
        self.api_client = api_client

    def fetch_repositories(self) -> List[Repository]:
        """Fetch all repositories available for current user."""
        api = RepositoriesApi(self.api_client)
        response = api.repositories_list(limit=self.FETCH_LIMIT)
        response_count = response.count
        if response_count > self.FETCH_LIMIT:
            response = api.repositories_list(limit=response_count)
        repositories_list = response.results
        return repositories_list

    def fetch_simulations(self) -> List[Simulation]:
        """Fetch all simulations available for current user."""
        api = SimulationsApi(self.api_client)
        created__date__gt = self.EXPIRATION_TIME.strftime('%Y-%m-%d')
        response = api.simulations_list(created__date__gt=created__date__gt, limit=self.FETCH_LIMIT)
        response_count = response.count
        if response_count > self.FETCH_LIMIT:
            response = api.simulations_list(created__date__gt=created__date__gt, limit=response_count)
        simulations_list = response.results
        return simulations_list

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

    def simulation_current_status(self, simulation_pk: int) -> CurrentStatus:
        """Get a given simulation current status."""
        api = SimulationsApi(self.api_client)
        current_status = api.simulations_status_list(str(simulation_pk), limit=self.FETCH_LIMIT)
        return current_status

    def simulations_progress(self, simulation_pk: int) -> Progress:
        """Get a given simulation progress. Available only if simulation was already started."""
        api = SimulationsApi(self.api_client)
        simulations_progress = api.simulations_progress_list(str(simulation_pk), limit=self.FETCH_LIMIT)
        return simulations_progress

    def all_simulations_progress(self, simulations_list: List[Simulation]
                                 ) -> Dict[int, Tuple[Simulation, CurrentStatus, Progress]]:
        """Get all simulations with statuses and progresses."""
        api = SimulationsApi(self.api_client)
        progresses = {}
        if not simulations_list:
            simulations_list = self.fetch_simulations()
        for sim in simulations_list:
            spk = sim.id
            spk_str = str(spk)
            current_status = api.simulations_status_list(spk_str, limit=self.FETCH_LIMIT)
            status_name = current_status.name
            status_time = current_status.time
            if status_time is None:
                status_time = 0
            if status_name == "initialized":
                sim_progress = api.simulations_progress_list(spk_str, limit=self.FETCH_LIMIT)
            elif status_name == "postprocessing" or status_name == "finished":
                sim_progress = Progress(percentage=100, time=status_time)
            else:
                sim_progress = Progress(percentage=0, time=status_time)
            progresses[spk] = (sim, current_status, sim_progress)
        return progresses

    def fetch_simulation_results(self, simulation_pk: int) -> List[ResultFile]:
        """Fetch simulation results list."""
        api = SimulationsApi(self.api_client)
        spk_str = str(simulation_pk)
        response = api.simulations_results_files_list(spk_str, limit=self.FETCH_LIMIT)
        response_count = response.count
        if response_count > self.FETCH_LIMIT:
            response = api.simulations_results_files_list(spk_str, limit=response_count)
        results_list = response.results
        return results_list

    def fetch_simulation_downloads(self, simulation_pk: int) -> List[Tuple[ResultFile, Download]]:
        """Fetch simulation downloads list."""
        api = SimulationsApi(self.api_client)
        spk_str = str(simulation_pk)
        downloads = []
        response = api.simulations_results_files_list(spk_str, limit=self.FETCH_LIMIT)
        response_count = response.count
        if response_count > self.FETCH_LIMIT:
            response = api.simulations_results_files_list(spk_str, limit=response_count)
        results_list = response.results
        for result_file in results_list:
            download = api.simulations_results_files_download(result_file.id, spk_str)
            downloads.append((result_file, download))
        return downloads

    def fetch_gridadmin_download(self, threedimodel_id: int) -> Tuple[ResultFile, Download]:
        """Fetch simulation model gridadmin file."""
        api = ThreedimodelsApi(self.api_client)
        result_file = ResultFile(filename="gridadmin.h5", created=datetime.utcnow())
        download = api.threedimodels_gridadmin_download(threedimodel_id)
        return result_file, download

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

    def add_breaches(self, simulation_pk: int, **data) -> Breach:
        """Add Breach to the given simulation."""
        api = SimulationsApi(self.api_client)
        breach = api.simulations_events_breaches_create((str(simulation_pk)), data)
        return breach

    def add_lateral_timeseries(self, simulation_pk: int, **data) -> TimeseriesLateral:
        """Add lateral_timeseries to the given simulation."""
        api = SimulationsApi(self.api_client)
        lateral_timeseries = api.simulations_events_lateral_timeseries_create((str(simulation_pk)), data)
        return lateral_timeseries

    def add_postprocessing_in_lizard_arrival(self, simulation_pk: int, **data) -> ArrivalTimePostProcessing:
        """Add add_postprocessing_in_lizard_arrival to the given simulation."""
        api = SimulationsApi(self.api_client)
        arrivalTimePostProcessing = api.simulations_results_post_processing_lizard_arrival_create((str(simulation_pk)), data)
        return arrivalTimePostProcessing

    def add_post_processing_lizard_basic(self, simulation_pk: int, **data) -> BasicPostProcessing:
        """Add add_post_processing_lizard_basic to the given simulation."""
        api = SimulationsApi(self.api_client)
        basicPostProcessing = api.simulations_results_post_processing_lizard_basic_create((str(simulation_pk)), data)
        return basicPostProcessing

    def add_post_processing_lizard_damage(self, simulation_pk: int, **data) -> DamagePostProcessing:
        """Add add_post_processing_lizard_damage to the given simulation."""
        api = SimulationsApi(self.api_client)
        basicPostProcessing = api.simulations_results_post_processing_lizard_damage_create((str(simulation_pk)), data)
        return basicPostProcessing

    def generate_saved_state_after_simulation(self, simulation_pk: int, **data) -> DamagePostProcessing:
        """Add generate_saved_state_after_simulation to the given simulation."""
        api = SimulationsApi(self.api_client)
        # todo call right api call simulations_create_saved_states_timed_create vs simulations_create_saved_states_stable_threshold_create
        basicPostProcessing = api.simulations_create_saved_states_timed_create((str(simulation_pk)), data)
        return basicPostProcessing

    def fetch_revisions(self) -> List[Revision]:
        """Fetch all Revisions available for current user."""
        api = RevisionsApi(self.api_client)
        response = api.revisions_list(limit=self.FETCH_LIMIT)
        response_count = response.count
        if response_count > self.FETCH_LIMIT:
            response = api.revisions_list(limit=response_count)
        revisions_list = response.results
        return revisions_list

    def fetch_revision_3di_models(self, rev_id: int) -> List[ThreediModel]:
        """Fetch all 3Di models belonging to given Revision."""
        api = RevisionsApi(self.api_client)
        revision_models_list = api.revisions_threedimodels(rev_id)
        return revision_models_list

    def fetch_organisations(self) -> List[Organisation]:
        """Fetch all Organisations available for current user."""
        api = OrganisationsApi(self.api_client)
        response = api.organisations_list(limit=self.FETCH_LIMIT)
        response_count = response.count
        if response_count > self.FETCH_LIMIT:
            response = api.organisations_list(limit=response_count)
        organisations = response.results
        return organisations
