# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import os
import json
import hashlib
import requests
from collections import OrderedDict

PLUGIN_PATH = os.path.dirname(os.path.realpath(__file__))
CACHE_PATH = os.path.join(PLUGIN_PATH, "_cached_data")
TEMPLATE_PATH = os.path.join(CACHE_PATH, "templates.json")
LATERALS_FILE_TEMPLATE = os.path.join(CACHE_PATH, "laterals.json")
CHUNK_SIZE = 1024 ** 2


def mmh_to_ms(mmh_value):
    """Converting values from 'mm/h' to the 'm/s'."""
    ms_value = mmh_value / 3600 * 0.001
    return ms_value


def ms_to_mmh(ms_value):
    """Converting values from 'm/s' to the 'mm/h'."""
    mmh_value = ms_value * 3600 * 1000
    return mmh_value


def mmtimestep_to_mmh(value, timestep, units="s"):
    """Converting values from 'mm/timestep' to the 'mm/h'."""
    if units == "s":
        timestep_seconds = timestep
    elif units == "mins":
        timestep_seconds = timestep * 60
    elif units == "hrs":
        timestep_seconds = timestep * 3600
    else:
        raise ValueError(f"Unsupported timestep units format ({units})!")
    value_per_second = value / timestep_seconds
    mmh_value = value_per_second * 3600
    return mmh_value


def mmh_to_mmtimestep(value, timestep, units="s"):
    """Converting values from 'mm/h' to the 'mm/timestep'."""
    if units == "s":
        timestep_seconds = timestep
    elif units == "mins":
        timestep_seconds = timestep * 60
    elif units == "hrs":
        timestep_seconds = timestep * 3600
    else:
        raise ValueError(f"Unsupported timestep units format ({units})!")
    value_per_second = value / 3600
    mmtimestep_value = value_per_second * timestep_seconds
    return mmtimestep_value


def load_saved_templates():
    """Loading parameters from saved template."""
    items = OrderedDict()
    with open(TEMPLATE_PATH, "a"):
        os.utime(TEMPLATE_PATH, None)
    with open(TEMPLATE_PATH, "r+") as json_file:
        data = {}
        if os.path.getsize(TEMPLATE_PATH):
            data = json.load(json_file)
        for name, parameters in sorted(data.items()):
            items[name] = parameters
    return items


def write_template(template_name, simulation_template):
    """Writing parameters as a template."""
    with open(TEMPLATE_PATH, "a"):
        os.utime(TEMPLATE_PATH, None)
    with open(TEMPLATE_PATH, "r+") as json_file:
        data = {}
        if os.path.getsize(TEMPLATE_PATH):
            data = json.load(json_file)
        data[template_name] = simulation_template
        jsonf = json.dumps(data)
        json_file.seek(0)
        json_file.write(jsonf)
        json_file.truncate()


def write_laterals_to_json(laterals_values):
    """Writing laterals values to the JSON file."""
    with open(LATERALS_FILE_TEMPLATE, "w") as json_file:
        jsonf = json.dumps(laterals_values)
        json_file.write(jsonf)


def upload_file(upload, filepath):
    """Upload file."""
    with open(filepath, "rb") as file:
        response = requests.put(upload.put_url, data=file)
        return response


def file_cached(file_path):
    """Checking if file exists."""
    return os.path.isfile(file_path)


def get_download_file(download, file_path):
    """Getting file from Download object and writing it under given path."""
    r = requests.get(download.get_url, stream=True, timeout=15)
    with open(file_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                f.write(chunk)


def check_download_checksum(download, filename):
    """Checking if Download object MD5 checksum matches checksum calculated for a cached file."""
    file_path = os.path.join(CACHE_PATH, filename)
    with open(file_path, "rb") as file_to_check:
        data = file_to_check.read()
        md5_returned = hashlib.md5(data).hexdigest()
        return download.etag == md5_returned


def extract_error_message(e):
    """Extracting useful information from ApiException exceptions."""
    error_body = e.body
    try:
        if isinstance(error_body, str):
            error_body = json.loads(error_body)
        if "details" in error_body:
            error_details = error_body["details"]
        elif "errors" in error_body:
            errors = error_body["errors"]
            error_parts = [f"{err['reason']} ({err['instance']['related_object']})" for err in errors]
            error_details = "\n".join(error_parts)
        else:
            error_details = str(error_body)
    except json.JSONDecodeError:
        error_details = str(error_body)
    error_msg = f"Error: {error_details}"
    return error_msg
