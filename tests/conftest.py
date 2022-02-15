# 3Di Models & Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2022 by Lutra Consulting for 3Di Water Management
import datetime


TEST_API_PARAMETERS = ("TEST_USERNAME", "TEST_PASSWORD", "TEST_API")
REPO_DATA_LIST = [
    {
        "id": 1,
        "organisation": "qwertyhash",
        "revision": ["api-qgis-demo1 - 1056fd7b1d95e184aa807162f1a5e2a7a505608e"],
        "slug": "api-qgis-demo1",
        "url": "https://testapi/repositories/1/",
    },
    {
        "id": 2,
        "organisation": "qwertyhash",
        "revision": ["api-qgis-demo2 - 1156fd7b1d95e184aa807162f1a5e2a7a505608e"],
        "slug": "api-qgis-demo2",
        "url": "https://testapi/repositories/2/",
    },
]
SIM_DATA_LIST = [
    {
        "created": "2 days ago",
        "duration": 72000,
        "duration_humanized": "20 hours, 0 minutes, 0 seconds",
        "end_datetime": datetime.datetime(2020, 3, 3, 6, 30, 12),
        "id": 1201,
        "name": "qgis client test run 1",
        "organisation": "qwertyhash",
        "organisation_name": "Lutra Consulting",
        "start_datetime": datetime.datetime(2020, 3, 2, 10, 30, 12),
        "tags": None,
        "threedimodel": "https://testapi/threedimodels/14/",
        "threedimodel_id": "14",
        "url": "https://testapi/simulations/1200/",
        "user": "lukasz.debek",
        "uuid": "55e63655-6102-4653-b0fe-901fb5686420",
    },
    {
        "created": "a day ago",
        "duration": 72000,
        "duration_humanized": "20 hours, 0 minutes, 0 seconds",
        "end_datetime": datetime.datetime(2020, 3, 3, 11, 19, 3),
        "id": 1202,
        "name": "qgis client test run 2",
        "organisation": "qwertyhash",
        "organisation_name": "Lutra Consulting",
        "start_datetime": datetime.datetime(2020, 3, 2, 15, 19, 3),
        "tags": None,
        "threedimodel": "https://testapi/threedimodels/14/",
        "threedimodel_id": "14",
        "url": "https://testapi/simulations/1203/",
        "user": "lukasz.debek",
        "uuid": "846a5952-c174-4d04-a9e5-44788a841eb7",
    },
]

SINGLE_SIM_DATA = {
    "id": 1000,
    "name": "Bad Simulation",
    "threedimodel": "14",
    "organisation": "qwertyhash",
    "start_datetime": datetime.datetime.utcnow(),
    "duration": 72000,
}

BAD_SIM_DATA = {
    "name": "qgis client test run",
    "threedimodel": "14",
    "organisation": "qwertyhash",
    "start_datetime": datetime.datetime.utcnow(),
    "duration": 72000,
}

ACTION_DATA = {"duration": None, "name": "start", "timeout": None}

PROGRESS_DATA = {"percentage": 25, "time": 18000}

CONSTANT_RAIN_DATA = {"duration": 5000, "offset": 60, "units": "m/s", "value": 0.0006}

RAIN_TIME_SERIES = [[0, 0.0005], [300, 0.0008], [1200, 0.0001]]

TIME_SERIES_RAIN_DATA = {"offset": 0, "interpolate": False, "values": RAIN_TIME_SERIES, "units": "m/s"}

REVISION_DATA_LIST = [
    {
        "hash": "qwertyhash1",
        "id": 1,
        "is_pinned": False,
        "number": 0,
        "repository": "https://testapi/repositories/1/",
        "url": "https://testapi/revisions/1/",
    },
    {
        "hash": "qwertyhash2",
        "id": 2,
        "is_pinned": False,
        "number": 0,
        "repository": "https://testapi/repositories/1/",
        "url": "https://testapi/revisions/2/",
    },
]

MODEL_DATA_LIST = [
    {
        "breach_count": "16",
        "description": "",
        "disabled": False,
        "epsg": 28892,
        "extent_one_d": "{'type': 'LineString', 'coordinates': [[4.65566310525691, "
        "52.590857471993935], [4.808619107856248, "
        "52.69717725606727]]}",
        "extent_two_d": "{'type': 'LineString', 'coordinates': [[4.668275740999323, "
        "52.619558911160205], [4.738494268493689, "
        "52.66453975864303]]}",
        "extent_zero_d": None,
        "id": 14,
        "inp_success": True,
        "inpy_version": "3.0.26.4-1.4.19-1",
        "lines_count": 18620,
        "model_ini": "v2_bergermeer_simple_infil_no_grndwtr.ini",
        "name": "romantic_elion",
        "nodes_count": 9068,
        "repository_slug": "api-qgis-demo",
        "revision": "https://testapi/revisions/2/",
        "revision_hash": "qwertyhash2",
        "slug": "api-qgis-demo-v2_bergermeer_simple_infil_no_grndwtr-0-6356fd7b1d95e184aa807162f1a5e2a7a505608e",
        "storage_space": 296327439,
        "storage_space_humanized": "296.3 MB",
        "url": "https://testapi/threedimodels/14/",
    },
    {
        "breach_count": "16",
        "description": "",
        "disabled": False,
        "epsg": 28892,
        "extent_one_d": "{'type': 'LineString', 'coordinates': [[4.65566310525691, "
        "52.590857471993935], [4.808619107856248, "
        "52.69717725606727]]}",
        "extent_two_d": "{'type': 'LineString', 'coordinates': [[4.668275740999323, "
        "52.619558911160205], [4.738494268493689, "
        "52.66453975864303]]}",
        "extent_zero_d": None,
        "id": 15,
        "inp_success": True,
        "inpy_version": "3.0.26.4-1.4.19-1",
        "lines_count": 18620,
        "model_ini": "v2_bergermeer_simple_infil_no_grndwtr.ini",
        "name": "romantic_elion",
        "nodes_count": 9068,
        "repository_slug": "api-qgis-demo",
        "revision": "https://testapi/revisions/2/",
        "revision_hash": "qwertyhash2",
        "slug": "api-qgis-demo-v2_bergermeer_simple_infil_no_grndwtr-0-6356fd7b1d95e184aa807162f1a5e2a7a505608e",
        "storage_space": 296327439,
        "storage_space_humanized": "296.3 MB",
        "url": "https://testapi/threedimodels/15/",
    },
]

CURRENT_STATUSES_LIST = [
    {"created": datetime.datetime.utcnow(), "id": 1201, "name": "initialized", "paused": None, "time": 18000.0},
    {"created": datetime.datetime.utcnow(), "id": 1202, "name": "finished", "paused": None, "time": 72000.0},
]


SIM_EXCEPTION_BODY = {"duration": ["minimum value for duration is 60"]}
DETAILED_EXCEPTION_BODY = {"details": {"duration": ["minimum value for duration is 60"]}}

RELATED_OBJECTS_EXCEPTION_BODY = {
    "errors": [
        {
            "instance": {
                "url": "<url>",
                "storage_name": "MINIO_DEV",
                "filename": "laterals.json",
                "bucket": "3di",
                "prefix": "None",
                "etag": "<etag>",
                "size": "1024",
                "expiry_date": "2021-08-01",
                "related_object": "<related_object>",
                "type": "bulklateral",
                "state": "error",
                "state_description": "Invalid file, see related event for further details",
                "meta": "None",
                "id": "123456",
            },
            "reason": "File processing error: Invalid file, see related event for further details",
            "resolution": "Fix the error, remove the event (see related_object) and try again",
        }
    ]
}


TIMESERIES24 = [
    [0.0, 5.867346938775e-06],
    [3600.0, 2.9336734693875e-06],
    [7200.0, 1.955782312925e-06],
    [10800.0, 1.955782312925e-06],
    [14400.0, 9.778911564625e-07],
    [18000.0, 9.778911564625e-07],
    [21600.0, 4.8894557823125e-06],
    [25200.0, 1.56462585034e-05],
    [28800.0, 1.46683673469375e-05],
    [32400.0, 1.173469387755e-05],
    [36000.0, 1.07568027210875e-05],
    [39600.0, 9.778911564625e-06],
    [43200.0, 8.8010204081625e-06],
    [46800.0, 7.8231292517e-06],
    [50400.0, 7.8231292517e-06],
    [54000.0, 6.845238095237501e-06],
    [57600.0, 6.845238095237501e-06],
    [61200.0, 7.8231292517e-06],
    [64800.0, 1.07568027210875e-05],
    [68400.0, 1.56462585034e-05],
    [72000.0, 1.3690476190475002e-05],
    [75600.0, 1.07568027210875e-05],
    [79200.0, 8.8010204081625e-06],
    [82800.0, 7.8231292517e-06],
    [86400.0, 5.867346938775e-06],
]


class SimpleApiException(Exception):
    """Simplified API exception class used for testing."""

    def __init__(self, body):
        self.body = body
