# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import logging
import os
import json
import time
import requests
from functools import partial
from qgis.PyQt.QtCore import QObject, QRunnable, QUrl, QByteArray, pyqtSignal, pyqtSlot
from qgis.PyQt import QtNetwork
from PyQt5 import QtWebSockets
from threedi_api_client.openapi import ApiException, Progress
from threedi_api_client.files import upload_file
from .api_calls.threedi_calls import ThreediCalls
from .utils import UploadFileStatus


logger = logging.getLogger(__name__)


class WSProgressesSentinel(QObject):
    """
    Worker object that will be moved to a separate thread and will check progresses of the running simulations.
    This worker is fetching data through the websocket.
    """

    thread_finished = pyqtSignal(str)
    thread_failed = pyqtSignal(str)
    progresses_fetched = pyqtSignal(dict)

    def __init__(self, threedi_api, wss_url, model_id=None):
        super().__init__()
        self.threedi_api = threedi_api
        self.wss_url = wss_url
        self.tc = None
        self.ws_client = None
        self.progresses = {}
        self.simulations_list = []
        self.model_id = model_id

    @pyqtSlot()
    def run(self):
        """Checking running simulations progresses."""
        try:
            self.tc = ThreediCalls(self.threedi_api)
            if self.model_id:
                logger.debug(f"Fetching simulations list and filtering it on model id {self.model_id}")
                full_simulations_list = self.tc.fetch_simulations()
                logger.debug(f"Starting out with {len(full_simulations_list)} simulations")
                self.simulations_list = [
                    simulation for simulation in full_simulations_list if simulation.threedimodel_id == self.model_id
                ]
                logger.debug(f"We have {len(self.simulations_list)} simulations left")

            result = self.tc.fetch_simulations_progresses(self.simulations_list)
            self.progresses_fetched.emit(result)
        except ApiException as e:
            error_msg = f"Error: {e}"
            self.thread_failed.emit(error_msg)
            return
        self.ws_client = QtWebSockets.QWebSocket("", QtWebSockets.QWebSocketProtocol.Version13, None)
        self.ws_client.textMessageReceived.connect(self.all_simulations_progress_web_socket)
        self.ws_client.error.connect(self.websocket_error)
        self.start_listening()

    def start_listening(self):
        """Start listening of active simulations websocket."""
        identifier = "Bearer"
        api_key = self.tc.threedi_api.api_client.configuration.api_key["Authorization"]
        api_version = self.tc.threedi_api.version
        token_with_prefix = f"{identifier} {api_key}"
        ws_request = QtNetwork.QNetworkRequest(QUrl(f"{self.wss_url}/{api_version}/active-simulations/"))
        ws_request.setRawHeader(QByteArray().append("Authorization"), QByteArray().append(token_with_prefix))
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
            # Note: commented-out 2021-05-21 by Reinout as this code can lead to
            # throttling, see https://github.com/nens/threedi-api-qgis-client/issues/151
            #
            logger.info(f"Fetching fresh simulation for simulation(s): {simulations.keys()}")
            for sim_id_str, sim_data in simulations.items():
                sim_id = int(sim_id_str)
                sim = json.loads(sim_data)
                simulation = self.tc.fetch_simulation(sim_id)
                current_status = self.tc.fetch_simulation_status(sim_id)
                status_name = current_status.name
                status_time = current_status.time
                if status_time is None:
                    status_time = 0
                if status_name == "initialized":
                    sim_progress = Progress(0, sim.get("progress"))
                else:
                    sim_progress = Progress(percentage=0, time=status_time)
                self.progresses[sim_id] = {
                    "simulation": simulation,
                    "current_status": current_status,
                    "progress": sim_progress,
                }
        elif data_type == "progress":
            sim_id = int(data["data"]["simulation_id"])
            self.progresses[sim_id]["progress"] = Progress(0, data["data"]["progress"])
        elif data_type == "status":
            sim_id = int(data["data"]["simulation_id"])
            self.progresses[sim_id]["current_status"].name = data["data"]["status"]

        result = dict()
        for sim_id, item in self.progresses.items():
            result[sim_id] = (item.get("simulation"), item.get("current_status"), item.get("progress"))
        self.progresses_fetched.emit(result)


class DownloadProgressWorker(QObject):
    """Worker object responsible for downloading simulations results."""

    thread_finished = pyqtSignal(str)
    download_failed = pyqtSignal(str)
    download_progress = pyqtSignal(float)

    CHUNK_SIZE = 1024 ** 2

    NOT_STARTED = -1
    FINISHED = 100
    FAILED = 101

    def __init__(self, simulation, downloads, directory):
        super().__init__()
        self.simulation = simulation
        self.downloads = downloads
        self.directory = directory
        self.success = True

    @pyqtSlot()
    def run(self):
        """Downloading simulation results files."""
        if self.downloads:
            finished_message = f"Downloading results of {self.simulation.name} ({self.simulation.id}) finished!"
        else:
            finished_message = "Nothing to download!"
        total_size = sum(download.size for result_file, download in self.downloads)
        size = 0
        self.download_progress.emit(size)
        for result_file, download in self.downloads:
            filename = result_file.filename
            filename_path = os.path.join(self.directory, filename)
            try:
                os.makedirs(self.directory, exist_ok=True)
                file_data = requests.get(download.get_url, stream=True, timeout=15)
                with open(filename_path, "wb") as f:
                    for chunk in file_data.iter_content(chunk_size=self.CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
                            size += len(chunk)
                            self.download_progress.emit(size / total_size * 100)
                continue
            except Exception as e:
                error_msg = f"Error: {e}"
            self.download_progress.emit(self.FAILED)
            self.download_failed.emit(error_msg)
            self.success = False
            break
        if self.success is True:
            self.download_progress.emit(self.FINISHED)
            self.thread_finished.emit(finished_message)


class UploadWorkerSignals(QObject):
    """Definition of the upload worker signals."""

    thread_finished = pyqtSignal(int, str)
    upload_failed = pyqtSignal(int, str)
    upload_progress = pyqtSignal(int, str, float, float)  # upload row number, task name, task progress, total progress


class RevisionUploadError(Exception):
    """Custom revision upload exception."""

    pass


class UploadProgressWorker(QRunnable):
    """Worker object responsible for uploading models."""

    CHUNK_SIZE = 1024 ** 2
    TASK_CHECK_INTERVAL = 2.5
    TASK_CHECK_RETRIES = 4

    def __init__(self, threedi_api, upload_specification, upload_row_number):
        super().__init__()
        self.threedi_api = threedi_api
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
        if not upload_only:
            tasks.append(self.commit_revision_task)
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
        sqlite_file = os.path.basename(schematisation_sqlite)
        upload = self.tc.upload_schematisation_revision_sqlite(self.schematisation.id, self.revision.id, sqlite_file)
        upload_file(upload.put_url, schematisation_sqlite, self.CHUNK_SIZE, callback_func=self.monitor_upload_progress)

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
        self.current_task = f"UPLOAD RASTER\n({raster_type})"
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
        upload_file(raster_upload.put_url, raster_filepath, self.CHUNK_SIZE, callback_func=self.monitor_upload_progress)

    def delete_raster_task(self, raster_type):
        """Run raster file deletion task."""
        types_to_delete = [raster_type]
        if raster_type == "dem_file":
            types_to_delete.append("dem_raw_file")  # We need to remove legacy 'dem_raw_file` as well
        self.current_task = f"DELETE RASTER\n({raster_type})"
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
        model_checker_task = None
        revision_tasks = self.tc.fetch_schematisation_revision_tasks(self.schematisation.id, self.revision.id)
        self.current_task_progress = 50.0
        self.report_upload_progress()
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
                err = RevisionUploadError("'modelchecker' errors detected - please check your schematisation")
                raise err
            self.current_task_progress = 100.0
            self.report_upload_progress()
        else:
            err = RevisionUploadError("'modelchecker' task was not started properly")
            raise err

    def create_3di_model_task(self):
        """Run creation of the new model out of revision data."""
        self.current_task = "MAKE 3DI MODEL"
        self.current_task_progress = 0.0
        self.report_upload_progress()
        model = self.tc.create_schematisation_revision_3di_model(
            self.schematisation.id, self.revision.id, **self.revision.to_dict()
        )
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
            model_tasks = self.tc.fetch_3di_model_tasks(model.id)
            for task in model_tasks:
                task_status = task.status
                if task_status == "success":
                    finished_tasks[task.name] = True
                elif task_status == "failure":
                    err = RevisionUploadError(task.detail["message"])
                    raise err
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
