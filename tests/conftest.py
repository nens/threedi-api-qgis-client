# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import datetime


TEST_API_PARAMETERS = ('TEST_USERNAME', 'TEST_PASSWORD', 'TEST_API')
REPO_DATA_LIST = [
        {
            'id': 1,
            'organisation': 'qwertyhash',
            'revision': ['api-qgis-demo1 - 1056fd7b1d95e184aa807162f1a5e2a7a505608e'],
            'slug': 'api-qgis-demo1',
            'url': 'https://testapi/repositories/1/'
        },
        {
            'id': 2,
            'organisation': 'qwertyhash',
            'revision': ['api-qgis-demo2 - 1156fd7b1d95e184aa807162f1a5e2a7a505608e'],
            'slug': 'api-qgis-demo2',
            'url': 'https://testapi/repositories/2/'
        }
    ]
SIM_DATA_LIST = [
        {
            'created': '2 days ago',
            'duration': 72000,
            'duration_humanized': '20 hours, 0 minutes, 0 seconds',
            'end_datetime': datetime.datetime(2020, 3, 3, 6, 30, 12),
            'id': 1201,
            'name': 'qgis client test run 1',
            'organisation': 'qwertyhash',
            'organisation_name': 'Lutra Consulting',
            'start_datetime': datetime.datetime(2020, 3, 2, 10, 30, 12),
            'tags': None,
            'threedimodel': 'https://testapi/threedimodels/14/',
            'threedimodel_id': '14',
            'url': 'https://testapi/simulations/1200/',
            'user': 'lukasz.debek',
            'uuid': '55e63655-6102-4653-b0fe-901fb5686420'
        },
        {
            'created': 'a day ago',
            'duration': 72000,
            'duration_humanized': '20 hours, 0 minutes, 0 seconds',
            'end_datetime': datetime.datetime(2020, 3, 3, 11, 19, 3),
            'id': 1202,
            'name': 'qgis client test run 2',
            'organisation': 'qwertyhash',
            'organisation_name': 'Lutra Consulting',
            'start_datetime': datetime.datetime(2020, 3, 2, 15, 19, 3),
            'tags': None,
            'threedimodel': 'https://testapi/threedimodels/14/',
            'threedimodel_id': '14',
            'url': 'https://testapi/simulations/1203/',
            'user': 'lukasz.debek',
            'uuid': '846a5952-c174-4d04-a9e5-44788a841eb7'
        }
    ]

SINGLE_SIM_DATA = {
    "id": 1000,
    "name": "Bad Simulation",
    "threedimodel": "14",
    "organisation": "qwertyhash",
    "start_datetime": datetime.datetime.utcnow(),
    "duration": 72000
}

BAD_SIM_DATA = {
    "name": "qgis client test run",
    "threedimodel": "14",
    "organisation": "qwertyhash",
    "start_datetime": datetime.datetime.utcnow(),
    "duration": 72000
}

ACTION_DATA = {'duration': None, 'name': 'start', 'rate_limit': None, 'timeout': None}

PROGRESS_DATA = {'percentage': 25, 'time': 18000}

CONSTANT_RAIN_DATA = {
    'duration': 5000,
    'offset': 60,
    'units': 'm/s',
    'value': 0.0006
}

RAIN_TIME_SERIES = [
    [0, 0.0005],
    [300, 0.0008],
    [1200, 0.0001]
]

TIME_SERIES_RAIN_DATA = {
    "offset": 0,
    "interpolate": False,
    "values": RAIN_TIME_SERIES,
    "units": "m/s"
}

REVISION_DATA_LIST = [
    {
        'hash': 'qwertyhash1',
        'id': 1,
        'is_pinned': False,
        'number': 0,
        'repository': 'https://testapi/repositories/1/',
        'url': 'https://testapi/revisions/1/'
    },
    {
        'hash': 'qwertyhash2',
        'id': 2,
        'is_pinned': False,
        'number': 0,
        'repository': 'https://testapi/repositories/1/',
        'url': 'https://testapi/revisions/2/'
    }
]

MODEL_DATA_LIST = [
    {
        'breach_count': '16',
        'description': '',
        'disabled': False,
        'epsg': 28892,
        'extent_one_d': "{'type': 'LineString', 'coordinates': [[4.65566310525691, "
                     '52.590857471993935], [4.808619107856248, '
                     '52.69717725606727]]}',
        'extent_two_d': "{'type': 'LineString', 'coordinates': [[4.668275740999323, "
                     '52.619558911160205], [4.738494268493689, '
                     '52.66453975864303]]}',
        'extent_zero_d': None,
        'id': 14,
        'inp_success': True,
        'inpy_version': '3.0.26.4-1.4.19-1',
        'lines_count': 18620,
        'model_ini': 'v2_bergermeer_simple_infil_no_grndwtr.ini',
        'name': 'romantic_elion',
        'nodes_count': 9068,
        'repository_slug': 'api-qgis-demo',
        'revision': 'https://testapi/revisions/2/',
        'revision_hash': 'qwertyhash2',
        'slug': 'api-qgis-demo-v2_bergermeer_simple_infil_no_grndwtr-0-6356fd7b1d95e184aa807162f1a5e2a7a505608e',
        'storage_space': 296327439,
        'storage_space_humanized': '296.3 MB',
        'url': 'https://testapi/threedimodels/14/'
    },
    {
        'breach_count': '16',
        'description': '',
        'disabled': False,
        'epsg': 28892,
        'extent_one_d': "{'type': 'LineString', 'coordinates': [[4.65566310525691, "
                     '52.590857471993935], [4.808619107856248, '
                     '52.69717725606727]]}',
        'extent_two_d': "{'type': 'LineString', 'coordinates': [[4.668275740999323, "
                     '52.619558911160205], [4.738494268493689, '
                     '52.66453975864303]]}',
        'extent_zero_d': None,
        'id': 15,
        'inp_success': True,
        'inpy_version': '3.0.26.4-1.4.19-1',
        'lines_count': 18620,
        'model_ini': 'v2_bergermeer_simple_infil_no_grndwtr.ini',
        'name': 'romantic_elion',
        'nodes_count': 9068,
        'repository_slug': 'api-qgis-demo',
        'revision': 'https://testapi/revisions/2/',
        'revision_hash': 'qwertyhash2',
        'slug': 'api-qgis-demo-v2_bergermeer_simple_infil_no_grndwtr-0-6356fd7b1d95e184aa807162f1a5e2a7a505608e',
        'storage_space': 296327439,
        'storage_space_humanized': '296.3 MB',
        'url': 'https://testapi/threedimodels/15/'
    }
]

CURRENT_STATUSES_LIST = [
    {
        'created': datetime.datetime.utcnow(),
        'id': 1201,
        'name': 'initialized',
        'paused': None,
        'time': 18000.0
    },
    {
        'created': datetime.datetime.utcnow(),
        'id': 1202,
        'name': 'finished',
        'paused': None,
        'time': 72000.0
    },
]
