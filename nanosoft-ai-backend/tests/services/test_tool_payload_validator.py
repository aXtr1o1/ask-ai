"""
Tests for tool payload normalization before DB calls.
"""
import pytest

from app.services.tool_payload_validator import (
    normalize_tool_args,
    validate_aggregate_request,
)


def test_low_count_by_buildingname_bdm_no_priority():
    query = "show all low count BuildingName BDM complaints"
    args = {
        "user_name": "poc",
        "priority": "P4 Low",
        "is_aggregate": False,
    }
    out = normalize_tool_args("BDM", query, args)
    assert out["is_aggregate"] is True
    assert out["group_by_columns"] == ["BuildingName"]
    assert "priority" not in out or out.get("priority") is None


def test_group_by_columns_forces_aggregate():
    args = {"user_name": "poc", "group_by_columns": ["building"]}
    out = normalize_tool_args("BDM", "complaints", args)
    assert out["is_aggregate"] is True
    assert out["group_by_columns"] == ["BuildingName"]


def test_p4_low_per_building_keeps_priority():
    query = "P4 Low BDM complaints per building"
    args = {"user_name": "poc"}
    out = normalize_tool_args("BDM", query, args)
    assert out.get("priority") == "P4 Low"
    assert out["is_aggregate"] is True
    assert "BuildingName" in out["group_by_columns"]


def test_aggregate_strips_keyword_bdm():
    query = "breakdown by BuildingName"
    args = {
        "user_name": "poc",
        "is_aggregate": True,
        "group_by_columns": ["BuildingName"],
        "keyword": "leak",
        "complaint_no": "99",
    }
    out = normalize_tool_args("BDM", query, args)
    assert "keyword" not in out
    assert "complaint_no" not in out


def test_coerce_string_is_aggregate():
    out = normalize_tool_args(
        "FA",
        "count per building",
        {"is_aggregate": "true", "group_by_columns": "BuildingName"},
    )
    assert out["is_aggregate"] is True
    assert out["group_by_columns"] == ["BuildingName"]


def test_validate_aggregate_request_raises():
    with pytest.raises(ValueError, match="group_by_columns"):
        validate_aggregate_request(True, None)

