# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
from unittest.mock import Mock, patch

import pytest
from threedi_api_client.openapi import (
    Action,
    ApiException,
    ConstantRain,
    CurrentStatus,
    Progress,
    Repository,
    Revision,
    Simulation,
    ThreediModel,
    TimeseriesRain,
)
from threedi_api_client.openapi.api.v3_api import V3Api

from threedi_models_and_simulations.api_calls.threedi_calls import ThreediCalls, get_api_client

from .conftest import (
    ACTION_DATA,
    BAD_SIM_DATA,
    CONSTANT_RAIN_DATA,
    CURRENT_STATUSES_LIST,
    MODEL_DATA_LIST,
    PROGRESS_DATA,
    REPO_DATA_LIST,
    REVISION_DATA_LIST,
    SIM_DATA_LIST,
    SINGLE_SIM_DATA,
    TEST_API_PARAMETERS,
    TIME_SERIES_RAIN_DATA,
)


@patch.object(V3Api, "repositories_list")
def test_fetch_repositories(mock_repositories_list):
    repos = [Repository(**data) for data in REPO_DATA_LIST]
    mock_repositories_list.return_value = Mock(results=repos, count=len(repos))
    api = get_api_client(*TEST_API_PARAMETERS)
    tc = ThreediCalls(api)
    results = tc.fetch_repositories()
    mock_repositories_list.assert_called()
    for res, raw_data in zip(results, REPO_DATA_LIST):
        for k, v in raw_data.items():
            assert hasattr(res, k)
            assert getattr(res, k) == v
    assert results == repos


@patch.object(V3Api, "simulations_list")
def test_fetch_simulations(mock_simulations_list):
    sims = [Simulation(**data) for data in SIM_DATA_LIST]
    mock_simulations_list.return_value = Mock(results=sims, count=len(sims))
    api = get_api_client(*TEST_API_PARAMETERS)
    tc = ThreediCalls(api)
    results = tc.fetch_simulations()
    mock_simulations_list.assert_called()
    for res, raw_data in zip(results, SIM_DATA_LIST):
        for k, v in raw_data.items():
            assert hasattr(res, k)
            assert getattr(res, k) == v
    assert results == sims


@patch.object(V3Api, "simulations_create", new=lambda self, data: data)
def test_new_simulation():
    api = get_api_client(*TEST_API_PARAMETERS)
    tc = ThreediCalls(api)
    sim = tc.create_simulation(**SINGLE_SIM_DATA)
    assert isinstance(sim, Simulation)


@patch.object(V3Api, "simulations_actions_create", new=lambda self, pk, data: Action(**data))
def test_make_action_on_simulation():
    api = get_api_client(*TEST_API_PARAMETERS)
    tc = ThreediCalls(api)
    pk = 1200
    action = tc.create_simulation_action(pk, **ACTION_DATA)
    assert isinstance(action, Action)
    assert action.name == "start"


@patch.object(V3Api, "simulations_progress_list")
def test_simulations_progress(mock_simulations_progress_list):
    mock_simulations_progress_list.return_value = Progress(**PROGRESS_DATA)
    api = get_api_client(*TEST_API_PARAMETERS)
    tc = ThreediCalls(api)
    pk = 1200
    progress = tc.fetch_simulation_progress(pk)
    assert isinstance(progress, Progress)
    assert progress.percentage == 25
    assert progress.time == 18000


@patch.object(V3Api, "simulations_list")
@patch.object(V3Api, "simulations_progress_list")
@patch.object(V3Api, "simulations_status_list")
def test_all_simulations_progress(mock_simulations_status_list, mock_simulations_progress_list, mock_simulations_list):
    statuses = [CurrentStatus(**data) for data in CURRENT_STATUSES_LIST]
    mock_simulations_status_list.side_effect = statuses + [ApiException(500)]
    sims = [Simulation(**data) for data in SIM_DATA_LIST]
    mock_simulations_list.return_value = Mock(results=sims, count=len(sims))
    sim1, sim2 = sims
    stat1, stat2 = statuses
    prog1 = Progress(**PROGRESS_DATA)
    mock_simulations_progress_list.side_effect = [prog1]
    api = get_api_client(*TEST_API_PARAMETERS)
    tc = ThreediCalls(api)
    progress_dict = tc.fetch_simulations_progresses([])
    assert all(s.id in progress_dict for s in sims)
    s1, cs1, p1 = progress_dict[sim1.id]
    s2, cs2, p2 = progress_dict[sim2.id]
    assert s1 == sim1
    assert cs1 == stat1
    assert p1.to_dict() == PROGRESS_DATA
    assert s2 == sim2
    assert cs2 == stat2
    assert p2.to_dict() == {"percentage": 100, "time": 72000}
    bad_results = [Simulation(**BAD_SIM_DATA)]
    mock_simulations_list.return_value = Mock(results=bad_results, count=len(bad_results))
    with pytest.raises(ApiException):
        tc.fetch_simulations_progresses([])


@patch.object(V3Api, "simulations_events_rain_constant_create", new=lambda self, pk, data: ConstantRain(**data))
def test_add_constant_precipitation():
    api = get_api_client(*TEST_API_PARAMETERS)
    tc = ThreediCalls(api)
    constant_rain = tc.create_simulation_constant_precipitation(1200, **CONSTANT_RAIN_DATA)
    assert isinstance(constant_rain, ConstantRain)
    for k, v in CONSTANT_RAIN_DATA.items():
        assert getattr(constant_rain, k) == v


@patch.object(V3Api, "simulations_events_rain_timeseries_create", new=lambda self, pk, data: TimeseriesRain(**data))
def test_add_custom_precipitation():
    api = get_api_client(*TEST_API_PARAMETERS)
    tc = ThreediCalls(api)
    custom_rain = tc.create_simulation_custom_precipitation(1200, **TIME_SERIES_RAIN_DATA)
    assert isinstance(custom_rain, TimeseriesRain)
    for k, v in TIME_SERIES_RAIN_DATA.items():
        assert getattr(custom_rain, k) == v


@patch.object(V3Api, "revisions_list")
def test_fetch_revisions(mock_revisions_list):
    revs = [Revision(**data) for data in REVISION_DATA_LIST]
    mock_revisions_list.return_value = Mock(results=revs, count=len(revs))
    api = get_api_client(*TEST_API_PARAMETERS)
    tc = ThreediCalls(api)
    results = tc.fetch_revisions()
    mock_revisions_list.assert_called()
    for res, raw_data in zip(results, REVISION_DATA_LIST):
        assert isinstance(res, Revision)
        for k, v in raw_data.items():
            assert hasattr(res, k)
            assert getattr(res, k) == v
    assert results == revs


@patch.object(V3Api, "revisions_threedimodels")
def test_fetch_revision_3di_models(mock_revisions_threedimodels):
    models = [ThreediModel(**data) for data in MODEL_DATA_LIST]
    mock_revisions_threedimodels.return_value = models
    api = get_api_client(*TEST_API_PARAMETERS)
    tc = ThreediCalls(api)
    rev_id = 2
    results = tc.fetch_revision_3di_models(rev_id)
    for res, raw_data in zip(results, MODEL_DATA_LIST):
        assert isinstance(res, ThreediModel)
        for k, v in raw_data.items():
            assert hasattr(res, k)
            assert getattr(res, k) == v
