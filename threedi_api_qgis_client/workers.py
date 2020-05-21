# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import json
import os
import requests
from time import sleep

from dateutil.parser import parse
from qgis.PyQt.QtCore import QObject, pyqtSignal, pyqtSlot
from openapi_client import ApiException, Simulation, CurrentStatus, Progress

from threedi_api_qgis_client.api_calls.ws_qt import ClientWS
from .api_calls.threedi_calls import ThreediCalls


class SimulationsProgressesSentinel(QObject):
    """Worker object that will be moved to a separate thread and will check progresses of the running simulations."""
    thread_finished = pyqtSignal(str)
    thread_failed = pyqtSignal(str)
    progresses_fetched = pyqtSignal(dict)

    DELAY = 5
    SIMULATIONS_REFRESH_TIME = 300

    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self.simulations_list = []
        self.refresh_at_step = int(self.SIMULATIONS_REFRESH_TIME / self.DELAY)
        self.progresses = None
        self.thread_active = True

    @pyqtSlot()
    def run(self):
        """Checking running simulations progresses."""
        stop_message = "Checking running simulation stopped."
        try:
            tc = ThreediCalls(self.api_client)
            counter = 0
            while self.thread_active:
                if counter == self.refresh_at_step:
                    del self.simulations_list[:]
                    counter -= self.refresh_at_step
                self.progresses = tc.all_simulations_progress(self.simulations_list)
                self.progresses_fetched.emit(self.progresses)
                sleep(self.DELAY)
                counter += 1
        except ApiException as e:
            error_body = e.body
            error_details = error_body["details"] if "details" in error_body else error_body
            error_msg = f"Error: {error_details}"
            self.thread_failed.emit(error_msg)
        except Exception as e:
            error_msg = f"Error: {e}"
            self.thread_failed.emit(error_msg)
        self.thread_finished.emit(stop_message)

    def stop(self):
        """Changing 'thread_active' flag to False."""
        self.thread_active = False


class DownloadProgressWorker(QObject):
    """Worker object responsible for downloading simulations results."""
    thread_finished = pyqtSignal(str)
    download_failed = pyqtSignal(str)
    download_progress = pyqtSignal(float)

    CHUNK_SIZE = 1024**2

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
                with open(filename_path, 'wb') as f:
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


class WsProgressesSentinel(QObject):
    """Worker object that will be moved to a separate thread and will check progresses of the running simulations."""
    thread_finished = pyqtSignal(str)
    thread_failed = pyqtSignal(str)
    progresses_fetched = pyqtSignal(dict)

    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self.tc = ThreediCalls(self.api_client)

        self.simulations_list = []
        self.progresses = None
        self.thread_active = True
        self.progresses = {}

    @pyqtSlot()
    def run(self):
        """Checking running simulations progresses."""
        token = self.api_client.configuration.access_token
        ws_client = ClientWS(self, self.all_simulations_progress_web_socket, token)

    def stop(self):
        """Changing 'thread_active' flag to False."""
        self.thread_active = False

    def all_simulations_progress_web_socket(self, data):
        """Get all simulations progresses."""
        data = json.loads(data)
        print(data)
        # my code which demonstrate progress bar update by websocket
        if data.get("type") == "active-simulations" or data.get("type") == "active-simulation":
            simulations = data.get("data")
            self.progresses.clear()
            for id, sim in simulations.items():
                sim = json.loads(sim)
                simulation = Simulation(slug=sim.get("simulation_slug"), uuid=sim.get("uuid"), name=sim.get("name"),
                                        created=sim.get("date_created"), start_datetime=parse(sim.get("date_created")), organisation_name=sim.get("organisation_name"), organisation=sim.get("organisation_name"),
                                        user=sim.get("user_name"), duration=sim.get("duration"), id=id, threedimodel="xxx")

                current_status = self.tc.simulation_current_status(id)
                status_name = current_status.name
                status_time = current_status.time
                if status_time is None:
                    status_time = 0
                if status_name == "initialized":
                    sim_progress = Progress(0, sim.get("progress"))
                else:
                    sim_progress = Progress(percentage=0, time=status_time)
                self.progresses[int(id)] = {"simulation": simulation, "current_status": current_status, "progress": sim_progress}
        if data.get("type") == "progress":
            self.progresses[data["data"]["simulation_id"]]["progress"] = Progress(0, data["data"]["progress"])

        if data.get("type") == "status":
            self.progresses[data["data"]["simulation_id"]]["current_status"].name = data["data"]["status"]

        result = dict()
        for id, item in self.progresses.items():
            result[id] = (item.get("simulation"), item.get("current_status"), item.get("progress"))
        self.progresses_fetched.emit(result)
        # end of code

