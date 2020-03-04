#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest
import datetime
from unittest.mock import Mock, patch
from openapi_client import Simulation
from threedi_api_qgis_client.api_calls.threedi_calls import (get_api_client, ThreediCalls, RepositoriesApi,
                                                             SimulationsApi)


@patch.object(RepositoriesApi, 'repositories_list')
def test_fetch_repositories(mock_repositories_list):
    mock_repositories_list.return_value = Mock(results=['result1', 'result2'])
    api = get_api_client('dummy_api', 'dummy_username', 'dummy_password', testing=True)
    tc = ThreediCalls(api)
    repos = tc.fetch_repositories()
    mock_repositories_list.assert_called()
    assert repos == ['result1', 'result2']


@patch.object(SimulationsApi, 'simulations_create', new=lambda self, data: data)
def test_new_simulation():
    api = get_api_client('dummy_api', 'dummy_username', 'dummy_password', testing=True)
    tc = ThreediCalls(api)
    data = {
        "name": "qgis client test run",
        "threedimodel": "14",
        "organisation": "cb0347bf57f7450984c4b1d27271c90f",
        "start_datetime":  datetime.datetime.utcnow(),
        "duration": 72000
    }
    sim = tc.new_simulation(**data)
    assert isinstance(sim, Simulation)
