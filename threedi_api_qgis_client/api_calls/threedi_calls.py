# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple, Callable, Any
from threedi_api_client import ThreediApi
from threedi_api_client.openapi import (
    ThreediModel,
    Repository,
    Simulation,
    Action,
    Progress,
    Revision,
    InitialWaterlevel,
    ConstantRain,
    TimeseriesRain,
    Organisation,
    CurrentStatus,
    ResultFile,
    Download,
    Breach,
    TimeseriesLateral,
    ArrivalTimePostProcessing,
    BasicPostProcessing,
    DamagePostProcessing,
    OneDWaterLevel,
    TwoDWaterLevel,
    OneDWaterLevelPredefined,
    TwoDWaterRaster,
    GroundWaterLevel,
    GroundWaterRaster,
    TimedSavedStateUpdate,
    ThreediModelSavedState,
    ThreediModelTask,
    InitialSavedState,
    PotentialBreach,
    LizardRasterRain,
    UploadEventFile,
    Upload,
    ConstantWind,
    TimeseriesWind,
    WindDragCoefficient,
    FileLateral,
    Schematisation,
    SchematisationRevision,
    SqliteFileUpload,
    RasterCreate,
    RevisionTask,
    RevisionRaster,
    Commit,
)


logger = logging.getLogger(__name__)


def get_api_client(api_username: str, api_password: str, api_host: str, version: str = "v3-beta") -> ThreediApi:
    """Setup open_api client using username and password."""
    os.environ["THREEDI_API_HOST"] = api_host
    os.environ["THREEDI_API_USERNAME"] = api_username
    os.environ["THREEDI_API_PASSWORD"] = api_password
    api_client = ThreediApi(version=version)
    return api_client


class ThreediCalls:
    """Class with methods used for the communication with the 3Di API."""

    FETCH_LIMIT = 250
    EXPIRATION_TIME = datetime.now(timezone.utc) - timedelta(days=7)

    def __init__(self, threedi_api: ThreediApi) -> None:
        self.threedi_api = threedi_api

    def paginated_fetch(self, api_method: Callable, *args, **kwargs) -> List[Any]:
        """Method for iterative fetching of the data via given API endpoint."""
        limit = self.FETCH_LIMIT
        logger.debug("Paginated fetch for %s...", api_method)
        response = api_method(*args, limit=limit, **kwargs)
        response_count = response.count
        results_list = response.results
        if response_count > limit:
            for offset in range(limit, response_count, limit):
                logger.debug("Another paginated fetch for %s...", api_method)
                response = api_method(*args, offset=offset, limit=limit, **kwargs)
                results_list += response.results
        return results_list

    def fetch_repositories(self) -> List[Repository]:
        """Fetch all repositories available for current user."""
        repositories_list = self.paginated_fetch(self.threedi_api.repositories_list)
        return repositories_list

    def fetch_simulations(self) -> List[Simulation]:
        """Fetch all simulations available for current user."""
        created__date__gt = self.EXPIRATION_TIME.strftime("%Y-%m-%d")
        simulations_list = self.paginated_fetch(self.threedi_api.simulations_list, created__date__gt=created__date__gt)
        return simulations_list

    def fetch_simulation(self, simulation_pk: int) -> Simulation:
        """Fetch single simulation."""
        logger.debug("Fetching single simulation %s...", simulation_pk)
        simulation = self.threedi_api.simulations_read(id=simulation_pk)
        return simulation

    def fetch_3di_models_with_count(
        self, limit: int = None, offset: int = None, name_contains: str = None
    ) -> Tuple[List[ThreediModel], int]:
        """Fetch 3Di models available for current user."""
        params = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if name_contains is not None:
            params["name__contains"] = name_contains.lower()
        logger.debug("Fetching 3di models for current user...")
        response = self.threedi_api.threedimodels_list(**params)
        models_list = response.results
        models_count = response.count
        return models_list, models_count

    def create_simulation(self, **simulation_data) -> Simulation:
        """Create a new Simulation."""
        sim = Simulation(**simulation_data)
        new_sim = self.threedi_api.simulations_create(sim)
        logger.info("Created new simulation")
        return new_sim

    def create_simulation_action(self, simulation_pk: int, **action_data) -> Action:
        """Make an action on 'simulation_pk' simulation."""
        action = self.threedi_api.simulations_actions_create(str(simulation_pk), action_data)
        return action

    def fetch_simulation_status(self, simulation_pk: int) -> CurrentStatus:
        """Get a given simulation current status."""
        logger.debug("Fetching simulation status for sim id %s...", str(simulation_pk))
        current_status = self.threedi_api.simulations_status_list(str(simulation_pk), limit=self.FETCH_LIMIT)
        return current_status

    def fetch_simulation_progress(self, simulation_pk: int) -> Progress:
        """Get a given simulation progress. Available only if simulation was already started."""
        logger.debug("Fetching simulation progress for sim id %s...", str(simulation_pk))
        simulations_progress = self.threedi_api.simulations_progress_list(str(simulation_pk), limit=self.FETCH_LIMIT)
        return simulations_progress

    def fetch_simulations_progresses(
        self, simulations_list: List[Simulation]
    ) -> Dict[int, Tuple[Simulation, CurrentStatus, Progress]]:
        """Get all simulations with statuses and progresses."""
        progresses = {}
        if not simulations_list:
            logger.warning("Simulations list not specified, we grab all simulations! ")
            simulations_list = self.fetch_simulations()
            if len(simulations_list) > 50:
                logger.warning("To prevent throttling, we limit the sim list to 50")
                simulations_list = simulations_list[:50]
        logger.info("Starting to grab sim statuses for %d simulations", len(simulations_list))
        for sim in simulations_list:
            spk = sim.id
            spk_str = str(spk)
            logger.debug("Fetching status for simulation %s", spk_str)
            current_status = self.threedi_api.simulations_status_list(spk_str, limit=self.FETCH_LIMIT)
            status_name = current_status.name
            status_time = current_status.time
            if status_time is None:
                status_time = 0
            if status_name == "initialized":
                sim_progress = self.threedi_api.simulations_progress_list(spk_str, limit=self.FETCH_LIMIT)
            elif status_name == "postprocessing" or status_name == "finished":
                sim_progress = Progress(percentage=100, time=status_time)
            else:
                sim_progress = Progress(percentage=0, time=status_time)
            progresses[spk] = (sim, current_status, sim_progress)
        return progresses

    def fetch_simulation_results(self, simulation_pk: int) -> List[ResultFile]:
        """Fetch simulation results list."""
        spk_str = str(simulation_pk)
        results_list = self.paginated_fetch(self.threedi_api.simulations_results_files_list, spk_str)
        return results_list

    def fetch_simulation_downloads(self, simulation_pk: int) -> List[Tuple[ResultFile, Download]]:
        """Fetch simulation downloads list."""
        spk_str = str(simulation_pk)
        downloads = []
        results_list = self.paginated_fetch(self.threedi_api.simulations_results_files_list, spk_str)
        for result_file in results_list:
            download = self.threedi_api.simulations_results_files_download(result_file.id, spk_str)
            downloads.append((result_file, download))
        return downloads

    def fetch_3di_model_geojson_cells_download(self, threedimodel_id: int) -> Download:
        """Fetch model geojson cells Download object."""
        logger.debug("Fetching cells json for model %s", threedimodel_id)
        cells_download = self.threedi_api.threedimodels_geojson_cells_download(threedimodel_id)
        return cells_download

    def fetch_3di_model_geojson_breaches_download(self, threedimodel_id: int) -> Download:
        """Fetch model geojson breaches Download object."""
        logger.debug("Fetching breaches json for model %s", threedimodel_id)
        breaches_download = self.threedi_api.threedimodels_geojson_breaches_download(threedimodel_id)
        return breaches_download

    def fetch_3di_model_gridadmin_download(self, threedimodel_id: int) -> Tuple[ResultFile, Download]:
        """Fetch simulation model gridadmin file."""
        logger.debug("Fetching gridadmin for model %s", threedimodel_id)
        result_file = ResultFile(filename="gridadmin.h5", created=datetime.utcnow())
        download = self.threedi_api.threedimodels_gridadmin_download(threedimodel_id)
        return result_file, download

    def fetch_3di_model_potential_breaches(self, threedimodel_id: str) -> List[PotentialBreach]:
        """Fetch breaches list."""
        breaches = self.paginated_fetch(self.threedi_api.threedimodels_potentialbreaches_list, threedimodel_id)
        return breaches

    def fetch_3di_model_potential_breach(self, threedimodel_id: str, content_pk: int = None) -> PotentialBreach:
        """Fetch a single potential breach."""
        params = {"threedimodel_pk": threedimodel_id}
        if content_pk is not None:
            params["connected_pnt_id"] = content_pk
        response = self.threedi_api.threedimodels_potentialbreaches_list(**params)
        breach = response.results[0]
        return breach

    def fetch_3di_model_initial_waterlevels(self, threedimodel_id: str) -> List[InitialWaterlevel]:
        """Fetch initial waterlevels List"""
        waterlevels = self.paginated_fetch(self.threedi_api.threedimodels_initial_waterlevels_list, threedimodel_id)
        return waterlevels

    def fetch_3di_model_saved_states(self, threedimodel_id: str) -> List[ThreediModelSavedState]:
        """Fetch saved states list."""
        states = self.paginated_fetch(self.threedi_api.threedimodels_saved_states_list, threedimodel_id)
        return states

    def fetch_3di_model_tasks(self, threedimodel_id: str) -> List[ThreediModelTask]:
        """Fetch tasks list."""
        tasks = self.paginated_fetch(self.threedi_api.threedimodels_tasks_list, threedimodel_id)
        return tasks

    def fetch_revisions(self) -> List[Revision]:
        """Fetch all Revisions available for current user."""
        revisions_list = self.paginated_fetch(self.threedi_api.revisions_list)
        return revisions_list

    def fetch_revision_3di_models(self, rev_id: int) -> List[ThreediModel]:
        """Fetch all 3Di models belonging to given Revision."""
        revision_models_list = self.threedi_api.revisions_threedimodels(rev_id)
        return revision_models_list

    def fetch_organisations(self) -> List[Organisation]:
        """Fetch all Organisations available for current user."""
        organisations = self.paginated_fetch(self.threedi_api.organisations_list)
        return organisations

    def create_simulation_constant_precipitation(self, simulation_pk: int, **rain_data) -> ConstantRain:
        """Add ConstantRain to the given simulation."""
        constant_rain = self.threedi_api.simulations_events_rain_constant_create(str(simulation_pk), rain_data)
        return constant_rain

    def create_simulation_custom_precipitation(self, simulation_pk: int, **rain_data) -> TimeseriesRain:
        """Add TimeseriesRain to the given simulation."""
        time_series_rain = self.threedi_api.simulations_events_rain_timeseries_create(str(simulation_pk), rain_data)
        return time_series_rain

    def create_simulation_custom_netcdf_precipitation(self, simulation_pk: int, **rain_data) -> Upload:
        """Add rain time series from NetCDF file to the given simulation."""
        netcdf_upload = self.threedi_api.simulations_events_rain_rasters_netcdf_create(str(simulation_pk), rain_data)
        return netcdf_upload

    def create_simulation_radar_precipitation(self, simulation_pk: int, **rain_data) -> LizardRasterRain:
        """Add LizardRasterRain to the given simulation."""
        time_series_rain = self.threedi_api.simulations_events_rain_rasters_lizard_create(str(simulation_pk), rain_data)
        return time_series_rain

    def create_simulation_breaches(self, simulation_pk: int, **data) -> Breach:
        """Add Breach to the given simulation."""
        breach = self.threedi_api.simulations_events_breaches_create(str(simulation_pk), data)
        return breach

    def create_simulation_lateral_timeseries(self, simulation_pk: int, **data) -> TimeseriesLateral:
        """Add lateral timeseries to the given simulation."""
        lateral_timeseries = self.threedi_api.simulations_events_lateral_timeseries_create(str(simulation_pk), data)
        return lateral_timeseries

    def create_simulation_lateral_file(self, simulation_pk: int, **data) -> UploadEventFile:
        """Add lateral file to the given simulation."""
        lateral_upload_file = self.threedi_api.simulations_events_lateral_file_create(str(simulation_pk), data)
        return lateral_upload_file

    def fetch_lateral_files(self, simulation_pk: int) -> List[FileLateral]:
        """Get list of the lateral files of the given simulation."""
        lateral_files_list = self.paginated_fetch(
            self.threedi_api.simulations_events_lateral_file_list, str(simulation_pk)
        )
        return lateral_files_list

    def create_simulation_postprocessing_in_lizard_arrival(
        self, simulation_pk: int, **data
    ) -> ArrivalTimePostProcessing:
        """Add add_postprocessing_in_lizard_arrival to the given simulation."""
        time_post_processing = self.threedi_api.simulations_results_post_processing_lizard_arrival_create(
            str(simulation_pk), data
        )
        return time_post_processing

    def create_simulation_post_processing_lizard_basic(self, simulation_pk: int, **data) -> BasicPostProcessing:
        """Add add_post_processing_lizard_basic to the given simulation."""
        basic_post_processing = self.threedi_api.simulations_results_post_processing_lizard_basic_create(
            str(simulation_pk), data
        )
        return basic_post_processing

    def create_simulation_post_processing_lizard_damage(self, simulation_pk: int, **data) -> DamagePostProcessing:
        """Add add_post_processing_lizard_damage to the given simulation."""
        dmg_post_processing = self.threedi_api.simulations_results_post_processing_lizard_damage_create(
            str(simulation_pk), data
        )
        return dmg_post_processing

    def create_simulation_saved_state_after_simulation(self, simulation_pk: int, **data) -> TimedSavedStateUpdate:
        """Add add_saved_state_after_simulation to the given simulation."""
        saved_state = self.threedi_api.simulations_create_saved_states_timed_create(str(simulation_pk), data)
        return saved_state

    def create_simulation_initial_1d_water_level_constant(self, simulation_pk: int, **data) -> OneDWaterLevel:
        """Add add_initial_1d_water_level_constant to the given simulation."""
        water_level_1d_const = self.threedi_api.simulations_initial1d_water_level_constant_create(
            str(simulation_pk), data
        )
        return water_level_1d_const

    def create_simulation_initial_1d_water_level_predefined(
        self, simulation_pk: int, **data
    ) -> OneDWaterLevelPredefined:
        """Add add_initial_1d_water_level_predefined to the given simulation."""
        water_level_1d_pred = self.threedi_api.simulations_initial1d_water_level_predefined_create(
            str(simulation_pk), data
        )
        return water_level_1d_pred

    def create_simulation_initial_2d_water_level_constant(self, simulation_pk: int, **data) -> TwoDWaterLevel:
        """Add add_initial_2d_water_level_constant to the given simulation."""
        water_level_2d_const = self.threedi_api.simulations_initial2d_water_level_constant_create(
            str(simulation_pk), data
        )
        return water_level_2d_const

    def create_simulation_initial_2d_water_level_raster(self, simulation_pk: int, **data) -> TwoDWaterRaster:
        """Add add_initial_2d_water_level_raster to the given simulation."""
        water_level_2d_raster = self.threedi_api.simulations_initial2d_water_level_raster_create(
            str(simulation_pk), data
        )
        return water_level_2d_raster

    def create_simulation_initial_groundwater_level_constant(self, simulation_pk: int, **data) -> GroundWaterLevel:
        """Add add_initial_groundwater_level_constant to the given simulation."""
        groundwater_const = self.threedi_api.simulations_initial_groundwater_level_constant_create(
            str(simulation_pk), data
        )
        return groundwater_const

    def create_simulation_initial_groundwater_level_raster(self, simulation_pk: int, **data) -> GroundWaterRaster:
        """Add add_initial_groundwater_level_raster to the given simulation."""
        groundwater_raster = self.threedi_api.simulations_initial_groundwater_level_raster_create(
            str(simulation_pk), data
        )
        return groundwater_raster

    def create_simulation_initial_saved_state(self, simulation_pk: int, **data) -> InitialSavedState:
        """Add initial saved state to the given simulation."""
        initial_saved_state = self.threedi_api.simulations_initial_saved_state_create(str(simulation_pk), data)
        return initial_saved_state

    def create_simulation_initial_wind_drag_coefficient(self, simulation_pk: int, **data) -> WindDragCoefficient:
        """Add initial wind drag coefficient to the given simulation."""
        initial_wind_drag_coefficient = self.threedi_api.simulations_initial_wind_drag_coefficient_create(
            str(simulation_pk), data
        )
        return initial_wind_drag_coefficient

    def create_simulation_constant_wind(self, simulation_pk: int, **wind_data) -> ConstantWind:
        """Add ConstantWind to the given simulation."""
        constant_wind = self.threedi_api.simulations_events_wind_constant_create(str(simulation_pk), wind_data)
        return constant_wind

    def create_simulation_custom_wind(self, simulation_pk: int, **wind_data) -> TimeseriesWind:
        """Add TimeseriesWind to the given simulation."""
        time_series_wind = self.threedi_api.simulations_events_wind_timeseries_create((str(simulation_pk)), wind_data)
        return time_series_wind

    # V3-beta API methods
    def fetch_schematisations(self, **data) -> List[Schematisation]:
        schematisations_list = self.paginated_fetch(self.threedi_api.schematisations_list, **data)
        return schematisations_list

    def fetch_schematisation(self, schematisation_pk: int, **data) -> Schematisation:
        schematisation = self.threedi_api.schematisations_read(id=schematisation_pk, **data)
        return schematisation

    def create_schematisation(self, name: str, owner: str, **data) -> Schematisation:
        data.update({"name": name, "owner": owner})
        schematisation = self.threedi_api.schematisations_create(data)
        return schematisation

    def fetch_schematisation_revisions(self, schematisation_pk: int, **data) -> List[SchematisationRevision]:
        schematisation_revisions = self.paginated_fetch(
            self.threedi_api.schematisations_revisions_list, schematisation_pk, **data
        )
        return schematisation_revisions

    def fetch_schematisation_revision(self, schematisation_pk: int, revision_pk: int) -> SchematisationRevision:
        schematisation_revision = self.threedi_api.schematisations_revisions_read(revision_pk, schematisation_pk)
        return schematisation_revision

    def fetch_schematisation_latest_revision(self, schematisation_pk: int) -> SchematisationRevision:
        schematisation_revision = self.threedi_api.schematisations_latest_revision(schematisation_pk)
        return schematisation_revision

    def create_schematisation_revision(
        self, schematisation_pk: int, empty: bool = True, **data
    ) -> SchematisationRevision:
        data["empty"] = empty
        schematisation_revision = self.threedi_api.schematisations_revisions_create(schematisation_pk, data)
        return schematisation_revision

    def upload_schematisation_revision_sqlite(
        self, schematisation_pk: int, revision_pk: int, filename: str, **data
    ) -> SqliteFileUpload:
        data["filename"] = filename
        sqlite_file_upload = self.threedi_api.schematisations_revisions_sqlite_upload(
            revision_pk, schematisation_pk, data
        )
        return sqlite_file_upload

    def delete_schematisation_revision_sqlite(self, schematisation_pk: int, revision_pk: int):
        self.threedi_api.schematisations_revisions_sqlite_delete(revision_pk, schematisation_pk)

    def fetch_schematisation_revision_rasters(self, schematisation_pk: int, revision_pk: int) -> List[RevisionRaster]:
        revision_rasters_list = self.paginated_fetch(
            self.threedi_api.schematisations_revisions_rasters_list, revision_pk, schematisation_pk
        )
        return revision_rasters_list

    def create_schematisation_revision_raster(
        self, schematisation_pk: int, revision_pk: int, name: str, raster_type: str = "dem_raw_file", **data
    ) -> RasterCreate:
        raster_type = "dem_raw_file" if raster_type == "dem_file" else raster_type
        data.update({"name": name, "type": raster_type})
        raster_create = self.threedi_api.schematisations_revisions_rasters_create(
            revision_pk, schematisation_pk, data
        )
        return raster_create

    def upload_schematisation_revision_raster(
        self, raster_pk: int, schematisation_pk: int, revision_pk: int, filename: str
    ) -> Upload:
        data = {"filename": filename}
        raster_file_upload = self.threedi_api.schematisations_revisions_rasters_upload(
            raster_pk, revision_pk, schematisation_pk, data
        )
        return raster_file_upload

    def delete_schematisation_revision_raster(self, raster_pk: int, schematisation_pk: int, revision_pk: int):
        self.threedi_api.schematisations_revisions_rasters_delete(raster_pk, revision_pk, schematisation_pk)

    def commit_schematisation_revision(self, schematisation_pk: int, revision_pk: int, **data) -> Commit:
        commit = self.threedi_api.schematisations_revisions_commit(revision_pk, schematisation_pk, data)
        return commit

    def create_schematisation_revision_3di_model(
        self, schematisation_pk: int, revision_pk: int, **data
    ) -> ThreediModel:
        threedi_model = self.threedi_api.schematisations_revisions_create_threedimodel(
            revision_pk, schematisation_pk, data
        )
        return threedi_model

    def fetch_schematisation_revision_tasks(self, schematisation_pk: int, revision_pk: int) -> List[RevisionTask]:
        revision_tasks_list = self.paginated_fetch(
            self.threedi_api.schematisations_revisions_tasks_list, revision_pk, schematisation_pk
        )
        return revision_tasks_list
