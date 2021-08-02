# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import os
import json
import hashlib
import requests
from collections import OrderedDict
from datetime import datetime

PLUGIN_PATH = os.path.dirname(os.path.realpath(__file__))
CACHE_PATH = os.path.join(PLUGIN_PATH, "_cached_data")
TEMPLATE_PATH = os.path.join(CACHE_PATH, "templates.json")
LATERALS_FILE_TEMPLATE = os.path.join(CACHE_PATH, "laterals.json")
DWF_FILE_TEMPLATE = os.path.join(CACHE_PATH, "dwf.json")
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


def write_laterals_to_json(laterals_values, laterals_file_template):
    """Writing laterals values to the JSON file."""
    with open(laterals_file_template, "w") as json_file:
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


def apply_24h_timeseries(start_datetime, end_datetime, timeseries):
    """Applying 24 hours Dry Weather Flow timeseries based on simulation duration."""
    start_day = datetime(start_datetime.year, start_datetime.month, start_datetime.day)
    end_day = datetime(end_datetime.year, end_datetime.month, end_datetime.day)
    hour_in_sec = 3600
    day_in_sec = hour_in_sec * 24
    full_days_delta = end_day - start_day
    full_days_duration = full_days_delta.days + 1
    full_days_sec = full_days_duration * day_in_sec
    flow_ts = [ts[-1] for ts in timeseries]
    extended_flow_ts = flow_ts + flow_ts[1:] * (full_days_duration - 1)  # skipping 0.0 time step while extending TS
    full_days_seconds_range = range(0, full_days_sec + hour_in_sec, hour_in_sec)
    start_time_delta = start_datetime - start_day
    end_time_delta = end_datetime - start_day
    start_timestep = (start_time_delta.total_seconds() // hour_in_sec) * hour_in_sec
    end_timestep = (end_time_delta.total_seconds() // hour_in_sec) * hour_in_sec
    timestep = 0.0
    new_timeseries = []
    for extended_timestep, flow in zip(full_days_seconds_range, extended_flow_ts):
        if extended_timestep < start_timestep:
            continue
        elif end_timestep >= extended_timestep >= start_timestep:
            new_timeseries.append((timestep, flow))
            timestep += hour_in_sec
        else:
            break
    return new_timeseries
