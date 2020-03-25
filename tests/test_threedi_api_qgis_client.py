# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2020 by Lutra Consulting for 3Di Water Management
import pytest
from unittest.mock import Mock, patch
from openapi_client import (ApiException, Repository, Simulation, Revision, Action, Progress, ConstantRain,
                            TimeseriesRain, ThreediModel, CurrentStatus)
from threedi_api_qgis_client.api_calls.threedi_calls import (get_api_client, ThreediCalls, RepositoriesApi,
                                                             SimulationsApi, RevisionsApi)
from .conftest import (TEST_API_PARAMETERS, REPO_DATA_LIST, SIM_DATA_LIST, SINGLE_SIM_DATA, BAD_SIM_DATA,
                       ACTION_DATA, PROGRESS_DATA, CONSTANT_RAIN_DATA, TIME_SERIES_RAIN_DATA, REVISION_DATA_LIST,
                       MODEL_DATA_LIST, CURRENT_STATUS_DATA)


@patch.object(RepositoriesApi, 'repositories_list')
def test_fetch_repositories(mock_repositories_list):
    repos = [Repository(**data) for data in REPO_DATA_LIST]
    mock_repositories_list.return_value = Mock(results=repos)
    api = get_api_client(*TEST_API_PARAMETERS)
    tc = ThreediCalls(api)
    results = tc.fetch_repositories()
    mock_repositories_list.assert_called()
    for res, raw_data in zip(results, REPO_DATA_LIST):
        for k, v in raw_data.items():
            assert hasattr(res, k)
            assert getattr(res, k) == v
    assert results == repos


@patch.object(SimulationsApi, 'simulations_list')
def test_fetch_simulations(mock_simulations_list):
    sims = [Simulation(**data) for data in SIM_DATA_LIST]
    mock_simulations_list.return_value = Mock(results=sims)
    api = get_api_client(*TEST_API_PARAMETERS)
    tc = ThreediCalls(api)
    results = tc.fetch_simulations()
    mock_simulations_list.assert_called()
    for res, raw_data in zip(results, SIM_DATA_LIST):
        for k, v in raw_data.items():
            assert hasattr(res, k)
            assert getattr(res, k) == v
    assert results == sims


@patch.object(SimulationsApi, 'simulations_create', new=lambda self, data: data)
def test_new_simulation():
    api = get_api_client(*TEST_API_PARAMETERS)
    tc = ThreediCalls(api)
    sim = tc.new_simulation(**SINGLE_SIM_DATA)
    assert isinstance(sim, Simulation)


@patch.object(SimulationsApi, 'simulations_actions_create', new=lambda self, pk, data: Action(**data))
def test_make_action_on_simulation():
    api = get_api_client(*TEST_API_PARAMETERS)
    tc = ThreediCalls(api)
    pk = 1200
    action = tc.make_action_on_simulation(pk, **ACTION_DATA)
    assert isinstance(action, Action)
    assert action.name == 'start'


@patch.object(SimulationsApi, 'simulations_progress_list')
def test_simulations_progress(mock_simulations_progress_list):
    mock_simulations_progress_list.return_value = Progress(**PROGRESS_DATA)
    api = get_api_client(*TEST_API_PARAMETERS)
    tc = ThreediCalls(api)
    pk = 1200
    progress = tc.simulations_progress(pk)
    assert isinstance(progress, Progress)
    assert progress.percentage == 25
    assert progress.time == 18000


@patch.object(SimulationsApi, 'simulations_list')
@patch.object(SimulationsApi, 'simulations_progress_list')
@patch.object(SimulationsApi, 'simulations_status_list')
def test_all_simulations_progress(mock_simulations_status_list, mock_simulations_progress_list, mock_simulations_list):
    mock_simulations_status_list.return_value = CurrentStatus(**CURRENT_STATUS_DATA)
    sims = [Simulation(**data) for data in SIM_DATA_LIST]
    mock_simulations_list.return_value = Mock(results=sims)
    sim1, sim2 = sims
    prog1 = Progress(**PROGRESS_DATA)
    mock_simulations_progress_list.side_effect = [prog1,  ApiException(404), ApiException(500)]
    api = get_api_client(*TEST_API_PARAMETERS)
    tc = ThreediCalls(api)
    progress_dict = tc.all_simulations_progress()
    assert all(s.id in progress_dict for s in sims)
    s1, p1 = progress_dict[sim1.id]
    s2, p2 = progress_dict[sim2.id]
    assert s1 == sim1
    assert p1.to_dict() == PROGRESS_DATA
    assert s2 == sim2
    assert p2.to_dict() == {'percentage': 100, 'time': 72000}
    mock_simulations_list.return_value = Mock(results=[Simulation(**BAD_SIM_DATA)])
    with pytest.raises(ApiException):
        tc.all_simulations_progress()


@patch.object(SimulationsApi, 'simulations_events_rain_constant_create',
              new=lambda self, pk, data: ConstantRain(**data))
def test_add_constant_precipitation():
    api = get_api_client(*TEST_API_PARAMETERS)
    tc = ThreediCalls(api)
    constant_rain = tc.add_constant_precipitation(1200, **CONSTANT_RAIN_DATA)
    assert isinstance(constant_rain, ConstantRain)
    for k, v in CONSTANT_RAIN_DATA.items():
        assert getattr(constant_rain, k) == v


@patch.object(SimulationsApi, 'simulations_events_rain_timeseries_create',
              new=lambda self, pk, data: TimeseriesRain(**data))
def test_add_custom_precipitation():
    api = get_api_client(*TEST_API_PARAMETERS)
    tc = ThreediCalls(api)
    custom_rain = tc.add_custom_precipitation(1200, **TIME_SERIES_RAIN_DATA)
    assert isinstance(custom_rain, TimeseriesRain)
    for k, v in TIME_SERIES_RAIN_DATA.items():
        assert getattr(custom_rain, k) == v


@patch.object(RevisionsApi, 'revisions_list')
def test_fetch_revisions(mock_revisions_list):
    revs = [Revision(**data) for data in REVISION_DATA_LIST]
    mock_revisions_list.return_value = Mock(results=revs)
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


@patch.object(RevisionsApi, 'revisions_threedimodels')
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
