import json
import tempfile
import time
from pathlib import Path

import urllib3
from threedi_api_client import ThreediApi
from threedi_api_client.files import download_file, upload_file

from threedi_models_and_simulations.processing.utils import MockFeedback, ProcessingException

DOWNLOAD_TIMEOUT = urllib3.Timeout(connect=60, read=600)


def add_substance_concentration(input_file, output_file, substance_id):
    # Load the original JSON data
    with open(input_file, 'r') as f:
        data = json.load(f)

    # Iterate over each entry in the data
    for entry in data:
        time_steps = [pair[0] for pair in entry.get('values', [])]
        concentrations = [[t, 100] for t in time_steps]

        entry['substances'] = [{
            "substance": substance_id,
            "concentrations": concentrations
        }]

    # Write the updated data to a new file
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=4)


def label_dwf(
    api_host: str,
    api_key: str,
    simulation_template_id: int,
    simulation_name: str,
    max_retries: int = 900,
    feedback=None
):
    """
    Creates a simulation from a template, labels DWF and adds the simulation to the queue.
    The simulation is owned by the same organisation that owns the simulation from which the template was made.
    Feedback (e.g. a QgsProcessingFeedback) should have the following methods:
    - pushInfo()
    """
    feedback = feedback or MockFeedback()

    config = {
        "THREEDI_API_HOST": api_host,
        "THREEDI_API_PERSONAL_API_TOKEN": api_key
    }

    api_client = ThreediApi(config=config, version='v3-beta')

    simulation_template = api_client.simulation_templates_read(simulation_template_id)
    feedback.pushInfo(f"Found simulation template '{simulation_template.name}' with id {simulation_template.id}")

    original_simulation_id = simulation_template.simulation.id
    lateral_files = api_client.simulations_events_lateral_file_list(original_simulation_id).results
    dwf_files = [f for f in lateral_files if f.periodic == "daily"]
    if not dwf_files:
        feedback.pushInfo(f"Simulation template does not have any dry weather flow events")
        return

    # Create new simulation from template
    simulation = api_client.simulations_from_template(
        data={
            "template": simulation_template.id,
            "name": simulation_name,
            "organisation": simulation_template.simulation.organisation,
            "start_datetime": simulation_template.simulation.start_datetime,
            "duration": simulation_template.simulation.duration
        }
    )
    feedback.pushInfo(f"Created simulation '{simulation.name}' with id {simulation.id}")

    dwf_substance = api_client.simulations_substances_create(simulation.id, {"name": "DWF (label)", "units": "%"})
    feedback.pushInfo(f"Created substance '{dwf_substance.name}' with id {dwf_substance.id}")

    # Download DWF laterals
    temp_dir = Path(tempfile.mkdtemp())  # creates a unique temp dir


    original_dwf_files = api_client.simulations_events_lateral_file_list(
        simulation_pk=simulation_template.simulation.id
    ).results
    original_dwf_file_paths = []
    for original_dwf_file in original_dwf_files:
        if original_dwf_file.periodic == "daily":
            original_dwf_file_download_url = api_client.simulations_events_lateral_file_download(
                simulation_pk=simulation_template.simulation.id,
                id=original_dwf_file.id
            ).get_url

            original_dwf_file_path = temp_dir / original_dwf_file.file.filename
            download_file(
                url=original_dwf_file_download_url,
                target=original_dwf_file_path,
                timeout=DOWNLOAD_TIMEOUT
            )
            original_dwf_file_paths.append(original_dwf_file_path)
            feedback.pushInfo(f"Downloaded {original_dwf_file_path}")

    # Add label to DWF
    edited_dwf_file_paths = []
    for original_dwf_file_path in original_dwf_file_paths:
        new_name = original_dwf_file_path.stem + "_with_label.json"
        edited_dwf_file_path = original_dwf_file_path.with_name(new_name)
        add_substance_concentration(original_dwf_file_path, edited_dwf_file_path, dwf_substance.id)
        edited_dwf_file_paths.append(edited_dwf_file_path)
        feedback.pushInfo(f"Added a label to {edited_dwf_file_path}, using substance id {dwf_substance.id}")

    # Delete existing DWF laterals from simulation
    lateral_files = api_client.simulations_events_lateral_file_list(simulation.id).results
    for lateral_file in lateral_files:
        if lateral_file.periodic == "daily":
            api_client.simulations_events_lateral_file_delete(lateral_file.id, simulation.id)
            feedback.pushInfo(f"Deleted lateral file {lateral_file.file.filename}")

    # Upload DWF laterals with labels
    for edited_dwf_file_path in edited_dwf_file_paths:
        upload_object = api_client.simulations_events_lateral_file_create(
            simulation.id,
            data={
                "filename": edited_dwf_file_path.name,
                "offset": 0,
                "periodic": "daily"
            }
        )
        res = upload_file(upload_object.put_url, edited_dwf_file_path)
        feedback.pushInfo(f"Processing DWF file...")
        laterals = api_client.simulations_events_lateral_file_list(simulation_pk=simulation.id).results
        found = False
        for lateral in laterals:
            if lateral.file.filename == edited_dwf_file_path.name:
                found = True
                feedback.pushInfo(f"Found lateral with id {lateral.id}")
                break
        if not found:
            raise ProcessingException("Lateral not found")
        wait_time = 1
        for i in range(max_retries):
            state = api_client.simulations_events_lateral_file_read(simulation_pk=simulation.id,
                                                                    id=lateral.id).file.state
            if state not in ["created", "uploaded", "processed"]:
                raise Exception(f"Something went wrong while processing uploaded laterals. State: {state}")
            if state == "processed":
                break
            time.sleep(wait_time)

        feedback.pushInfo("Finished processing laterals file")

    # Add simulation to queue
    api_client.simulations_actions_create(simulation.id, data={"name": "queue"})
    feedback.pushInfo(f"Added simulation '{simulation.name}' with id {simulation.id} to queue")
