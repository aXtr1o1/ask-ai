"""
Tests for the route-level aggregate guard.

normalize_tool_args() / normalize_location_text() (the regex-based
value-correction chain this file used to test) no longer exist — see
app/services/tool_payload_validator.py's own module docstring: they existed
only to patch up payloads guessed by the old bind_tools flow, and Normal
ASK-AI's payload agent now builds is_aggregate / group_by_columns directly
from real metadata, so there is nothing left to correct after the fact.
validate_aggregate_request() is the one function still live in that module.
"""
import pytest

from app.services.tool_payload_validator import validate_aggregate_request


def test_validate_aggregate_request_raises_without_group_by():
    with pytest.raises(ValueError, match="group_by_columns"):
        validate_aggregate_request(True, None)


def test_validate_aggregate_request_raises_on_empty_group_by():
    with pytest.raises(ValueError, match="group_by_columns"):
        validate_aggregate_request(True, [])


def test_validate_aggregate_request_passes_with_group_by():
    # Should not raise
    validate_aggregate_request(True, ["BuildingName"])


def test_validate_aggregate_request_skips_check_when_not_aggregate():
    # is_aggregate=False means group_by_columns is irrelevant — should not raise
    validate_aggregate_request(False, None)