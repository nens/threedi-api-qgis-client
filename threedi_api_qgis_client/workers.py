# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import logging
import os
import json
import requests
from qgis.PyQt.QtCore import QObject, QRunnable, QUrl, QByteArray, pyqtSignal, pyqtSlot
from qgis.PyQt import QtNetwork
from PyQt5 import QtWebSockets
from threedi_api_client.openapi import ApiException, Progress
from threedi_api_client.files import upload_file
from .api_calls.threedi_calls import ThreediCalls


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


class RunnableWorkerSignals(QObject):
    thread_finished = pyqtSignal(str)
    upload_failed = pyqtSignal(str)
    upload_progress = pyqtSignal(int, str, float, float)  # upload row index, task name, task progress, total progress


class UploadProgressWorker(QRunnable):
    """Worker object responsible for uploading models."""

    CHUNK_SIZE = 1024 ** 2

    def __init__(self, threedi_api, upload_specification, upload_row_idx):
        super().__init__()
        self.threedi_api = threedi_api
        self.upload_specification = upload_specification
        self.upload_idx = upload_row_idx
        self.current_task = "NO TASK"
        self.current_task_progress = 0.0
        self.total_progress = 0.0
        self.tc = None
        self.signals = RunnableWorkerSignals()

    @pyqtSlot()
    def run(self):
        """Uploading model to the schematisation."""
        self.tc = ThreediCalls(self.threedi_api)
        schematisation = self.upload_specification["schematisation"]
        schematisation_sqlite = self.upload_specification["sqlite_filepath"]
        sqlite_file = os.path.basename(schematisation_sqlite)
        commit_message = self.upload_specification["commit_message"]
        try:
            self.current_task = "CREATE REVISION"
            self.current_task_progress = 0.0
            self.total_progress = 0.0
            self.report_upload_progress()
            revision = self.tc.create_schematisation_revision(schematisation.id)
            new_rev_id = revision.id
            self.current_task_progress = 100.0
            self.total_progress = 10.0
            self.report_upload_progress()

            self.current_task = "DELETE REVISION SQLITE IF EXIST"
            self.current_task_progress = 0.0
            self.report_upload_progress()
            self.tc.delete_schematisation_revision_sqlite(schematisation.id, new_rev_id)
            self.current_task_progress = 100.0
            self.total_progress = 20.0
            self.report_upload_progress()

            self.current_task = "UPLOAD SPATIALITE"
            self.current_task_progress = 0.0
            self.report_upload_progress()
            upload = self.tc.upload_schematisation_revision_sqlite(schematisation.id, new_rev_id, sqlite_file)
            upload_file(
                upload.put_url, schematisation_sqlite, self.CHUNK_SIZE, callback_func=self.monitor_upload_progress
            )
            self.current_task_progress = 100.0
            self.total_progress = 80.0
            self.report_upload_progress()

            self.current_task = "COMMIT REVISION"
            self.current_task_progress = 0.0
            self.report_upload_progress()
            self.tc.commit_schematisation_revision(schematisation.id, new_rev_id, commit_message=commit_message)
            self.current_task_progress = 100.0
            self.total_progress = 100.0
            self.report_upload_progress()
            self.current_task = "DONE"
            self.report_upload_progress()

            self.signals.thread_finished.emit("Model upload finished!")
        except Exception as e:
            error_msg = f"Error: {e}"
            self.signals.upload_failed.emit(error_msg)

    def report_upload_progress(self):
        self.signals.upload_progress.emit(
            self.upload_idx, self.current_task, self.current_task_progress, self.total_progress
        )

    def monitor_upload_progress(self, chunk_size, total_size):
        upload_progress = chunk_size / total_size * 100
        self.current_task_progress = upload_progress
        self.report_upload_progress()
