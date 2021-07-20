# 3Di API Client for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2021 by Lutra Consulting for 3Di Water Management
import pytest
from threedi_api_qgis_client.utils import (
    mmh_to_ms,
    ms_to_mmh,
    mmtimestep_to_mmh,
    mmh_to_mmtimestep,
    extract_error_message,
)
from .conftest import RELATED_OBJECTS_EXCEPTION_BODY, SIM_EXCEPTION_BODY, DETAILED_EXCEPTION_BODY, SimpleApiException


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


def test_extract_error_message():
    sim_error = SimpleApiException(SIM_EXCEPTION_BODY)
    detailed_error = SimpleApiException(DETAILED_EXCEPTION_BODY)
    rel_error = SimpleApiException(RELATED_OBJECTS_EXCEPTION_BODY)
    decode_error = SimpleApiException("invalid JSON body")
    unknown_error_body = SimpleApiException(["nobody expects the spanish inquisition"])
    assert extract_error_message(sim_error) == "Error: {'duration': ['minimum value for duration is 60']}"
    assert extract_error_message(detailed_error) == "Error: {'duration': ['minimum value for duration is 60']}"
    assert (
        extract_error_message(rel_error)
        == "Error: File processing error: Invalid file, see related event for further details (<related_object>)"
    )
    assert extract_error_message(decode_error) == "Error: invalid JSON body"
    assert extract_error_message(unknown_error_body) == "Error: ['nobody expects the spanish inquisition']"
