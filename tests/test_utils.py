# 3Di Models & Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2022 by Lutra Consulting for 3Di Water Management
import pytest
from datetime import datetime
from threedi_api_qgis_client.utils import (
    mmh_to_ms,
    ms_to_mmh,
    mmtimestep_to_mmh,
    mmh_to_mmtimestep,
    extract_error_message,
    apply_24h_timeseries,
)
from .conftest import (
    RELATED_OBJECTS_EXCEPTION_BODY,
    SIM_EXCEPTION_BODY,
    DETAILED_EXCEPTION_BODY,
    TIMESERIES24,
    SimpleApiException,
)


def test_mmh_to_ms():
    mmh_value = 200
    ms_value = mmh_to_ms(mmh_value)
    ms_value_str = f"{ms_value:.10f}"
    assert ms_value_str == "0.0000555556"


def test_ms_to_mmh():
    ms_value = 0.0000555556
    mmh_value = ms_to_mmh(ms_value)
    mmh_value_str = f"{mmh_value:.0f}"
    assert mmh_value_str == "200"


def test_mmtimestep_to_mmh():
    timestep = 5
    units = "mins"
    mmtimestep_series = [0.3, 0.6, 0.9, 1.2, 1.5, 2.1, 2.7, 3.3, 3.3, 2.1, 1.2, 0.6, 0.0]
    expected_mmh_series = [3.6, 7.2, 10.8, 14.4, 18.0, 25.2, 32.4, 39.6, 39.6, 25.2, 14.4, 7.2, 0.0]
    mmh_series = [round(mmtimestep_to_mmh(v, timestep, units), 2) for v in mmtimestep_series]
    assert mmh_series == expected_mmh_series


def test_mmh_to_mmtimestep():
    timestep = 5
    units = "mins"
    mmh_series = [3.6, 7.2, 10.8, 14.4, 18.0, 25.2, 32.4, 39.6, 39.6, 25.2, 14.4, 7.2, 0.0]
    expected_mmtimestep_series = [0.3, 0.6, 0.9, 1.2, 1.5, 2.1, 2.7, 3.3, 3.3, 2.1, 1.2, 0.6, 0.0]
    mmtimestep_series = [round(mmh_to_mmtimestep(v, timestep, units), 2) for v in mmh_series]
    assert mmtimestep_series == expected_mmtimestep_series


def test_extract_error_message_simulation_err():
    sim_error = SimpleApiException(SIM_EXCEPTION_BODY)
    assert extract_error_message(sim_error) == "Error: {'duration': ['minimum value for duration is 60']}"


def test_extract_error_message_detailed_err():
    detailed_error = SimpleApiException(DETAILED_EXCEPTION_BODY)
    assert extract_error_message(detailed_error) == "Error: {'duration': ['minimum value for duration is 60']}"


def test_extract_error_message_related_err():
    rel_error = SimpleApiException(RELATED_OBJECTS_EXCEPTION_BODY)
    assert (
        extract_error_message(rel_error)
        == "Error: File processing error: Invalid file, see related event for further details (<related_object>)"
    )


def test_extract_error_message_decode_err():
    decode_error = SimpleApiException("invalid JSON body")
    assert extract_error_message(decode_error) == "Error: invalid JSON body"


def test_extract_error_message_unknown_err():
    unknown_error_body = SimpleApiException(["nobody expects the spanish inquisition"])
    assert extract_error_message(unknown_error_body) == "Error: ['nobody expects the spanish inquisition']"


def test_apply_24h_timeseries_trim():
    start_datetime = datetime(2021, 1, 10, 10, 10)
    end_datetime = datetime(2021, 1, 10, 15, 15)
    expected_ts = [
        (0.0, 1.07568027210875e-05),
        (3600.0, 9.778911564625e-06),
        (7200.0, 8.8010204081625e-06),
        (10800.0, 7.8231292517e-06),
        (14400.0, 7.8231292517e-06),
        (18000.0, 6.845238095237501e-06),
    ]
    trimmed_ts = apply_24h_timeseries(start_datetime, end_datetime, TIMESERIES24)
    assert trimmed_ts == expected_ts


def test_apply_24h_timeseries_extend_full_days():
    start_datetime = datetime(2021, 1, 10, 0, 0)
    end_datetime = datetime(2021, 1, 15, 0, 0)
    ts_values = [v for t, v in TIMESERIES24]
    expected_ts_values = ts_values + ts_values[1:] * 4
    extended_ts_values = [v for t, v in apply_24h_timeseries(start_datetime, end_datetime, TIMESERIES24)]
    assert extended_ts_values == expected_ts_values


def test_apply_24h_timeseries_extend_extra_hours():
    end_shift_hours = 2
    start_datetime = datetime(2021, 1, 10, 0, 0)
    end_datetime = datetime(2021, 1, 15, end_shift_hours, 0)
    ts_values = [v for t, v in TIMESERIES24]
    expected_ts_values = ts_values + ts_values[1:] * 4
    expected_ts_values += ts_values[1 : end_shift_hours + 1]  # Adding time steps for additional hours
    extended_ts_values = [v for t, v in apply_24h_timeseries(start_datetime, end_datetime, TIMESERIES24)]
    assert extended_ts_values == expected_ts_values


def test_apply_24h_timeseries_extend_almost_full_days():
    start_datetime = datetime(2021, 1, 10, 0, 0)
    end_datetime = datetime(2021, 1, 14, 23, 59)
    ts_values = [v for t, v in TIMESERIES24]
    expected_ts_values = ts_values + ts_values[1:] * 4
    expected_ts_values.pop()  # Removing last hour time step
    extended_ts_values = [v for t, v in apply_24h_timeseries(start_datetime, end_datetime, TIMESERIES24)]
    assert extended_ts_values == expected_ts_values


def test_apply_24h_timeseries_extend_uneven_hours():
    start_shift_hours = 2
    end_shift_hours = 1
    start_datetime = datetime(2021, 1, 10, start_shift_hours)
    end_datetime = datetime(2021, 1, 15, end_shift_hours)
    ts_values = [v for t, v in TIMESERIES24]
    expected_ts_values = ts_values + ts_values[1:] * 4
    del expected_ts_values[:start_shift_hours]  # Removing time steps according to the start time shift
    expected_ts_values += ts_values[1 : end_shift_hours + 1]  # Adding time steps for additional hours
    extended_ts_values = [v for t, v in apply_24h_timeseries(start_datetime, end_datetime, TIMESERIES24)]
    assert extended_ts_values == expected_ts_values
