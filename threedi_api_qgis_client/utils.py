# 3Di Models & Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import os
import json
import hashlib
import requests
import shutil
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED
from enum import Enum
from collections import OrderedDict, defaultdict
from itertools import chain
from datetime import datetime

TEMPDIR = tempfile.gettempdir()
PLUGIN_PATH = os.path.dirname(os.path.realpath(__file__))
CACHE_PATH = os.path.join(PLUGIN_PATH, "_cached_data")
TEMPLATE_PATH = os.path.join(CACHE_PATH, "templates.json")
LATERALS_FILE_TEMPLATE = os.path.join(CACHE_PATH, "laterals.json")
DWF_FILE_TEMPLATE = os.path.join(CACHE_PATH, "dwf.json")
DATA_PATH = os.path.join(PLUGIN_PATH, "_data")
EMPTY_DB_PATH = os.path.join(DATA_PATH, "empty.sqlite")
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


def read_json_data(json_filepath):
    """Parse and return data from JSON file."""
    with open(json_filepath, "r+") as json_file:
        data = json.load(json_file)
        return data


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


def is_file_checksum_equal(file_path, etag):
    """Checking if etag (MD5 checksum) matches checksum calculated for a given file."""
    with open(file_path, "rb") as file_to_check:
        data = file_to_check.read()
        md5_returned = hashlib.md5(data).hexdigest()
        return etag == md5_returned


def zip_sqlite(sqlite_filepath, compression=ZIP_DEFLATED):
    """Zip sqlite file."""
    sqlite_file = os.path.basename(sqlite_filepath)
    zip_filepath = sqlite_filepath.rsplit(".", 1)[0] + ".zip"
    with ZipFile(zip_filepath, "w", compression=compression) as zf:
        zf.write(sqlite_filepath, arcname=sqlite_file)
    return zip_filepath


def unzip_sqlite(zip_filepath, location=None):
    """Unzip sqlite file."""
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
        if "details" in error_body:
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


class LocalRevision:
    """Local revision directory structure representation."""

    def __init__(self, local_schematisation, revision_number=None, sqlite_filename=None):
        self.local_schematisation = local_schematisation
        self.number = revision_number
        self.sqlite_filename = sqlite_filename
        if not self.sqlite_filename and self.structure_is_valid():
            self.discover_sqlite()

    def structure_is_valid(self):
        """Check if all revision subpaths are present."""
        is_valid = all(os.path.exists(p) if p else False for p in self.subpaths)
        return is_valid

    @property
    def sub_dir(self):
        """Get schematisation revision subdirectory name."""
        if self.number:
            subdirectory = f"revision {self.number}"
            return subdirectory

    @property
    def main_dir(self):
        """Get schematisation revision main directory path."""
        if self.number:
            schematisation_dir_path = self.local_schematisation.main_dir
            schematisation_revision_dir_path = os.path.join(schematisation_dir_path, self.sub_dir)
            return schematisation_revision_dir_path

    @property
    def admin_dir(self):
        """Get schematisation revision admin directory path."""
        if self.number:
            admin_dir_path = os.path.join(self.main_dir, "admin")
            return admin_dir_path

    @property
    def grid_dir(self):
        """Get schematisation revision grid directory path."""
        if self.number:
            grid_dir_path = os.path.join(self.main_dir, "grid")
            return grid_dir_path

    @property
    def schematisation_dir(self):
        """Get schematisation revision schematisation directory path."""
        if self.number:
            grid_dir_path = os.path.join(self.main_dir, "schematisation")
            return grid_dir_path

    @property
    def raster_dir(self):
        """Get schematisation revision raster directory path."""
        if self.number:
            rasters_dir_path = os.path.join(self.main_dir, "schematisation", "rasters")
            return rasters_dir_path

    @property
    def sqlite(self):
        """Get schematisation revision sqlite filepath."""
        if not self.number:
            self.discover_sqlite()
            sqlite_filepath = (
                os.path.join(self.schematisation_dir, self.sqlite_filename) if self.sqlite_filename else None
            )
            return sqlite_filepath

    @property
    def subpaths(self):
        """Revision directory sub-paths."""
        paths = [
            self.admin_dir,
            self.grid_dir,
            self.schematisation_dir,
            self.raster_dir,
        ]
        return paths

    def make_revision_structure(self, exist_ok=True):
        """Function for schematisation dir structure creation."""
        for subpath in self.subpaths:
            if subpath:
                os.makedirs(subpath, exist_ok=exist_ok)

    def discover_sqlite(self):
        """Find schematisation revision sqlite filepath."""
        if self.number:
            for sqlite_candidate in os.listdir(self.schematisation_dir):
                if sqlite_candidate.endswith(".sqlite"):
                    self.sqlite_filename = sqlite_candidate
                    break


class WIPRevision(LocalRevision):
    """Local Work In Progress directory structure representation."""

    @property
    def sub_dir(self):
        """Get schematisation revision subdirectory name."""
        subdirectory = "work in progress"
        return subdirectory

    @property
    def main_dir(self):
        """Get schematisation revision main directory path."""
        schematisation_dir_path = self.local_schematisation.main_dir
        schematisation_revision_dir_path = os.path.join(schematisation_dir_path, self.sub_dir)
        return schematisation_revision_dir_path

    @property
    def admin_dir(self):
        """Get schematisation revision admin directory path."""
        admin_dir_path = os.path.join(self.main_dir, "admin")
        return admin_dir_path

    @property
    def grid_dir(self):
        """Get schematisation revision grid directory path."""
        grid_dir_path = os.path.join(self.main_dir, "grid")
        return grid_dir_path

    @property
    def schematisation_dir(self):
        """Get schematisation revision schematisation directory path."""
        grid_dir_path = os.path.join(self.main_dir, "schematisation")
        return grid_dir_path

    @property
    def raster_dir(self):
        """Get schematisation revision raster directory path."""
        rasters_dir_path = os.path.join(self.main_dir, "schematisation", "rasters")
        return rasters_dir_path

    @property
    def sqlite(self):
        """Get schematisation revision sqlite filepath."""
        self.discover_sqlite()
        sqlite_filepath = os.path.join(self.schematisation_dir, self.sqlite_filename) if self.sqlite_filename else None
        return sqlite_filepath

    def discover_sqlite(self):
        """Find schematisation revision sqlite filepath."""
        for sqlite_candidate in os.listdir(self.schematisation_dir):
            if sqlite_candidate.endswith(".sqlite"):
                self.sqlite_filename = sqlite_candidate
                break


class LocalSchematisation:
    """Local revision directory structure representation."""

    def __init__(self, working_dir, schematisation_pk, schematisation_name, parent_revision_number=None, create=False):
        self.working_directory = working_dir
        self.id = schematisation_pk
        self.name = schematisation_name
        self.revisions = OrderedDict()
        self.wip_revision = WIPRevision(self, parent_revision_number) if parent_revision_number is not None else None
        if create:
            self.build_schematisation_structure()

    def add_revision(self, revision_number):
        """Add a new revision."""
        local_revision = LocalRevision(self, revision_number)
        if revision_number in self.revisions and os.path.exists(local_revision.main_dir):
            shutil.rmtree(local_revision.main_dir)
        local_revision.make_revision_structure()
        self.revisions[revision_number] = local_revision
        self.write_schematisation_metadata()
        return local_revision

    def set_wip_revision(self, revision_number):
        """Set a new work in progress revision."""
        if self.wip_revision is not None and os.path.exists(self.wip_revision.main_dir):
            shutil.rmtree(self.wip_revision.main_dir)
        self.wip_revision = WIPRevision(self, revision_number)
        self.wip_revision.make_revision_structure()
        self.wip_revision.discover_sqlite()
        self.write_schematisation_metadata()
        return self.wip_revision

    def update_wip_revision(self, revision_number):
        """Update a work in progress revision number."""
        if self.wip_revision is not None and os.path.exists(self.wip_revision.main_dir):
            self.wip_revision.number = revision_number
            self.write_schematisation_metadata()
            return True
        else:
            return False

    @classmethod
    def initialize_from_location(cls, schematisation_dir):
        """Initialize local schematisation structure from the root schematisation dir."""
        local_schematisation = None
        if os.path.isdir(schematisation_dir):
            expected_config_path = os.path.join(schematisation_dir, "admin", "schematisation.json")
            if os.path.exists(expected_config_path):
                schema_metadata = cls.read_schematisation_metadata(expected_config_path)
                working_dir = os.path.dirname(schematisation_dir)
                schematisation_pk = schema_metadata["id"]
                schematisation_name = schema_metadata["name"]
                local_schematisation = cls(working_dir, schematisation_pk, schematisation_name)
                revision_numbers = schema_metadata["revisions"] or []
                for revision_number in revision_numbers:
                    local_revision = LocalRevision(local_schematisation, revision_number)
                    local_schematisation.revisions[revision_number] = local_revision
                wip_parent_revision_number = schema_metadata["wip_parent_revision"]
                if wip_parent_revision_number is not None:
                    local_schematisation.wip_revision = WIPRevision(local_schematisation, wip_parent_revision_number)
        return local_schematisation

    @staticmethod
    def read_schematisation_metadata(schematisation_config_path):
        """Read schematisation metadata from the JSON file."""
        schematisation_metadata = defaultdict(lambda: None)
        if os.path.exists(schematisation_config_path):
            with open(schematisation_config_path, "r+") as config_file:
                schematisation_metadata.update(json.load(config_file))
        return schematisation_metadata

    def write_schematisation_metadata(self):
        """Write schematisation metadata to the JSON file."""
        schematisation_metadata = {
            "id": self.id,
            "name": self.name,
            "revisions": [local_revision.number for local_revision in self.revisions.values()],
            "wip_parent_revision": self.wip_revision.number if self.wip_revision is not None else None,
        }
        with open(self.schematisation_config_path, "w") as config_file:
            config_file_dump = json.dumps(schematisation_metadata)
            config_file.write(config_file_dump)

    def structure_is_valid(self):
        """Check if all schematisation subpaths are present."""
        subpaths_collections = [self.subpaths]
        subpaths_collections += [local_revision.subpaths for local_revision in self.revisions.values()]
        subpaths_collections.append(self.wip_revision.subpaths)
        is_valid = all(os.path.exists(p) if p else False for p in chain.from_iterable(subpaths_collections))
        return is_valid

    @property
    def main_dir(self):
        """Get schematisation main directory."""
        schematisation_dir_path = os.path.normpath(os.path.join(self.working_directory, self.name))
        return schematisation_dir_path

    @property
    def admin_dir(self):
        """Get schematisation admin directory path."""
        admin_dir_path = os.path.join(self.main_dir, "admin")
        return admin_dir_path

    @property
    def subpaths(self):
        """Get schematisation directory sub-paths."""
        paths = [self.admin_dir]
        return paths

    @property
    def schematisation_config_path(self):
        """Get schematisation configuration filepath."""
        config_path = os.path.join(self.admin_dir, "schematisation.json")
        return config_path

    @property
    def sqlite(self):
        """Get schematisation work in progress revision sqlite filepath."""
        return self.wip_revision.sqlite

    def build_schematisation_structure(self):
        """Function for schematisation dir structure creation."""
        for schema_subpath in self.subpaths:
            os.makedirs(schema_subpath, exist_ok=True)
        for local_revision in self.revisions:
            local_revision.make_revision_structure()
        if self.wip_revision is not None:
            self.wip_revision.make_revision_structure()
        self.write_schematisation_metadata()


def list_local_schematisations(working_dir):
    """Get local schematisations present in the given directory."""
    local_schematisations = OrderedDict()
    for basename in os.listdir(working_dir):
        full_path = os.path.join(working_dir, basename)
        local_schematisation = LocalSchematisation.initialize_from_location(full_path)
        if local_schematisation is not None:
            local_schematisations[local_schematisation.id] = local_schematisation
    return local_schematisations


def replace_revision_data(source_revision, target_revision):
    """Replace target revision content with the source revision data."""
    shutil.rmtree(target_revision.main_dir)
    shutil.copytree(source_revision.main_dir, target_revision.main_dir)
