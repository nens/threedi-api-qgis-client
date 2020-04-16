# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import os
import requests
from time import sleep
from qgis.PyQt.QtCore import QObject, pyqtSignal, pyqtSlot
from openapi_client import ApiException
from .api_calls.threedi_calls import ThreediCalls


class SimulationsProgressesSentinel(QObject):
    """Worker object that will be moved to a separate thread and will check progresses of the running simulations."""
    thread_finished = pyqtSignal(str)
    thread_failed = pyqtSignal(str)
    progresses_fetched = pyqtSignal(dict)

    DELAY = 5
    SIMULATIONS_REFRESH_TIME = 300

    def __init__(self, api_client):
        super(QObject, self).__init__()
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
        self.thread_finished.emit(stop_message)

    def stop(self):
        """Changing 'thread_active' flag to False."""
        self.thread_active = False


class DownloadProgressWorker(QObject):
    """Worker object responsible for downloading simulations results."""
    thread_finished = pyqtSignal(str)
    download_failed = pyqtSignal(str)
    download_progress = pyqtSignal(float)

    NOT_STARTED = -1
    FINISHED = 100
    FAILED = 101

    def __init__(self, simulation, downloads, directory):
        super(QObject, self).__init__()
        self.simulation = simulation
        self.downloads = downloads
        self.directory = directory

    @pyqtSlot()
    def run(self):
        """Downloading simulation results files."""
        if self.downloads:
            finished_message = f"Downloading results of {self.simulation.name} ({self.simulation.id}) finished!"
        else:
            finished_message = "Nothing to download!"
        success = True
        total_size = sum(download.size for result_file, download in self.downloads)
        size = 0
        self.download_progress.emit(size)
        for result_file, download in self.downloads:
            filename = result_file.filename
            filename_path = os.path.join(self.directory, filename)
            try:
                os.makedirs(self.directory, exist_ok=True)
                with open(filename_path, 'wb') as f:
                    file_data = requests.get(download.get_url)
                    f.write(file_data.content)
                    size += download.size
                    self.download_progress.emit(size / total_size * 100)
                    continue
            except requests.RequestException as e:
                error_details = e.response
                error_msg = f"Error: {error_details}"
            except (OSError, PermissionError) as e:
                error_msg = f"Error: {e}"
            self.download_progress.emit(self.FAILED)
            self.download_failed.emit(error_msg)
            success = False
            break
        if success is True:
            self.download_progress.emit(self.FINISHED)
            self.thread_finished.emit(finished_message)
