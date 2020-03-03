#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest
import datetime
from mock import Mock, patch
from openapi_client import Simulation
from threedi_api_qgis_client.api_calls.threedi_calls import ThreediCalls, get_api_client


@patch('openapi_client.RepositoriesApi.repositories_list')
def test_fetch_repositories(mock_repositories_list):
    mock_repositories_list.return_value = Mock(results=['result1', 'result2'])
    api = get_api_client('dummy_api', 'dummy_username', 'dummy_password', testing=True)
    tc = ThreediCalls(api)
    repos = tc.fetch_repositories()
    assert repos == ['result1', 'result2']
    #assert mock_repositories_list.assert_called()


@patch('openapi_client.SimulationsApi.simulations_create')
def test_new_simulation(mock_simulations_create):
    mock_simulations_create.side_effect = lambda x: x
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

