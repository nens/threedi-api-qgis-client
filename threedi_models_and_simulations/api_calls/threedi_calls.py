# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import logging
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
    FileStructureControl,
    MemoryStructureControl,
    TableStructureControl,
    TimedStructureControl,
    FileBoundaryCondition,
    FileLateral,
    Schematisation,
    SchematisationRevision,
    SqliteFileUpload,
    RasterCreate,
    RevisionTask,
    RevisionRaster,
    Commit,
    Template,
    SimulationSettingsOverview,
    PhysicalSettings,
    NumericalSettings,
    TimeStepSettings,
    AggregationSettings,
    Event,
    User,
    Raster,
    Contract,
)


logger = logging.getLogger(__name__)


def get_api_client(api_username: str, api_password: str, api_host: str, version: str = "v3-beta") -> ThreediApi:
    """Setup 3Di API Client using username and password."""
    config = {
        "THREEDI_API_HOST": api_host,
        "THREEDI_API_USERNAME": api_username,
        "THREEDI_API_PASSWORD": api_password,
    }
    api_client = ThreediApi(config=config, version=version)
    return api_client


def get_api_client_with_tokens(
    api_host: str, api_access_token: str, api_refresh_token: str, version: str = "v3-beta"
) -> ThreediApi:
    """Setup 3Di API Client using access and refresh tokens."""
    config = {
        "THREEDI_API_HOST": api_host,
        "THREEDI_API_ACCESS_TOKEN": api_access_token,
        "THREEDI_API_REFRESH_TOKEN": api_refresh_token,
    }
    api_client = ThreediApi(config=config, version=version)
    return api_client


def get_api_client_with_personal_api_token(
    personal_api_token: str, api_host: str, version: str = "v3-beta"
) -> ThreediApi:
    """Setup 3Di API Client using Personal API Token."""
    config = {
        "THREEDI_API_HOST": api_host,
        "THREEDI_API_USERNAME": "__key__",
        "THREEDI_API_PERSONAL_API_TOKEN": personal_api_token,
    }
    api_client = ThreediApi(config=config, version=version)
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

    def fetch_current_user(self) -> User:
        """Fetch current user instance."""
        user = self.threedi_api.auth_profile_list()
        return user

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
        self,
        limit: int = None,
        offset: int = None,
        name_contains: str = None,
        schematisation_name: str = None,
        schematisation_owner: str = None,
        show_invalid: bool = False,
    ) -> Tuple[List[ThreediModel], int]:
        """Fetch 3Di models available for current user."""
        params = {"revision__schematisation__isnull": False}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if name_contains is not None:
            params["name__icontains"] = name_contains.lower()
        if schematisation_name is not None:
            params["revision__schematisation__name"] = schematisation_name
        if schematisation_owner is not None:
            params["revision__schematisation__owner__unique_id"] = schematisation_owner
        if show_invalid:
            params["is_valid"] = ""
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

    def fetch_3di_model(self, threedimodel_id: int) -> ThreediModel:
        """Fetch 3Di model with a given id."""
        logger.debug("Fetching model %s", threedimodel_id)
        threedi_model = self.threedi_api.threedimodels_read(threedimodel_id)
        return threedi_model

    def delete_3di_model(self, threedimodel_id: int) -> None:
        """Delete 3Di model with a given id."""
        logger.debug("Deleting model %s", threedimodel_id)
        self.threedi_api.threedimodels_delete(threedimodel_id)

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

    def fetch_3di_model_point_potential_breach(self, threedimodel_id: str, content_pk: int = None) -> PotentialBreach:
        """Fetch a single potential breach at given connected_pnt_id."""
        params = {"threedimodel_pk": threedimodel_id}
        if content_pk is not None:
            params["connected_pnt_id"] = content_pk
        response = self.threedi_api.threedimodels_potentialbreaches_list(**params)
        breach = response.results[0]
        return breach

    def fetch_3di_model_potential_breach(self, threedimodel_id: str, breach_pk: int) -> PotentialBreach:
        """Fetch a single potential breach with given id."""
        breach = self.threedi_api.threedimodels_potentialbreaches_read(breach_pk, threedimodel_id)
        return breach

    def fetch_3di_model_initial_waterlevels(self, threedimodel_id: str) -> List[InitialWaterlevel]:
        """Fetch initial water levels list"""
        water_levels = self.paginated_fetch(self.threedi_api.threedimodels_initial_waterlevels_list, threedimodel_id)
        return water_levels

    def fetch_3di_model_initial_waterlevel(self, threedimodel_id: str, water_level_id: int) -> InitialWaterlevel:
        """Fetch initial water level with given id"""
        water_level = self.threedi_api.threedimodels_initial_waterlevels_read(water_level_id, threedimodel_id)
        return water_level

    def fetch_3di_model_raster(self, threedimodel_id: str, raster_id: int) -> Raster:
        """Fetch raster with given id"""
        raster = self.threedi_api.threedimodels_rasters_read(raster_id, threedimodel_id)
        return raster

    def fetch_3di_model_saved_states(self, threedimodel_id: str) -> List[ThreediModelSavedState]:
        """Fetch saved states list."""
        states = self.paginated_fetch(self.threedi_api.threedimodels_saved_states_list, threedimodel_id)
        return states

    def fetch_3di_model_tasks(self, threedimodel_id: str) -> List[ThreediModelTask]:
        """Fetch 3Di model tasks list."""
        tasks = self.paginated_fetch(self.threedi_api.threedimodels_tasks_list, threedimodel_id)
        return tasks

    def fetch_3di_model_task(self, threedimodel_id: str, task_id: int) -> ThreediModelTask:
        """Fetch 3Di model task with given ID."""
        task = self.threedi_api.threedimodels_tasks_read(task_id, threedimodel_id)
        return task

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

    def fetch_lateral_files(self, simulation_pk: int) -> List[FileLateral]:
        """Get list of the lateral files of the given simulation."""
        lateral_files_list = self.paginated_fetch(
            self.threedi_api.simulations_events_lateral_file_list, str(simulation_pk)
        )
        return lateral_files_list

    def fetch_lateral_file(self, simulation_pk: int, lateral_pk: int) -> FileLateral:
        """Get a laterals file with given id."""
        lateral_file = self.threedi_api.simulations_events_lateral_file_read(lateral_pk, str(simulation_pk))
        return lateral_file

    def fetch_lateral_file_download(self, simulation_pk: int, lateral_pk: int) -> Download:
        """Get the lateral file Download object."""
        lateral_download = self.threedi_api.simulations_events_lateral_file_download(lateral_pk, str(simulation_pk))
        return lateral_download

    def fetch_structure_control_files(self, simulation_pk: int) -> List[FileStructureControl]:
        """Get list of the structure control files of the given simulation."""
        sc_files_list = self.paginated_fetch(
            self.threedi_api.simulations_events_structure_control_file_list, str(simulation_pk)
        )
        return sc_files_list

    def fetch_structure_control_file(self, simulation_pk: int, sc_pk: int) -> FileStructureControl:
        """Get a structure control file with given id."""
        sc_file = self.threedi_api.simulations_events_structure_control_file_read(sc_pk, str(simulation_pk))
        return sc_file

    def fetch_structure_control_file_download(self, simulation_pk: int, sc_pk: int) -> Download:
        """Get a structure control file Download object."""
        sc_download = self.threedi_api.simulations_events_structure_control_file_download(sc_pk, str(simulation_pk))
        return sc_download

    def create_simulation_structure_control_file(self, simulation_pk: int, **data) -> Upload:
        """Add structure control file to the given simulation."""
        sc_upload_file = self.threedi_api.simulations_events_structure_control_file_create(str(simulation_pk), data)
        return sc_upload_file

    def create_simulation_structure_control_memory(self, simulation_pk: int, **data) -> MemoryStructureControl:
        """Add memory structure control to the given simulation."""
        sc_memory = self.threedi_api.simulations_events_structure_control_memory_create(str(simulation_pk), data)
        return sc_memory

    def create_simulation_structure_control_table(self, simulation_pk: int, **data) -> TableStructureControl:
        """Add table structure control to the given simulation."""
        sc_table = self.threedi_api.simulations_events_structure_control_table_create(str(simulation_pk), data)
        return sc_table

    def create_simulation_structure_control_timed(self, simulation_pk: int, **data) -> TimedStructureControl:
        """Add timed structure control to the given simulation."""
        sc_timed = self.threedi_api.simulations_events_structure_control_timed_create(str(simulation_pk), data)
        return sc_timed

    def fetch_boundarycondition_files(self, simulation_pk: int) -> List[FileBoundaryCondition]:
        """Get list of the boundary condition files of the given simulation."""
        bc_files_list = self.paginated_fetch(
            self.threedi_api.simulations_events_boundaryconditions_file_list, str(simulation_pk)
        )
        return bc_files_list

    def fetch_boundarycondition_file(self, simulation_pk: int, bc_pk: int) -> FileBoundaryCondition:
        """Get a boundary condition file with given id."""
        bc_file = self.threedi_api.simulations_events_boundaryconditions_file_read(bc_pk, str(simulation_pk))
        return bc_file

    def fetch_boundarycondition_file_download(self, simulation_pk: int, bc_pk: int) -> Download:
        """Get a boundary condition file Download object."""
        bc_download = self.threedi_api.simulations_events_boundaryconditions_file_download(bc_pk, str(simulation_pk))
        return bc_download

    def create_simulation_boundarycondition_file(self, simulation_pk: int, **data) -> Upload:
        """Add boundary conditions file to the given simulation."""
        bc_upload_file = self.threedi_api.simulations_events_boundaryconditions_file_create(str(simulation_pk), data)
        return bc_upload_file

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

    def create_initial_water_level(self, threedimodel_id: str, **data) -> InitialWaterlevel:
        """Add initial water level to the given 3Di model."""
        initial_water_level = self.threedi_api.threedimodels_initial_waterlevels_create(threedimodel_id, data)
        return initial_water_level

    def upload_initial_water_level(self, threedimodel_id: str, water_level_id: int, **data) -> Upload:
        """Upload initial water level for the given 3Di model."""
        initial_water_level_upload = self.threedi_api.threedimodels_initial_waterlevels_upload(
            water_level_id, threedimodel_id, data
        )
        return initial_water_level_upload

    def create_3di_model_raster(self, threedimodel_id: str, **data) -> Raster:
        """Create raster for the given 3Di model."""
        raster = self.threedi_api.threedimodels_rasters_create(threedimodel_id, data)
        return raster

    def upload_3di_model_raster(self, threedimodel_id: str, raster_id: int, **data) -> Upload:
        """Upload raster to the given 3Di model."""
        raster_upload = self.threedi_api.threedimodels_rasters_upload(raster_id, threedimodel_id, data)
        return raster_upload

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

    def update_simulation_constant_precipitation(self, event_id: int, simulation_pk: int, **rain_data) -> None:
        """Update ConstantRain of the given simulation."""
        self.threedi_api.simulations_events_rain_constant_partial_update(event_id, str(simulation_pk), rain_data)

    def update_simulation_custom_precipitation(self, event_id: int, simulation_pk: int, **rain_data) -> None:
        """Update TimeseriesRain of the given simulation."""
        self.threedi_api.simulations_events_rain_timeseries_partial_update(event_id, str(simulation_pk), rain_data)

    def update_simulation_custom_netcdf_precipitation(self, event_id: int, simulation_pk: int, **rain_data) -> None:
        """Update rain time series from NetCDF file of the given simulation."""
        self.threedi_api.simulations_events_rain_rasters_netcdf_partial_update(event_id, str(simulation_pk), rain_data)

    def update_simulation_radar_precipitation(self, event_id: int, simulation_pk: int, **rain_data) -> None:
        """Update LizardRasterRain of the given simulation."""
        self.threedi_api.simulations_events_rain_rasters_lizard_partial_update(event_id, str(simulation_pk), rain_data)

    def update_simulation_breaches(self, event_id: int, simulation_pk: int, **data) -> None:
        """Update Breach of the given simulation."""
        self.threedi_api.simulations_events_breaches_partial_update(event_id, str(simulation_pk), data)

    def update_simulation_lateral_timeseries(self, event_id: int, simulation_pk: int, **data) -> None:
        """Update lateral timeseries of the given simulation."""
        self.threedi_api.simulations_events_lateral_timeseries_partial_update(event_id, str(simulation_pk), data)

    def update_simulation_lateral_file(self, event_id: int, simulation_pk: int, **data) -> None:
        """Update lateral file of the given simulation."""
        self.threedi_api.simulations_events_lateral_file_partial_update(event_id, str(simulation_pk), data)

    def update_simulation_initial_1d_water_level_constant(
        self, initial_id: int, simulation_pk: int, **data
    ) -> OneDWaterLevel:
        """Update add_initial_1d_water_level_constant of the given simulation."""
        water_level_1d_const = self.threedi_api.simulations_initial1d_water_level_constant_partial_update(
            initial_id, str(simulation_pk), data
        )
        return water_level_1d_const

    def update_simulation_initial_1d_water_level_predefined(
        self, initial_id: int, simulation_pk: int, **data
    ) -> OneDWaterLevelPredefined:
        """Update add_initial_1d_water_level_predefined of the given simulation."""
        water_level_1d_pred = self.threedi_api.simulations_initial1d_water_level_predefined_partial_update(
            initial_id, str(simulation_pk), data
        )
        return water_level_1d_pred

    def update_simulation_initial_2d_water_level_constant(
        self, initial_id: int, simulation_pk: int, **data
    ) -> TwoDWaterLevel:
        """Update add_initial_2d_water_level_constant of the given simulation."""
        water_level_2d_const = self.threedi_api.simulations_initial2d_water_level_constant_partial_update(
            initial_id, str(simulation_pk), data
        )
        return water_level_2d_const

    def update_simulation_initial_2d_water_level_raster(
        self, initial_id: int, simulation_pk: int, **data
    ) -> TwoDWaterRaster:
        """Update add_initial_2d_water_level_raster of the given simulation."""
        water_level_2d_raster = self.threedi_api.simulations_initial2d_water_level_raster_partial_update(
            initial_id, str(simulation_pk), data
        )
        return water_level_2d_raster

    def update_simulation_initial_groundwater_level_constant(
        self, initial_id: int, simulation_pk: int, **data
    ) -> GroundWaterLevel:
        """Update add_initial_groundwater_level_constant of the given simulation."""
        groundwater_const = self.threedi_api.simulations_initial_groundwater_level_constant_partial_update(
            initial_id, str(simulation_pk), data
        )
        return groundwater_const

    def update_simulation_initial_groundwater_level_raster(
        self, initial_id: int, simulation_pk: int, **data
    ) -> GroundWaterRaster:
        """Update add_initial_groundwater_level_raster of the given simulation."""
        groundwater_raster = self.threedi_api.simulations_initial_groundwater_level_raster_partial_update(
            initial_id, str(simulation_pk), data
        )
        return groundwater_raster

    def update_simulation_initial_saved_state(self, initial_id: int, simulation_pk: int, **data) -> InitialSavedState:
        """Update initial saved state of the given simulation."""
        initial_saved_state = self.threedi_api.simulations_initial_saved_state_partial_update(
            initial_id, str(simulation_pk), data
        )
        return initial_saved_state

    def update_simulation_initial_wind_drag_coefficient(
        self, initial_id: int, simulation_pk: int, **data
    ) -> WindDragCoefficient:
        """Update initial wind drag coefficient of the given simulation."""
        initial_wind_drag_coefficient = self.threedi_api.simulations_initial_wind_drag_coefficient_partial_update(
            initial_id, str(simulation_pk), data
        )
        return initial_wind_drag_coefficient

    def update_simulation_constant_wind(self, event_id: int, simulation_pk: int, **wind_data) -> ConstantWind:
        """Update ConstantWind of the given simulation."""
        constant_wind = self.threedi_api.simulations_events_wind_constant_partial_update(
            event_id, str(simulation_pk), wind_data
        )
        return constant_wind

    def update_simulation_custom_wind(self, event_id: int, simulation_pk: int, **wind_data) -> TimeseriesWind:
        """Update TimeseriesWind of the given simulation."""
        time_series_wind = self.threedi_api.simulations_events_wind_timeseries_partial_update(
            event_id, (str(simulation_pk)), wind_data
        )
        return time_series_wind

    # V3-beta API methods
    def fetch_schematisations(self, **data) -> List[Schematisation]:
        """Get list of the schematisations."""
        schematisations_list = self.paginated_fetch(self.threedi_api.schematisations_list, **data)
        return schematisations_list

    def fetch_schematisations_with_count(
        self, limit: int = None, offset: int = None, name_contains: str = None
    ) -> Tuple[List[Schematisation], int]:
        """Get list of the schematisations with count."""
        params = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if name_contains is not None:
            params["name__icontains"] = name_contains.lower()
        logger.debug("Fetching schematisations...")
        response = self.threedi_api.schematisations_list(**params)
        schematisations_list = response.results
        schematisations_count = response.count
        return schematisations_list, schematisations_count

    def fetch_schematisation(self, schematisation_pk: int, **data) -> Schematisation:
        """Get schematisation with given id."""
        schematisation = self.threedi_api.schematisations_read(id=schematisation_pk, **data)
        return schematisation

    def create_schematisation(self, name: str, owner: str, **data) -> Schematisation:
        """Create a new schematisation."""
        data.update({"name": name, "owner": owner})
        schematisation = self.threedi_api.schematisations_create(data)
        return schematisation

    def fetch_schematisation_revisions(
        self, schematisation_pk: int, committed: bool = True, **data
    ) -> List[SchematisationRevision]:
        """Get list of the schematisation revisions."""
        schematisation_revisions = self.paginated_fetch(
            self.threedi_api.schematisations_revisions_list, schematisation_pk, committed=committed, **data
        )
        return schematisation_revisions

    def fetch_schematisation_revisions_with_count(
        self,
        schematisation_pk: int,
        committed: bool = True,
        limit: int = None,
        offset: int = None,
    ) -> Tuple[List[SchematisationRevision], int]:
        """Get list of the schematisation revisions with count."""
        params = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        logger.debug("Fetching schematisations...")
        response = self.threedi_api.schematisations_revisions_list(schematisation_pk, committed=committed, **params)
        schematisation_revisions_list = response.results
        schematisation_revisions_count = response.count
        return schematisation_revisions_list, schematisation_revisions_count

    def fetch_schematisation_revision(self, schematisation_pk: int, revision_pk: int) -> SchematisationRevision:
        """Get schematisation revision."""
        schematisation_revision = self.threedi_api.schematisations_revisions_read(revision_pk, schematisation_pk)
        return schematisation_revision

    def fetch_schematisation_latest_revision(self, schematisation_pk: int) -> SchematisationRevision:
        """Get latest schematisation revision."""
        schematisation_revision = self.threedi_api.schematisations_latest_revision(schematisation_pk)
        return schematisation_revision

    def create_schematisation_revision(
        self, schematisation_pk: int, empty: bool = False, **data
    ) -> SchematisationRevision:
        """Create a new schematisation revision."""
        data["empty"] = empty
        schematisation_revision = self.threedi_api.schematisations_revisions_create(schematisation_pk, data)
        return schematisation_revision

    def download_schematisation_revision_sqlite(self, schematisation_pk: int, revision_pk: int) -> Download:
        """Get schematisation revision sqlite Download object."""
        sqlite_download = self.threedi_api.schematisations_revisions_sqlite_download(revision_pk, schematisation_pk)
        return sqlite_download

    def upload_schematisation_revision_sqlite(
        self, schematisation_pk: int, revision_pk: int, filename: str, **data
    ) -> SqliteFileUpload:
        """Create a new schematisation revision SqliteFileUpload."""
        data["filename"] = filename
        sqlite_file_upload = self.threedi_api.schematisations_revisions_sqlite_upload(
            revision_pk, schematisation_pk, data
        )
        return sqlite_file_upload

    def delete_schematisation_revision_sqlite(self, schematisation_pk: int, revision_pk: int):
        """Remove schematisation revision sqlite file."""
        self.threedi_api.schematisations_revisions_sqlite_delete(revision_pk, schematisation_pk)

    def fetch_schematisation_revision_rasters(self, schematisation_pk: int, revision_pk: int) -> List[RevisionRaster]:
        """Get list of the schematisation revision rasters."""
        revision_rasters_list = self.paginated_fetch(
            self.threedi_api.schematisations_revisions_rasters_list, revision_pk, schematisation_pk
        )
        return revision_rasters_list

    def create_schematisation_revision_raster(
        self, schematisation_pk: int, revision_pk: int, name: str, raster_type: str = "dem_file", **data
    ) -> RasterCreate:
        """Create a new schematisation revision raster."""
        raster_type = "dem_file" if raster_type == "dem_raw_file" else raster_type
        data.update({"name": name, "type": raster_type})
        raster_create = self.threedi_api.schematisations_revisions_rasters_create(revision_pk, schematisation_pk, data)
        return raster_create

    def upload_schematisation_revision_raster(
        self, raster_pk: int, schematisation_pk: int, revision_pk: int, filename: str
    ) -> Upload:
        """Create a new schematisation revision raster Upload object."""
        data = {"filename": filename}
        raster_file_upload = self.threedi_api.schematisations_revisions_rasters_upload(
            raster_pk, revision_pk, schematisation_pk, data
        )
        return raster_file_upload

    def delete_schematisation_revision_raster(self, raster_pk: int, schematisation_pk: int, revision_pk: int):
        """Remove schematisation revision raster."""
        self.threedi_api.schematisations_revisions_rasters_delete(raster_pk, revision_pk, schematisation_pk)

    def download_schematisation_revision_raster(
        self, raster_pk: int, schematisation_pk: int, revision_pk: int
    ) -> Download:
        """Download schematisation revision raster."""
        raster_download = self.threedi_api.schematisations_revisions_rasters_download(
            raster_pk, revision_pk, schematisation_pk
        )
        return raster_download

    def commit_schematisation_revision(self, schematisation_pk: int, revision_pk: int, **data) -> Commit:
        """Commit schematisation revision."""
        commit = self.threedi_api.schematisations_revisions_commit(revision_pk, schematisation_pk, data)
        return commit

    def fetch_schematisation_revision_3di_models(self, schematisation_pk: int, revision_pk: int) -> List[ThreediModel]:
        """Fetch 3Di models belonging to the particular schematisation revision."""
        threedi_models = self.threedi_api.schematisations_revisions_threedimodels(revision_pk, schematisation_pk)
        return threedi_models

    def create_schematisation_revision_3di_model(self, schematisation_pk: int, revision_pk: int) -> ThreediModel:
        """Create a new 3Di model out of committed revision."""
        threedi_model = self.threedi_api.schematisations_revisions_create_threedimodel(revision_pk, schematisation_pk)
        return threedi_model

    def fetch_schematisation_revision_tasks(self, schematisation_pk: int, revision_pk: int) -> List[RevisionTask]:
        """Get list of the schematisation revision tasks."""
        revision_tasks_list = self.paginated_fetch(
            self.threedi_api.schematisations_revisions_tasks_list, revision_pk, schematisation_pk
        )
        return revision_tasks_list

    def fetch_schematisation_revision_task(
        self, task_pk: int, schematisation_pk: int, revision_pk: int
    ) -> RevisionTask:
        """Get schematisation revision task."""
        revision_task = self.threedi_api.schematisations_revisions_tasks_read(task_pk, revision_pk, schematisation_pk)
        return revision_task

    def fetch_simulation_templates(self, **params) -> List[Template]:
        """Get list of the simulation templates."""
        simulation_templates_list = self.paginated_fetch(self.threedi_api.simulation_templates_list, **params)
        return simulation_templates_list

    def fetch_simulation_templates_with_count(
        self, simulation_pk: int = None, limit: int = None, offset: int = None
    ) -> Tuple[List[Template], int]:
        """Get list of the simulation templated with count."""
        params = {}
        if simulation_pk is not None:
            params["simulation__threedimodel__id"] = simulation_pk
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        logger.debug("Fetching simulation templates...")
        response = self.threedi_api.simulation_templates_list(**params)
        simulation_templates_list = response.results
        simulation_templates_count = response.count
        return simulation_templates_list, simulation_templates_count

    def fetch_simulation_template(self, template_pk: int) -> Template:
        """Get a simulation template with given id."""
        simulation_template = self.threedi_api.simulation_templates_read(id=template_pk)
        return simulation_template

    def delete_simulation_template(self, template_pk: int):
        """Delete a simulation template with given id."""
        self.threedi_api.simulation_templates_delete(id=template_pk)

    def create_template_from_simulation(self, name: str, simulation_pk: str, **data) -> Template:
        """Create simulation template out of the simulation."""
        data.update({"name": name, "simulation": simulation_pk})
        simulation_template = self.threedi_api.simulation_templates_create(data)
        return simulation_template

    def create_simulation_from_template(
        self, template: str, name: str, organisation: str, start_datetime: str, end_datetime: str, **data
    ) -> Simulation:
        """Create simulation out of the simulation template."""
        data.update(
            {
                "name": name,
                "template": template,
                "organisation": organisation,
                "start_datetime": start_datetime,
                "end_datetime": end_datetime,
            }
        )
        simulation = self.threedi_api.simulations_from_template(data)
        return simulation

    def fetch_simulation_settings_overview(self, simulation_pk: str) -> SimulationSettingsOverview:
        """Get a simulation settings overview."""
        simulation_settings_overview = self.threedi_api.simulations_settings_overview(simulation_pk=simulation_pk)
        return simulation_settings_overview

    def fetch_simulation_events(self, simulation_pk: int) -> Event:
        """Get a simulation events collection."""
        simulation_events = self.threedi_api.simulations_events(id=simulation_pk)
        return simulation_events

    def create_simulation_settings_physical(self, simulation_pk: int, **data) -> PhysicalSettings:
        """Create a simulation physical settings."""
        simulation_settings_physical = self.threedi_api.simulations_settings_physical_create(str(simulation_pk), data)
        return simulation_settings_physical

    def create_simulation_settings_numerical(self, simulation_pk: int, **data) -> NumericalSettings:
        """Create a simulation numerical settings."""
        simulation_settings_numerical = self.threedi_api.simulations_settings_numerical_create(str(simulation_pk), data)
        return simulation_settings_numerical

    def create_simulation_settings_time_step(self, simulation_pk: int, **data) -> TimeStepSettings:
        """Create a simulation time step settings."""
        simulation_settings_time_step = self.threedi_api.simulations_settings_time_step_create(str(simulation_pk), data)
        return simulation_settings_time_step

    def create_simulation_settings_aggregation(self, simulation_pk: int, **data) -> AggregationSettings:
        """Create a simulation aggregation settings."""
        simulations_settings_aggregation = self.threedi_api.simulations_settings_aggregation_create(
            str(simulation_pk), data
        )
        return simulations_settings_aggregation

    def update_simulation_settings_physical(self, simulation_pk: int, **data) -> None:
        """Update a simulation physical settings."""
        self.threedi_api.simulations_settings_physical_partial_update(str(simulation_pk), data)

    def update_simulation_settings_numerical(self, simulation_pk: int, **data) -> None:
        """Update a simulation numerical settings."""
        self.threedi_api.simulations_settings_numerical_partial_update(str(simulation_pk), data)

    def update_simulation_settings_time_step(self, simulation_pk: int, **data) -> None:
        """Update a simulation time step settings."""
        self.threedi_api.simulations_settings_time_step_partial_update(str(simulation_pk), data)

    def update_simulation_settings_aggregation(self, setting_id: int, simulation_pk: int, **data) -> None:
        """Update a simulation aggregation settings."""
        self.threedi_api.simulations_settings_aggregation_partial_update(setting_id, str(simulation_pk), data)

    def fetch_contracts(self, **data) -> List[Contract]:
        """Get valid 3Di contracts list."""
        contracts_list = self.paginated_fetch(self.threedi_api.contracts_list, **data)
        return contracts_list
