# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import base64
import json
import logging
import os
import time
from functools import partial

import requests
from PyQt5 import QtWebSockets
from PyQt5.QtNetwork import QNetworkRequest
from qgis.PyQt.QtCore import QByteArray, QObject, QRunnable, QUrl, pyqtSignal, pyqtSlot
from threedi_api_client.files import upload_file
from threedi_api_client.openapi import ApiException
from threedi_mi_utils import bypass_max_path_limit

from .api_calls.threedi_calls import ThreediCalls
from .data_models import simulation_data_models as dm
from .data_models.enumerators import SimulationStatusName
from .utils import (
    API_DATETIME_FORMAT,
    BOUNDARY_CONDITIONS_TEMPLATE,
    CHUNK_SIZE,
    DWF_FILE_TEMPLATE,
    LATERALS_FILE_TEMPLATE,
    RADAR_ID,
    TEMPDIR,
    EventTypes,
    UploadFileStatus,
    extract_error_message,
    get_download_file,
    split_to_even_chunks,
    unzip_archive,
    upload_local_file,
    write_json_data,
    zip_into_archive,
)

logger = logging.getLogger(__name__)


class WSProgressesSentinel(QObject):
    """
    Worker object that will be moved to a separate thread and will check progresses of the running simulations.
    This worker is fetching data through the websocket.
    """

    thread_finished = pyqtSignal(str)
    thread_failed = pyqtSignal(str)
    progresses_fetched = pyqtSignal(dict)
    simulation_finished = pyqtSignal(dict)

    def __init__(self, threedi_api, wss_url, personal_api_key, model_id=None):
        super().__init__()
        self.threedi_api = threedi_api
        self.wss_url = wss_url
        self.personal_api_key = personal_api_key
        self.tc = None
        self.ws_client = None
        self.running_simulations = {}
        self.model_id = model_id

    @pyqtSlot()
    def run(self):
        """Checking running simulations progresses."""
        try:
            self.tc = ThreediCalls(self.threedi_api)
            logger.debug("Fetching finished simulation statuses")
            finished_simulations_statuses = self.tc.fetch_simulation_statuses(name=SimulationStatusName.FINISHED.value)
            if self.model_id:
                logger.debug(f"Filtering simulation statuses on model id {self.model_id}")
                finished_simulations_statuses = (
                    status for status in finished_simulations_statuses if status.threedimodel_id == self.model_id
                )
            finished_simulations_data = {
                status.simulation_id: {
                    "date_created": status.created.strftime(API_DATETIME_FORMAT),
                    "name": status.simulation_name,
                    "progress": 100,
                    "status": status.name,
                    "user_name": None,  # SimulationStatus does not contain information about the user
                }
                for status in finished_simulations_statuses
            }
            logger.debug(f"Fetched {len(finished_simulations_data)} finished simulation statuses")
            time.sleep(1)
            self.simulation_finished.emit(finished_simulations_data)
        except ApiException as e:
            error_msg = extract_error_message(e)
            self.thread_failed.emit(error_msg)
            return
        self.ws_client = QtWebSockets.QWebSocket(version=QtWebSockets.QWebSocketProtocol.VersionLatest)
        self.ws_client.textMessageReceived.connect(self.all_simulations_progress_web_socket)
        self.ws_client.error.connect(self.websocket_error)
        self.start_listening()

    def start_listening(self):
        """Start listening of active simulations websocket."""
        identifier = "Basic"
        api_key = base64.b64encode(f"__key__:{self.personal_api_key}".encode()).decode()
        basic_auth_token = f"{identifier} {api_key}"
        api_version = self.tc.threedi_api.version
        ws_request = QNetworkRequest(QUrl(f"{self.wss_url}/{api_version}/active-simulations/"))
        ws_request.setRawHeader(QByteArray().append("Authorization"), QByteArray().append(basic_auth_token))
        self.ws_client.open(ws_request)

    def stop_listening(self):
        """Close websocket client."""
        if self.ws_client is not None:
            self.ws_client.textMessageReceived.disconnect(self.all_simulations_progress_web_socket)
            self.ws_client.error.disconnect(self.websocket_error)
            self.ws_client.close()
            stop_message = "Checking running simulation stopped."
            self.thread_finished.emit(stop_message)

    def websocket_error(self, error_code):
        """Report errors from websocket."""
        error_string = self.ws_client.errorString()
        error_msg = f"Websocket error ({error_code}): {error_string}"
        self.thread_failed.emit(error_msg)

    def all_simulations_progress_web_socket(self, data):
        """Get all simulations progresses through the websocket."""
        data = json.loads(data)
        data_type = data.get("type")
        logger.debug(f"Got simulation progress (type {data_type}) from the websocket")
        if data_type == "active-simulations" or data_type == "active-simulation":
            simulations = data.get("data")
            for sim_id_str, sim_data_str in simulations.items():
                sim_id = int(sim_id_str)
                sim_data = json.loads(sim_data_str)
                self.running_simulations[sim_id] = sim_data
        elif data_type == "progress":
            sim_id = int(data["data"]["simulation_id"])
            progress_percentage = data["data"]["progress"]
            sim_data = self.running_simulations[sim_id]
            sim_data["progress"] = progress_percentage
        elif data_type == "status":
            sim_id = int(data["data"]["simulation_id"])
            status_name = data["data"]["status"]
            sim_data = self.running_simulations[sim_id]
            sim_data["status"] = status_name
            if status_name == SimulationStatusName.FINISHED.value:
                if sim_data["progress"] == 100:
                    self.simulation_finished.emit({sim_id: sim_data})
                else:
                    sim_data["status"] = SimulationStatusName.STOPPED.value
        self.progresses_fetched.emit(self.running_simulations)


class DownloadWorkerSignals(QObject):
    """Definition of the download worker signals."""

    thread_finished = pyqtSignal(str, str)  # finish message, download directory
    download_failed = pyqtSignal(str)
    download_progress = pyqtSignal(float)


class DownloadProgressWorker(QRunnable):
    """Worker object responsible for downloading simulations results."""

    NOT_STARTED = -1
    FINISHED = 100
    FAILED = 101

    def __init__(self, simulation, downloads, directory):
        super().__init__()
        self.simulation = simulation
        self.downloads = downloads
        self.directory = bypass_max_path_limit(directory)
        self.success = True
        self.signals = DownloadWorkerSignals()

    @pyqtSlot()
    def run(self):
        """Downloading simulation results files."""
        if self.downloads:
            finished_message = (
                f"Downloading results of {self.simulation.name} ({self.simulation.id}) finished! "
                f"The files have been saved in the following location: '{self.directory}'"
            )
        else:
            finished_message = "Nothing to download!"
        total_size = sum(download.size for result_file, download in self.downloads)
        size = 0
        self.signals.download_progress.emit(size)
        for result_file, download in self.downloads:
            filename = result_file.filename
            filename_path = bypass_max_path_limit(os.path.join(self.directory, filename), is_file=True)
            try:
                os.makedirs(self.directory, exist_ok=True)
                file_data = requests.get(download.get_url, stream=True, timeout=15)
                with open(filename_path, "wb") as f:
                    for chunk in file_data.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
                            size += len(chunk)
                            self.signals.download_progress.emit(size / total_size * 100)
                if filename.lower().endswith(".zip"):
                    unzip_archive(filename_path)
                continue
            except Exception as e:
                error_msg = f"Error: {e}"
            self.signals.download_progress.emit(self.FAILED)
            self.signals.download_failed.emit(error_msg)
            self.success = False
            break
        if self.success is True:
            self.signals.download_progress.emit(self.FINISHED)
            self.signals.thread_finished.emit(finished_message, self.directory)


class UploadWorkerSignals(QObject):
    """Definition of the upload worker signals."""

    thread_finished = pyqtSignal(int, str)
    upload_failed = pyqtSignal(int, str)
    upload_progress = pyqtSignal(int, str, float, float)  # upload row number, task name, task progress, total progress
    revision_committed = pyqtSignal()


class RevisionUploadError(Exception):
    """Custom revision upload exception."""

    pass


class UploadProgressWorker(QRunnable):
    """Worker object responsible for uploading models."""

    TASK_CHECK_INTERVAL = 2.5
    TASK_CHECK_RETRIES = 4

    def __init__(self, threedi_api, local_schematisation, upload_specification, upload_row_number):
        super().__init__()
        self.threedi_api = threedi_api
        self.local_schematisation = local_schematisation
        self.upload_specification = upload_specification
        self.upload_row_number = upload_row_number
        self.current_task = "NO TASK"
        self.current_task_progress = 0.0
        self.total_progress = 0.0
        self.tc = None
        self.schematisation = self.upload_specification["schematisation"]
        self.revision = self.upload_specification["latest_revision"]
        self.signals = UploadWorkerSignals()

    @pyqtSlot()
    def run(self):
        """Run all schematisation upload tasks."""
        self.tc = ThreediCalls(self.threedi_api)
        tasks_list = self.build_tasks_list()
        if not tasks_list:
            self.current_task = "DONE"
            self.current_task_progress = 100.0
            self.total_progress = 100.0
            self.report_upload_progress()
            self.signals.thread_finished.emit(self.upload_row_number, "Nothing to upload or process")
            return
        progress_per_task = 1 / len(tasks_list) * 100
        try:
            for i, task in enumerate(tasks_list, start=1):
                task()
                self.total_progress = progress_per_task * i
            self.current_task = "DONE"
            self.total_progress = 100.0
            self.report_upload_progress()
            msg = f"Schematisation '{self.schematisation.name}' (revision: {self.revision.number}) files uploaded"
            self.signals.thread_finished.emit(self.upload_row_number, msg)
        except Exception as e:
            error_msg = f"Error: {e}"
            self.signals.upload_failed.emit(self.upload_row_number, error_msg)

    def build_tasks_list(self):
        """Build upload tasks list."""
        tasks = list()
        create_revision = self.upload_specification["create_revision"]
        upload_only = self.upload_specification["upload_only"]
        if create_revision:
            tasks.append(self.create_revision_task)
        for file_name, file_state in self.upload_specification["selected_files"].items():
            make_action_on_file = file_state["make_action"]
            file_status = file_state["status"]
            if make_action_on_file is False:
                continue
            if file_status == UploadFileStatus.NEW:
                if file_name == "spatialite":
                    tasks.append(self.upload_sqlite_task)
                else:
                    tasks.append(partial(self.upload_raster_task, file_name))
            elif file_status == UploadFileStatus.CHANGES_DETECTED:
                if file_name == "spatialite":
                    tasks.append(self.delete_sqlite_task)
                    tasks.append(self.upload_sqlite_task)
                else:
                    tasks.append(partial(self.delete_raster_task, file_name))
                    tasks.append(partial(self.upload_raster_task, file_name))
            elif file_status == UploadFileStatus.DELETED_LOCALLY:
                tasks.append(partial(self.delete_raster_task, file_name))
            else:
                continue
        tasks.append(self.commit_revision_task)
        if not upload_only:
            tasks.append(self.create_3di_model_task)
        return tasks

    def create_revision_task(self):
        """Run creation of the new revision task."""
        self.current_task = "CREATE REVISION"
        self.current_task_progress = 0.0
        self.report_upload_progress()
        self.revision = self.tc.create_schematisation_revision(self.schematisation.id)
        self.current_task_progress = 100.0
        self.report_upload_progress()

    def upload_sqlite_task(self):
        """Run sqlite file upload task."""
        self.current_task = "UPLOAD SPATIALITE"
        self.current_task_progress = 0.0
        self.report_upload_progress()
        schematisation_sqlite = self.upload_specification["selected_files"]["spatialite"]["filepath"]
        zipped_sqlite_filepath = zip_into_archive(schematisation_sqlite)
        zipped_sqlite_file = os.path.basename(zipped_sqlite_filepath)
        upload = self.tc.upload_schematisation_revision_sqlite(
            self.schematisation.id, self.revision.id, zipped_sqlite_file
        )
        upload_file(upload.put_url, zipped_sqlite_filepath, CHUNK_SIZE, callback_func=self.monitor_upload_progress)
        os.remove(zipped_sqlite_filepath)
        self.current_task_progress = 100.0
        self.report_upload_progress()

    def delete_sqlite_task(self):
        """Run sqlite file deletion task."""
        self.current_task = "DELETE SPATIALITE"
        self.current_task_progress = 0.0
        self.report_upload_progress()
        self.tc.delete_schematisation_revision_sqlite(self.schematisation.id, self.revision.id)
        self.current_task_progress = 100.0
        self.report_upload_progress()

    def upload_raster_task(self, raster_type):
        """Run raster file upload task."""
        self.current_task = f"UPLOAD RASTER ({raster_type})"
        self.current_task_progress = 0.0
        self.report_upload_progress()
        raster_filepath = self.upload_specification["selected_files"][raster_type]["filepath"]
        raster_file = os.path.basename(raster_filepath)
        raster_revision = self.tc.create_schematisation_revision_raster(
            self.schematisation.id, self.revision.id, raster_file, raster_type=raster_type
        )
        raster_upload = self.tc.upload_schematisation_revision_raster(
            raster_revision.id, self.schematisation.id, self.revision.id, raster_file
        )
        upload_file(raster_upload.put_url, raster_filepath, CHUNK_SIZE, callback_func=self.monitor_upload_progress)
        self.current_task_progress = 100.0
        self.report_upload_progress()

    def delete_raster_task(self, raster_type):
        """Run raster file deletion task."""
        types_to_delete = [raster_type]
        if raster_type == "dem_file":
            types_to_delete.append("dem_raw_file")  # We need to remove legacy 'dem_raw_file` as well
        self.current_task = f"DELETE RASTER ({raster_type})"
        self.current_task_progress = 0.0
        self.report_upload_progress()
        for revision_raster in self.revision.rasters:
            revision_type = revision_raster.type
            if revision_type in types_to_delete:
                self.tc.delete_schematisation_revision_raster(
                    revision_raster.id, self.schematisation.id, self.revision.id
                )
                break
        self.current_task_progress = 100.0
        self.report_upload_progress()

    def commit_revision_task(self):
        """Run committing revision task."""
        self.current_task = "COMMIT REVISION"
        self.current_task_progress = 0.0
        self.report_upload_progress()
        commit_message = self.upload_specification["commit_message"]
        self.tc.commit_schematisation_revision(self.schematisation.id, self.revision.id, commit_message=commit_message)
        self.revision = self.tc.fetch_schematisation_revision(self.schematisation.id, self.revision.id)
        while self.revision.is_valid is None:
            time.sleep(2)
            self.revision = self.tc.fetch_schematisation_revision(self.schematisation.id, self.revision.id)
        self.current_task_progress = 100.0
        self.report_upload_progress()
        self.local_schematisation.update_wip_revision(self.revision.number)
        self.signals.revision_committed.emit()

    def create_3di_model_task(self):
        """Run creation of the new model out of revision data."""
        self.current_task = "MAKE 3DI MODEL"
        self.current_task_progress = 0.0
        self.report_upload_progress()
        # Wait for the 'modelchecker' validations
        model_checker_task = None
        revision_tasks = self.tc.fetch_schematisation_revision_tasks(self.schematisation.id, self.revision.id)
        for i in range(self.TASK_CHECK_RETRIES):
            for rtask in revision_tasks:
                if rtask.name == "modelchecker":
                    model_checker_task = rtask
                    break
            if model_checker_task:
                break
            else:
                time.sleep(self.TASK_CHECK_INTERVAL)
        if model_checker_task:
            status = model_checker_task.status
            while status != "success":
                model_checker_task = self.tc.fetch_schematisation_revision_task(
                    model_checker_task.id, self.schematisation.id, self.revision.id
                )
                status = model_checker_task.status
                if status == "success":
                    break
                elif status == "failure":
                    err = RevisionUploadError(model_checker_task.detail["message"])
                    raise err
                else:
                    time.sleep(self.TASK_CHECK_INTERVAL)
            checker_errors = model_checker_task.detail["result"]["errors"]
            if checker_errors:
                error_msg = "\n".join(error["description"] for error in checker_errors)
                err = RevisionUploadError(error_msg)
                raise err
        # Create 3Di model
        model = self.tc.create_schematisation_revision_3di_model(self.schematisation.id, self.revision.id)
        model_id = model.id
        finished_tasks = {
            "make_gridadmin": False,
            "make_tables": False,
            "make_aggregations": False,
            "make_cog": False,
            "make_geojson": False,
            "make_simulation_templates": False,
        }
        expected_tasks_number = len(finished_tasks)
        while not all(finished_tasks.values()):
            model_tasks = self.tc.fetch_3di_model_tasks(model_id)
            for task in model_tasks:
                task_status = task.status
                if task_status == "success":
                    finished_tasks[task.name] = True
                elif task_status == "failure":
                    err = RevisionUploadError(task.detail["message"])
                    raise err
            model = self.tc.fetch_3di_model(model_id)
            if getattr(model, "is_valid", False):
                finished_tasks = {task_name: True for task_name in finished_tasks.keys()}
            finished_tasks_count = len([val for val in finished_tasks.values() if val])
            self.monitor_upload_progress(finished_tasks_count, expected_tasks_number)
            if finished_tasks_count != expected_tasks_number:
                time.sleep(self.TASK_CHECK_INTERVAL)

    def report_upload_progress(self):
        """Report upload progress."""
        self.signals.upload_progress.emit(
            self.upload_row_number, self.current_task, self.current_task_progress, self.total_progress
        )

    def monitor_upload_progress(self, chunk_size, total_size):
        """Upload progress callback method."""
        upload_progress = chunk_size / total_size * 100
        self.current_task_progress = upload_progress
        self.report_upload_progress()


class SimulationRunnerError(Exception):
    """Simulation runner exception class."""

    pass


class SimulationRunnerSignals(QObject):
    """Definition of the simulation runner signals."""

    # simulation to run, simulation initialized, current progress, total progress
    initializing_simulations_progress = pyqtSignal(dm.NewSimulation, bool, int, int)
    # error message
    initializing_simulations_failed = pyqtSignal(str)
    # message
    initializing_simulations_finished = pyqtSignal(str)


class SimulationRunner(QRunnable):
    """Worker object responsible for running simulations."""

    def __init__(self, threedi_api, simulations_to_run, upload_timeout=900):
        super().__init__()
        self.threedi_api = threedi_api
        self.simulations_to_run = simulations_to_run
        self.current_simulation = None
        self.valid_states = ["processed", "valid", "success"]
        self.upload_timeout = upload_timeout
        self.tc = None
        self.signals = SimulationRunnerSignals()
        self.total_progress = 100
        self.steps_per_simulation = 10
        self.current_step = 0
        self.number_of_steps = len(self.simulations_to_run) * self.steps_per_simulation
        self.percentage_per_step = self.total_progress / self.number_of_steps

    def create_simulation(self):
        """Create a new simulation out of the NewSimulation data model."""
        simulation = self.tc.create_simulation(
            name=self.current_simulation.name,
            tags=self.current_simulation.tags,
            threedimodel=self.current_simulation.threedimodel_id,
            start_datetime=self.current_simulation.start_datetime,
            organisation=self.current_simulation.organisation_uuid,
            duration=self.current_simulation.duration,
        )
        self.current_simulation.simulation = simulation
        current_status = self.tc.fetch_simulation_status(simulation.id)
        self.current_simulation.initial_status = current_status

    def include_init_options(self):
        """Apply initialization options to the new simulation."""
        sim_id = self.current_simulation.simulation.id
        init_options = self.current_simulation.init_options
        if init_options.raster_edits:
            re = init_options.raster_edits
            raster_edit_data = {
                "raster": re.raster,
                "offset": re.offset,
                "value": re.value,
                "polygon": re.polygon,
                "relative": re.relative,
            }
            self.tc.create_raster_edits(sim_id, **raster_edit_data)
        if init_options.leakage:
            pass  # TODO: need implementation
        if init_options.sources_sinks:
            if init_options.sources_sinks.lizard_raster_sources_sinks:
                lrss = init_options.sources_sinks.lizard_raster_sources_sinks
                lizard_raster_sources_sinks_data = {
                    "offset": lrss.offset,
                    "duration": lrss.duration,
                    "reference_uuid": lrss.reference_uuid,
                    "start_datetime": lrss.start_datetime,
                }
                self.tc.create_lizard_raster_sources_sinks(sim_id, **lizard_raster_sources_sinks_data)
            if init_options.sources_sinks.lizard_timeseries_sources_sinks:
                ltss = init_options.sources_sinks.lizard_timeseries_sources_sinks
                lizard_timeseries_sources_sinks_data = {
                    "offset": ltss.offset,
                    "duration": ltss.duration,
                    "reference_uuid": ltss.reference_uuid,
                    "start_datetime": ltss.start_datetime,
                    "interpolate": ltss.interpolate,
                }
                self.tc.create_lizard_timeseries_sources_sinks(sim_id, **lizard_timeseries_sources_sinks_data)
            if init_options.sources_sinks.timeseries_sources_sinks:
                tss = init_options.sources_sinks.timeseries_sources_sinks
                timeseries_sources_sinks_data = {
                    "offset": tss.offset,
                    "interpolate": tss.interpolate,
                    "values": tss.values,
                    "units": tss.units,
                }
                self.tc.create_timeseries_sources_sinks(sim_id, **timeseries_sources_sinks_data)
            if init_options.sources_sinks.file_raster_sources_sinks:
                pass  # TODO: needs implementation
            if init_options.sources_sinks.file_timeseries_sources_sinks:
                pass  # TODO: needs implementation
        if init_options.local_timeseries_rain:
            if init_options.local_timeseries_rain.lizard_timeseries_rain:
                ltr = init_options.local_timeseries_rain.lizard_timeseries_rain
                lizard_timeseries_rain_data = {
                    "offset": ltr.offset,
                    "duration": ltr.duration,
                    "reference_uuid": ltr.reference_uuid,
                    "start_datetime": ltr.start_datetime,
                    "interpolate": ltr.interpolate,
                    "units": ltr.units,
                }
                self.tc.create_lizard_timeseries_rain(sim_id, **lizard_timeseries_rain_data)
            if init_options.local_rain:
                lr = init_options.local_rain
                if lr.constant:
                    local_rain_data = {
                        "offset": lr.offset,
                        "value": lr.value,
                        "units": lr.units,
                        "duration": lr.duration,
                        "interpolate": lr.interpolate,
                        "diameter": lr.diameter,
                        "point": lr.point,
                    }
                    self.tc.create_local_rain_constant(sim_id, **local_rain_data)
                else:
                    local_rain_data = {
                        "offset": lr.offset,
                        "values": lr.values,
                        "interpolate": lr.interpolate,
                        "units": lr.units,
                        "diameter": lr.diameter,
                        "point": lr.point,
                    }
                    self.tc.create_local_rain_timeseries(sim_id, **local_rain_data)
            if init_options.file_timeseries_rain:
                pass  # TODO: needs implementation
        if init_options.obstacle_edits:
            oe = init_options.obstacle_edits
            obstacle_edit_data = {
                "offset": oe.offset,
                "value": oe.value,
                "linestring": oe.linestring,
                "relative": oe.relative,
            }
            self.tc.create_obstacle_edits(sim_id, **obstacle_edit_data)

    def include_boundary_conditions(self):
        """Apply boundary conditions to the new simulation."""
        sim_id = self.current_simulation.simulation.id
        sim_name = self.current_simulation.name
        boundary_conditions = self.current_simulation.boundary_conditions

        def upload_file_boundary_conditions(filename, filepath):
            bc_upload = self.tc.create_simulation_boundarycondition_file(sim_id, filename=filename)
            upload_local_file(bc_upload, filepath)
            for ti in range(int(self.upload_timeout // 2)):
                uploaded_bc = self.tc.fetch_boundarycondition_files(sim_id)[0]
                if uploaded_bc.state in self.valid_states:
                    break
                else:
                    time.sleep(2)

        if boundary_conditions.file_boundary_conditions is not None:
            sim_temp_id = self.current_simulation.simulation_template_id
            bc_file = boundary_conditions.file_boundary_conditions
            bc_file_download = self.tc.fetch_boundarycondition_file_download(sim_temp_id, bc_file.id)
            bc_file_name = bc_file.file.filename
            bc_temp_filepath = os.path.join(TEMPDIR, bc_file_name)
            get_download_file(bc_file_download, bc_temp_filepath)
            upload_file_boundary_conditions(bc_file_name, bc_temp_filepath)
            os.remove(bc_temp_filepath)
        if boundary_conditions.data:
            write_json_data(boundary_conditions.data, BOUNDARY_CONDITIONS_TEMPLATE)
            bc_file_name = f"{sim_name}_boundary_conditions.json"
            upload_file_boundary_conditions(bc_file_name, BOUNDARY_CONDITIONS_TEMPLATE)

    def include_structure_controls(self):
        """Apply structure controls to the new simulation."""
        ignore_keys = {"id", "url", "uid", "state", "state_detail", "simulation"}
        sim_id = self.current_simulation.simulation.id
        sim_temp_id = self.current_simulation.simulation_template_id
        structure_controls = self.current_simulation.structure_controls

        def upload_file_structure_controls(filename, filepath, offset):
            sc_upload = self.tc.create_simulation_structure_control_file(sim_id, filename=filename, offset=offset)
            upload_local_file(sc_upload, filepath)
            for ti in range(int(self.upload_timeout // 2)):
                uploaded_files = {scf.file.filename: scf for scf in self.tc.fetch_structure_control_files(sim_id)}
                uploaded_sc = uploaded_files[sc_upload.filename]
                if uploaded_sc.state in self.valid_states:
                    break
                else:
                    time.sleep(2)

        if structure_controls.file_structure_controls:
            sc_file = structure_controls.file_structure_controls
            sc_file_download = self.tc.fetch_structure_control_file_download(sim_temp_id, sc_file.id)
            sc_file_name = sc_file.file.filename
            sc_file_offset = sc_file.offset
            sc_filepath = os.path.join(TEMPDIR, sc_file_name)
            get_download_file(sc_file_download, sc_filepath)
            upload_file_structure_controls(sc_file_name, sc_filepath, sc_file_offset)
            os.remove(sc_filepath)
        if structure_controls.local_file_structure_controls:
            sc_filepath = structure_controls.local_file_structure_controls
            sc_file_name = os.path.basename(sc_filepath)
            sc_file_offset = 0.0
            upload_file_structure_controls(sc_file_name, sc_filepath, sc_file_offset)
        if structure_controls.memory_structure_controls:
            sc_memory_data = {
                k: v for k, v in structure_controls.memory_structure_controls.to_dict().items() if k not in ignore_keys
            }
            self.tc.create_simulation_structure_control_memory(sim_id, **sc_memory_data)
        if structure_controls.table_structure_controls:
            sc_table_data = {
                k: v for k, v in structure_controls.table_structure_controls.to_dict().items() if k not in ignore_keys
            }
            self.tc.create_simulation_structure_control_table(sim_id, **sc_table_data)
        if structure_controls.timed_structure_controls:
            sc_timed_data = {
                k: v for k, v in structure_controls.timed_structure_controls.to_dict().items() if k not in ignore_keys
            }
            self.tc.create_simulation_structure_control_timed(sim_id, **sc_timed_data)

    def include_initial_conditions(self):
        """Add initial conditions to the new simulation."""
        sim_id = self.current_simulation.simulation.id
        threedimodel_id = self.current_simulation.threedimodel_id
        initial_conditions = self.current_simulation.initial_conditions
        # 1D
        if initial_conditions.global_value_1d is not None:
            self.tc.create_simulation_initial_1d_water_level_constant(sim_id, value=initial_conditions.global_value_1d)
        if initial_conditions.from_spatialite_1d:
            self.tc.create_simulation_initial_1d_water_level_predefined(sim_id)
        # 2D
        if initial_conditions.global_value_2d is not None:
            self.tc.create_simulation_initial_2d_water_level_constant(sim_id, value=initial_conditions.global_value_2d)
        if initial_conditions.online_raster_2d is None and initial_conditions.local_raster_2d is not None:
            local_raster_2d_name = os.path.basename(initial_conditions.local_raster_2d)
            initial_water_level_raster_2d = self.tc.create_3di_model_raster(
                threedimodel_id, name=local_raster_2d_name, type="initial_waterlevel_file"
            )
            initial_wl_raster_2d_id = initial_water_level_raster_2d.id
            init_water_level_upload_2d = self.tc.upload_3di_model_raster(
                threedimodel_id,
                initial_wl_raster_2d_id,
                filename=local_raster_2d_name,
            )
            upload_local_file(init_water_level_upload_2d, initial_conditions.local_raster_2d)
            raster_task_2d = None
            for ti in range(int(self.upload_timeout // 2)):
                if raster_task_2d is None:
                    model_tasks = self.tc.fetch_3di_model_tasks(threedimodel_id)
                    for task in model_tasks:
                        try:
                            if initial_wl_raster_2d_id in task.params["only_raster_ids"]:
                                raster_task_2d = task
                                break
                        except KeyError:
                            continue
                else:
                    raster_task_2d = self.tc.fetch_3di_model_task(threedimodel_id, raster_task_2d.id)
                if raster_task_2d and raster_task_2d.status in self.valid_states:
                    break
                else:
                    time.sleep(2)
            initial_waterlevels = self.tc.fetch_3di_model_initial_waterlevels(threedimodel_id)
            for iw in initial_waterlevels:
                if iw.source_raster_id == initial_wl_raster_2d_id:
                    initial_conditions.online_raster_2d = iw
                    break
        if initial_conditions.online_raster_2d is not None:
            try:
                self.tc.create_simulation_initial_2d_water_level_raster(
                    sim_id,
                    aggregation_method=initial_conditions.aggregation_method_2d,
                    initial_waterlevel=initial_conditions.online_raster_2d.url,
                )
            except AttributeError:
                error_msg = "Error: selected 2D raster for initial water level is not valid."
                raise SimulationRunnerError(error_msg)
        # Groundwater
        if initial_conditions.global_value_groundwater is not None:
            self.tc.create_simulation_initial_groundwater_level_constant(
                sim_id, value=initial_conditions.global_value_groundwater
            )
        if (
            initial_conditions.online_raster_groundwater is None
            and initial_conditions.local_raster_groundwater is not None
        ):
            local_raster_groundwater_name = os.path.basename(initial_conditions.local_raster_groundwater)
            initial_water_level_raster_gw = self.tc.create_3di_model_raster(
                threedimodel_id,
                name=local_raster_groundwater_name,
                type="initial_groundwater_level_file",
            )
            initial_wl_raster_gw_id = initial_water_level_raster_gw.id
            init_water_level_upload_gw = self.tc.upload_3di_model_raster(
                threedimodel_id,
                initial_wl_raster_gw_id,
                filename=local_raster_groundwater_name,
            )
            upload_local_file(init_water_level_upload_gw, initial_conditions.local_raster_groundwater)
            raster_task_gw = None
            for ti in range(int(self.upload_timeout // 2)):
                if raster_task_gw is None:
                    model_tasks = self.tc.fetch_3di_model_tasks(threedimodel_id)
                    for task in model_tasks:
                        try:
                            if initial_wl_raster_gw_id in task.params["only_raster_ids"]:
                                raster_task_gw = task
                                break
                        except KeyError:
                            continue
                else:
                    raster_task_gw = self.tc.fetch_3di_model_task(threedimodel_id, raster_task_gw.id)
                if raster_task_gw and raster_task_gw.status in self.valid_states:
                    break
                else:
                    time.sleep(2)
            initial_waterlevels = self.tc.fetch_3di_model_initial_waterlevels(threedimodel_id)
            for iw in initial_waterlevels:
                if iw.source_raster_id == initial_wl_raster_gw_id:
                    initial_conditions.online_raster_groundwater = iw
                    break
        if initial_conditions.online_raster_groundwater is not None:
            try:
                self.tc.create_simulation_initial_groundwater_level_raster(
                    sim_id,
                    aggregation_method=initial_conditions.aggregation_method_groundwater,
                    initial_waterlevel=initial_conditions.online_raster_groundwater.url,
                )
            except AttributeError:
                error_msg = "Error: selected groundwater raster is not valid."
                raise SimulationRunnerError(error_msg)
        # Saved state
        if initial_conditions.saved_state:
            saved_state_id = initial_conditions.saved_state.url.strip("/").split("/")[-1]
            self.tc.create_simulation_initial_saved_state(sim_id, saved_state=saved_state_id)

    def include_laterals(self):
        """Add initial laterals to the new simulation."""
        sim_id = self.current_simulation.simulation.id
        sim_name = self.current_simulation.name
        if self.current_simulation.laterals:
            lateral_values = list(self.current_simulation.laterals.data.values())
            write_json_data(lateral_values, LATERALS_FILE_TEMPLATE)
            upload_event_file = self.tc.create_simulation_lateral_file(
                sim_id, filename=f"{sim_name}_laterals.json", offset=0
            )
            upload_local_file(upload_event_file, LATERALS_FILE_TEMPLATE)
            for ti in range(int(self.upload_timeout // 2)):
                uploaded_lateral = self.tc.fetch_lateral_files(sim_id)[0]
                if uploaded_lateral.state in self.valid_states:
                    break
                else:
                    time.sleep(2)

    def include_dwf(self):
        """Add Dry Weather Flow to the new simulation."""
        sim_id = self.current_simulation.simulation.id
        sim_name = self.current_simulation.name
        if self.current_simulation.dwf:
            dwf_values = list(self.current_simulation.dwf.data.values())
            write_json_data(dwf_values, DWF_FILE_TEMPLATE)
            upload_event_file = self.tc.create_simulation_lateral_file(
                sim_id,
                filename=f"{sim_name}_dwf.json",
                offset=0,
                periodic="daily",
            )
            upload_local_file(upload_event_file, DWF_FILE_TEMPLATE)
            for ti in range(int(self.upload_timeout // 2)):
                uploaded_dwf = self.tc.fetch_lateral_files(sim_id)[0]
                if uploaded_dwf.state in self.valid_states:
                    break
                else:
                    time.sleep(2)

    def include_breaches(self):
        """Add breaches to the new simulation."""
        sim_id = self.current_simulation.simulation.id
        threedimodel_id = self.current_simulation.threedimodel_id
        if self.current_simulation.breach:
            breach_obj = self.tc.fetch_3di_model_point_potential_breach(
                threedimodel_id, int(self.current_simulation.breach.breach_id)
            )
            breach = breach_obj.to_dict()
            self.tc.create_simulation_breaches(
                sim_id,
                potential_breach=breach["url"],
                duration_till_max_depth=self.current_simulation.breach.duration_in_units,
                initial_width=self.current_simulation.breach.width,
                offset=self.current_simulation.breach.offset,
                discharge_coefficient_positive=self.current_simulation.breach.discharge_coefficient_positive,
                discharge_coefficient_negative=self.current_simulation.breach.discharge_coefficient_negative,
                maximum_breach_depth=self.current_simulation.breach.max_breach_depth,
            )

    def include_precipitation(self):
        """Add precipitation to the new simulation."""
        sim_id = self.current_simulation.simulation.id
        if self.current_simulation.precipitation:
            precipitation_type = self.current_simulation.precipitation.precipitation_type
            values = self.current_simulation.precipitation.values
            units = self.current_simulation.precipitation.units
            duration = self.current_simulation.precipitation.duration
            offset = self.current_simulation.precipitation.offset
            start = self.current_simulation.precipitation.start
            interpolate = self.current_simulation.precipitation.interpolate
            filepath = self.current_simulation.precipitation.filepath
            from_csv = self.current_simulation.precipitation.from_csv

            if precipitation_type == EventTypes.CONSTANT.value:
                self.tc.create_simulation_constant_precipitation(
                    sim_id, value=values, units=units, duration=duration, offset=offset
                )
            elif precipitation_type == EventTypes.CUSTOM.value:
                if from_csv:
                    for values_chunk in split_to_even_chunks(values, 300):
                        chunk_offset = values_chunk[0][0]
                        values_chunk = [[t - chunk_offset, v] for t, v in values_chunk]
                        self.tc.create_simulation_custom_precipitation(
                            sim_id,
                            values=values_chunk,
                            units=units,
                            duration=duration,
                            offset=offset + chunk_offset,
                            interpolate=interpolate,
                        )
                else:
                    filename = os.path.basename(filepath)
                    upload = self.tc.create_simulation_custom_netcdf_precipitation(sim_id, filename=filename)
                    upload_local_file(upload, filepath)
            elif precipitation_type == EventTypes.DESIGN.value:
                self.tc.create_simulation_custom_precipitation(
                    sim_id, values=values, units=units, duration=duration, offset=offset
                )
            elif precipitation_type == EventTypes.RADAR.value:
                self.tc.create_simulation_radar_precipitation(
                    sim_id,
                    reference_uuid=RADAR_ID,
                    units=units,
                    duration=duration,
                    offset=offset,
                    start_datetime=start,
                )

    def include_wind(self):
        """Add wind to the new simulation."""
        sim_id = self.current_simulation.simulation.id
        if self.current_simulation.wind:
            wind_type = self.current_simulation.wind.wind_type
            offset = self.current_simulation.wind.offset
            duration = self.current_simulation.wind.duration
            speed = self.current_simulation.wind.speed
            direction = self.current_simulation.wind.direction
            units = self.current_simulation.wind.units
            drag_coefficient = self.current_simulation.wind.drag_coefficient
            interpolate_speed = self.current_simulation.wind.interpolate_speed
            interpolate_direction = self.current_simulation.wind.interpolate_speed
            values = self.current_simulation.wind.values
            self.tc.create_simulation_initial_wind_drag_coefficient(sim_id, value=drag_coefficient)
            if wind_type == EventTypes.CONSTANT.value:
                self.tc.create_simulation_constant_wind(
                    sim_id,
                    offset=offset,
                    duration=duration,
                    units=units,
                    speed_value=speed,
                    direction_value=direction,
                )
            elif wind_type == EventTypes.CUSTOM.value:
                self.tc.create_simulation_custom_wind(
                    sim_id,
                    offset=offset,
                    values=values,
                    units=units,
                    speed_interpolate=interpolate_speed,
                    direction_interpolate=interpolate_direction,
                )

    def include_settings(self):
        """Add settings to the new simulation."""
        sim_id = self.current_simulation.simulation.id
        settings = self.current_simulation.settings
        self.tc.create_simulation_settings_physical(sim_id, **settings.physical_settings)
        self.tc.create_simulation_settings_numerical(sim_id, **settings.numerical_settings)
        self.tc.create_simulation_settings_time_step(sim_id, **settings.time_step_settings)
        for aggregation_settings in settings.aggregation_settings_list:
            self.tc.create_simulation_settings_aggregation(sim_id, **aggregation_settings)

    def include_lizard_post_processing(self):
        """Add post-processing in Lizard to the new simulation."""
        sim_id = self.current_simulation.simulation.id
        sim_name = self.current_simulation.name
        lizard_post_processing = self.current_simulation.lizard_post_processing
        if lizard_post_processing:
            self.tc.create_simulation_post_processing_lizard_basic(
                sim_id, scenario_name=sim_name, process_basic_results=True
            )
            if lizard_post_processing.arrival_time_map:
                self.tc.create_simulation_postprocessing_in_lizard_arrival(sim_id, basic_post_processing=True)
            if lizard_post_processing.damage_estimation is not None:
                de = lizard_post_processing.damage_estimation
                self.tc.create_simulation_post_processing_lizard_damage(
                    sim_id,
                    basic_post_processing=True,
                    cost_type=de.cost_type,
                    flood_month=de.flood_month,
                    inundation_period=de.inundation_period,
                    repair_time_infrastructure=de.repair_time_infrastructure,
                    repair_time_buildings=de.repair_time_buildings,
                )

    def include_new_saved_state(self):
        """Generate a new saved state along the new simulation."""
        sim_id = self.current_simulation.simulation.id
        duration = self.current_simulation.duration
        new_saved_state = self.current_simulation.new_saved_state
        if new_saved_state:
            if new_saved_state.thresholds:
                self.tc.create_simulation_saved_state_stable_threshold(
                    sim_id, name=new_saved_state.name, tags=new_saved_state.tags, thresholds=new_saved_state.thresholds
                )
            else:
                self.tc.create_simulation_saved_state_timed(
                    sim_id,
                    name=new_saved_state.name,
                    tags=new_saved_state.tags,
                    time=new_saved_state.time if new_saved_state.time >= 0 else duration,
                )

    def start_simulation(self):
        """Start (or add to queue) given simulation."""
        sim_id = self.current_simulation.simulation.id
        try:
            self.tc.create_simulation_action(sim_id, name="start")
        except ApiException as e:
            if e.status == 429:
                self.tc.create_simulation_action(sim_id, name="queue")
            else:
                raise e
        if self.current_simulation.template_name is not None:
            self.tc.create_template_from_simulation(self.current_simulation.template_name, str(sim_id))

    @pyqtSlot()
    def run(self):
        """Run new simulation(s)."""
        try:
            self.tc = ThreediCalls(self.threedi_api)
            for simulation_to_run in self.simulations_to_run:
                self.current_simulation = simulation_to_run
                self.report_progress(increase_current_step=False)
                self.create_simulation()
                self.report_progress()
                self.include_init_options()
                self.report_progress()
                self.include_boundary_conditions()
                self.report_progress()
                self.include_structure_controls()
                self.report_progress()
                self.include_initial_conditions()
                self.report_progress()
                self.include_laterals()
                self.report_progress()
                self.include_dwf()
                self.report_progress()
                self.include_breaches()
                self.report_progress()
                self.include_precipitation()
                self.report_progress()
                self.include_wind()
                self.report_progress()
                self.include_settings()
                self.report_progress()
                self.include_new_saved_state()
                self.report_progress()
                self.include_lizard_post_processing()
                self.report_progress()
                self.start_simulation()
                self.report_progress(simulation_initialized=True)
            self.report_finished("Simulations successfully initialized!")
        except ApiException as e:
            error_msg = extract_error_message(e)
            self.report_failure(error_msg)
        except Exception as e:
            error_msg = f"Error: {e}"
            self.report_failure(error_msg)

    def report_progress(self, simulation_initialized=False, increase_current_step=True):
        """Report worker progress."""
        current_progress = int(self.current_step * self.percentage_per_step)
        if increase_current_step:
            self.current_step += 1
        self.signals.initializing_simulations_progress.emit(
            self.current_simulation, simulation_initialized, current_progress, self.total_progress
        )

    def report_failure(self, error_message):
        """Report worker failure message."""
        self.signals.initializing_simulations_failed.emit(error_message)

    def report_finished(self, message):
        """Report worker finished message."""
        self.signals.initializing_simulations_finished.emit(message)
