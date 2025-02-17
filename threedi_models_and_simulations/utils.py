# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import hashlib
import json
import os
import tempfile
from collections import OrderedDict
from datetime import datetime
from enum import Enum
from typing import List
from zipfile import ZIP_DEFLATED, ZipFile

import requests

TEMPDIR = tempfile.gettempdir()
PLUGIN_PATH = os.path.dirname(os.path.realpath(__file__))
CACHE_PATH = os.path.join(PLUGIN_PATH, "_cached_data")
TEMPLATE_PATH = os.path.join(CACHE_PATH, "templates.json")
INITIAL_WATERLEVELS_TEMPLATE = os.path.join(CACHE_PATH, "initial_waterlevels.json")
INITIAL_CONCENTRATIONS_TEMPLATE = os.path.join(CACHE_PATH, "initial_concentrations.json")
BOUNDARY_CONDITIONS_TEMPLATE = os.path.join(CACHE_PATH, "boundary_conditions.json")
LATERALS_FILE_TEMPLATE = os.path.join(CACHE_PATH, "laterals.json")
DWF_FILE_TEMPLATE = os.path.join(CACHE_PATH, "dwf.json")
DATA_PATH = os.path.join(PLUGIN_PATH, "_data")
EMPTY_DB_PATH = os.path.join(DATA_PATH, "empty.gpkg")
CHUNK_SIZE = 1024**2
RADAR_ID = "d6c2347d-7bd1-4d9d-a1f6-b342c865516f"
API_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"
USER_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class EventTypes(Enum):
    CONSTANT = "Constant"
    FROM_CSV = "From CSV"
    FROM_NETCDF = "From NetCDF"
    DESIGN = "Design"
    RADAR = "Radar - NL Only"


class UploadFileStatus(Enum):
    """Possible actions on files upload."""

    NO_CHANGES_DETECTED = "NO CHANGES DETECTED"
    CHANGES_DETECTED = "CHANGES DETECTED"
    NEW = "NEW"
    DELETED_LOCALLY = "DELETED LOCALLY"
    INVALID_REFERENCE = "INVALID REFERENCE!"


class UploadFileType(Enum):
    """File types of the uploaded files."""

    DB = "DB"
    RASTER = "RASTER"


class FileState(Enum):
    """Possible uploaded file states."""

    CREATED = "created"
    UPLOADED = "uploaded"
    PROCESSED = "processed"
    ERROR = "error"
    REMOVED = "removed"


class ThreediFileState(Enum):
    """Possible 3Di file states."""

    PROCESSING = "processing"
    VALID = "valid"
    INVALID = "invalid"


class ThreediModelTaskStatus(Enum):
    """Possible 3Di Model Task statuses."""

    PENDING = "pending"
    SENT = "sent"
    RECEIVED = "received"
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"
    REVOKED = "revoked"


class BreachSourceType(Enum):
    POTENTIAL_BREACHES = "Potential breaches"
    FLOWLINES = "1D2D Flowlines"


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


def units_to_seconds(units="s"):
    """Converting timestep to seconds."""
    if units == "s":
        seconds_per_unit = 1
    elif units == "mins":
        seconds_per_unit = 60
    elif units == "hrs":
        seconds_per_unit = 3600
    else:
        raise ValueError(f"Unsupported timestep units format ({units})!")
    return seconds_per_unit


def convert_timeseries_to_seconds(timeseries, units="s"):
    """Converting timeseries to seconds."""
    seconds_per_unit = units_to_seconds(units)
    converted_timeseries = [[t * seconds_per_unit, v] for (t, v) in timeseries]
    return converted_timeseries


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


def read_json_data(json_filepath):
    """Parse and return data from JSON file."""
    with open(json_filepath, "r+") as json_file:
        data = json.load(json_file)
        return data


def write_json_data(values, json_file_template):
    """Writing data to the JSON file."""
    with open(json_file_template, "w") as json_file:
        jsonf = json.dumps(values)
        json_file.write(jsonf)


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


def upload_local_file(upload, filepath):
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


def is_file_checksum_equal(file_path, etag):
    """Checking if etag (MD5 checksum) matches checksum calculated for a given file."""
    with open(file_path, "rb") as file_to_check:
        data = file_to_check.read()
        md5_returned = hashlib.md5(data).hexdigest()
        return etag == md5_returned


def zip_into_archive(file_path, compression=ZIP_DEFLATED):
    """Zip file."""
    zip_filename = os.path.basename(file_path)
    zip_filepath = file_path.rsplit(".", 1)[0] + ".zip"
    with ZipFile(zip_filepath, "w", compression=compression) as zf:
        zf.write(file_path, arcname=zip_filename)
    return zip_filepath


def unzip_archive(zip_filepath, location=None):
    """Unzip archive content."""
    if not location:
        location = os.path.dirname(zip_filepath)
    with ZipFile(zip_filepath, "r") as zf:
        content_list = zf.namelist()
        zf.extractall(location)
        return content_list


def extract_error_message(e):
    """Extracting useful information from ApiException exceptions."""
    error_body = e.body
    try:
        if isinstance(error_body, str):
            error_body = json.loads(error_body)
        if "detail" in error_body:
            error_details = error_body["detail"]
        elif "details" in error_body:
            error_details = error_body["details"]
        elif "errors" in error_body:
            errors = error_body["errors"]
            try:
                error_parts = [f"{err['reason']} ({err['instance']['related_object']})" for err in errors]
            except TypeError:
                error_parts = list(errors.values())
            error_details = "\n" + "\n".join(error_parts)
        else:
            error_details = str(error_body)
    except json.JSONDecodeError:
        error_details = str(error_body)
    error_msg = f"Error: {error_details}"
    return error_msg


def handle_csv_header(header: List[str]):
    """
    Handle CSV header.
    Return None if fetch successful or error message if file is empty or have invalid structure.
    """
    error_message = None
    if not header:
        error_message = "CSV file is empty!"
        return error_message
    if "id" not in header:
        error_message = "Missing 'id' column in CSV file!"
    if "timeseries" not in header:
        error_message = "Missing 'timeseries' column in CSV file!"
    return error_message


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


def split_to_even_chunks(collection, chunk_length):
    """Split collection to even chunks list."""
    return [collection[i : i + chunk_length] for i in range(0, len(collection), chunk_length)]


def intervals_are_even(time_series):
    """Check if intervals in the time series are all even."""
    expected_interval = time_series[1][0] - time_series[0][0]
    time_steps = [time_step for time_step, value in time_series]
    for start_time_step, end_time_step in zip(time_steps, time_steps[1:]):
        if end_time_step - start_time_step != expected_interval:
            return False
    return True


def parse_version_number(version_str):
    """Parse version number in a string format and convert it into list of an integers."""
    version = [int(i) for i in version_str.split(".") if i.isnumeric()]
    return version


def constains_only_ascii(text):
    return all(ord(c) < 128 for c in text)


def parse_timeseries(timeseries: str):
    """Parse the timeseries from the given string."""
    return [[float(f) for f in line.split(",")] for line in timeseries.split("\n")]


def translate_illegal_chars(text, illegal_characters=r'\/:*?"<>|', replacement_character="-"):
    """Remove illegal characters from the text."""
    sanitized_text = "".join(char if char not in illegal_characters else replacement_character for char in text)
    return sanitized_text


class NestedObject:
    """A class to convert a nested dictionary into an object."""

    def __init__(self, data):
        for key, value in data.items():
            if isinstance(value, (list, tuple)):
                setattr(self, key, [NestedObject(x) if isinstance(x, dict) else x for x in value])
            else:
                setattr(self, key, NestedObject(value) if isinstance(value, dict) else value)


class SchematisationRasterReferences:

    @staticmethod
    def settings_to_api_raster_types():
        raster_type_map = {
            "friction_coefficient_file": "frict_coef_file",
            "max_infiltration_volume_file": "max_infiltration_capacity_file",
            "groundwater_hydraulic_conductivity_file": "groundwater_hydro_connectivity_file",
        }
        return raster_type_map

    @staticmethod
    def api_to_settings_raster_types():
        raster_type_map = {v: k for k, v in SchematisationRasterReferences.settings_to_api_raster_types().items()}
        return raster_type_map

    @staticmethod
    def api_client_raster_type(settings_raster_type):
        try:
            return SchematisationRasterReferences.settings_to_api_raster_types()[settings_raster_type]
        except KeyError:
            return settings_raster_type

    @staticmethod
    def settings_raster_type(api_raster_type):
        try:
            return SchematisationRasterReferences.api_to_settings_raster_types()[api_raster_type]
        except KeyError:
            return api_raster_type

    @staticmethod
    def model_settings_rasters():
        """Rasters mapping from the Model settings layer."""
        raster_info = OrderedDict(
            (
                ("dem_file", "Digital elevation model [m MSL]"),
                ("friction_coefficient_file", "Friction coefficient [-]"),
            )
        )
        return raster_info

    @staticmethod
    def initial_conditions_rasters():
        """Rasters mapping for the Initial conditions."""
        raster_info = OrderedDict(
            (
                ("initial_groundwater_level_file", "Initial groundwater level [m MSL]"),
                ("initial_water_level_file", "Initial water level [m MSL]"),
            )
        )
        return raster_info

    @staticmethod
    def interception_rasters():
        """Rasters mapping for the Interception."""
        raster_info = OrderedDict((("interception_file", "Interception [m]"),))
        return raster_info

    @staticmethod
    def simple_infiltration_rasters():
        """Rasters mapping for the Infiltration."""
        raster_info = OrderedDict(
            (
                ("infiltration_rate_file", "Infiltration rate [mm/d]"),
                ("max_infiltration_volume_file", "Max infiltration volume [m]"),
            )
        )
        return raster_info

    @staticmethod
    def groundwater_rasters():
        """Rasters mapping for the Groundwater."""
        raster_info = OrderedDict(
            (
                ("equilibrium_infiltration_rate_file", "Equilibrium infiltration rate [mm/d]"),
                ("groundwater_hydraulic_conductivity_file", "Hydraulic conductivity [m/day]"),
                ("groundwater_impervious_layer_level_file", "Impervious layer level [m MSL]"),
                ("infiltration_decay_period_file", "Infiltration decay period [d]"),
                ("initial_infiltration_rate_file", "Initial infiltration rate [mm/d]"),
                ("leakage_file", "Leakage [mm/d]"),
                ("phreatic_storage_capacity_file", "Phreatic storage capacity [-]"),
            )
        )
        return raster_info

    @staticmethod
    def interflow_rasters():
        """Rasters mapping for the Interflow."""
        raster_info = OrderedDict(
            (
                ("hydraulic_conductivity_file", "Hydraulic conductivity [m/d]"),
                ("porosity_file", "Porosity [-]"),
            )
        )
        return raster_info

    @staticmethod
    def vegetation_drag_rasters():
        """Rasters mapping for the Vegetation drag settings."""
        raster_info = OrderedDict(
            (
                ("vegetation_height_file", "Vegetation height [m]"),
                ("vegetation_stem_count_file", "Vegetation stem count [-]"),
                ("vegetation_stem_diameter_file", "Vegetation stem diameter [m]"),
                ("vegetation_drag_coefficient_file", "Vegetation drag coefficient [-]"),
            )
        )
        return raster_info

    @classmethod
    def raster_reference_tables(cls):
        """GeoPackage tables mapping with references to the rasters."""
        reference_tables = OrderedDict(
            (
                ("model_settings", cls.model_settings_rasters()),
                ("initial_conditions", cls.initial_conditions_rasters()),
                ("interception", cls.interception_rasters()),
                ("simple_infiltration", cls.simple_infiltration_rasters()),
                ("groundwater", cls.groundwater_rasters()),
                ("interflow", cls.interflow_rasters()),
                ("vegetation_drag_2d", cls.vegetation_drag_rasters()),
            )
        )
        return reference_tables

    @classmethod
    def raster_table_mapping(cls):
        """Rasters to geopackage tables mapping."""
        table_mapping = {}
        for table_name, raster_files_references in cls.raster_reference_tables().items():
            for raster_type in raster_files_references.keys():
                table_mapping[raster_type] = table_name
        return table_mapping
