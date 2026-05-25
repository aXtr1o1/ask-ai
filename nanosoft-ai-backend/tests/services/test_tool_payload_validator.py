"""
Tests for tool payload normalization before DB calls.
"""
import pytest

from app.services.tool_payload_validator import (
    normalize_location_text,
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


def test_electrical_services_routes_to_service_type_not_division():
    query = "how many ELECTRICAL SERVICES BDM complaints are registered"
    args = {
        "user_name": "poc",
        "division": "Electrical System",
    }
    out = normalize_tool_args("BDM", query, args)
    assert out.get("service_type") == "Electrical Services"
    assert "division" not in out


def test_housekeeping_services_not_division():
    query = "how many Housekeeping Services BDM complaints are registered"
    out = normalize_tool_args(
        "BDM",
        query,
        {"user_name": "poc", "division": "Housekeeping"},
    )
    assert out.get("service_type") == "Housekeeping Services"
    assert "division" not in out


def test_compare_two_services_aggregate_by_service_type():
    query = "compare Electrical Services and Housekeeping Services BDM complaints"
    out = normalize_tool_args(
        "BDM",
        query,
        {
            "user_name": "poc",
            "division": "Housekeeping",
            "service_type": "Electrical Services",
        },
    )
    assert out.get("is_aggregate") is True
    assert out.get("group_by_columns") == ["ServiceTypeName"]
    assert "division" not in out
    assert "service_type" not in out


def test_electrical_system_routes_to_division():
    query = "how many Electrical System BDM complaints"
    args = {"user_name": "poc", "service_type": "Electrical Services"}
    out = normalize_tool_args("BDM", query, args)
    assert out.get("division") == "Electrical System"
    assert "service_type" not in out


def test_locality_en_dash_normalized_to_ascii_hyphen():
    assert normalize_location_text("Terminal \u2013 A2") == "Terminal - A2"
    assert normalize_location_text("Terminal–A2") == "Terminal - A2"
    assert normalize_location_text("Terminal - A2") == "Terminal - A2"


def test_fa_closed_maps_to_stage_not_category():
    query = "how many Closed BDM and FA complaints are registered"
    out = normalize_tool_args(
        "FA",
        query,
        {"user_name": "poc", "category": "Closed"},
    )
    assert out.get("stage") == "Closed"
    assert "category" not in out


def test_how_many_floors_in_assets_uses_floorname_aggregate():
    query = "how many floors in the assets"
    out = normalize_tool_args(
        "ASSETS",
        query,
        {
            "user_name": "poc",
            "building": "floors in the",
            "is_aggregate": False,
        },
    )
    assert out.get("is_aggregate") is True
    assert out.get("group_by_columns") == ["FloorName"]
    assert out.get("aggregate_function") == "COUNT"
    assert "building" not in out


@pytest.mark.parametrize(
    "tool,query,wrong,expected_col",
    [
        ("BDM", "how many floors in BDM complaints", {"building": "floors in the"}, "FloorName"),
        ("FA", "how many buildings in FA complaints", {"building": "buildings in the"}, "BuildingName"),
        ("PPM", "how many frequencies in PPM work orders", {"frequency": "frequencies in"}, "FrequencyName"),
        ("BDM", "how many statuses in BDM complaints", {"status": "statuses in"}, "WoStatus"),
        ("FA", "how many categories in FA audits", {"category": "categories in"}, "RMCategoryName"),
        ("SB", "how many service types in SB work orders", {"service_type": "service types in"}, "ServiceTypeName"),
    ],
)
def test_dimension_count_aggregate_all_tools(tool, query, wrong, expected_col):
    args = {"user_name": "poc", "is_aggregate": False, **wrong}
    out = normalize_tool_args(tool, query, args)
    assert out.get("is_aggregate") is True
    assert out.get("group_by_columns") == [expected_col]
    for k in wrong:
        assert k not in out


def test_named_building_count_not_dimension_aggregate():
    """'how many Building 1 BDM' is a place filter, not group-by buildings."""
    query = "how many Building 1 - Residential High Rise BDM"
    out = normalize_tool_args(
        "BDM",
        query,
        {"user_name": "poc", "is_aggregate": False},
    )
    assert out.get("is_aggregate") is False
    assert not out.get("group_by_columns")
    assert out.get("building") == "Building 1 - Residential High Rise"


def test_corridor_bdm_clears_keyword_when_building_set():
    query = "how many Corridor BDM and FA complaints are registered"
    out = normalize_tool_args(
        "BDM",
        query,
        {
            "user_name": "poc",
            "building": "Corridor",
            "keyword": "Corridor",
            "is_aggregate": False,
        },
    )
    assert out.get("building") == "Corridor"
    assert "keyword" not in out


def test_power_plant_building_strips_descriptor_building():
    """POWER PLANT Building → filter POWER PLANT (Building is grammar, not DB token)."""
    query = "how many POWER PLANT Building BDM and FA complaints are registered"
    out = normalize_tool_args(
        "BDM",
        query,
        {"user_name": "poc", "keyword": "POWER PLANT Building", "is_aggregate": False},
    )
    assert out.get("building") == "POWER PLANT"
    assert "keyword" not in out
    assert out.get("is_aggregate") is False


def test_apron_building_strips_descriptor_building():
    query = "how many APRON Building BDM and FA complaints are registered"
    out = normalize_tool_args(
        "FA",
        query,
        {"user_name": "poc", "building": "APRON Building", "is_aggregate": False},
    )
    assert out.get("building") == "APRON"
    assert "keyword" not in out


def test_warehouse_building_lowercase_suffix():
    query = "how many Warehouse building BDM and FA complaints are registered"
    out = normalize_tool_args("BDM", query, {"user_name": "poc", "is_aggregate": False})
    assert out.get("building") == "Warehouse building"


def test_staff_canteen_bdm_routes_to_building_not_division():
    query = "how many Staff Canteen BDM"
    out = normalize_tool_args(
        "BDM",
        query,
        {"user_name": "poc", "division": "Staff Canteen", "is_aggregate": False},
    )
    assert out.get("building") == "Staff Canteen"
    assert "division" not in out
    assert out.get("is_aggregate") is False
    assert not out.get("group_by_columns")


def test_staff_canteen_bdm_fa_registered_no_group_by():
    query = "how many Staff Canteen BDM and FA complaints are registered"
    payload = {
        "user_name": "poc",
        "building": "Staff Canteen",
        "is_aggregate": True,
        "group_by_columns": ["BuildingName"],
        "aggregate_function": "COUNT",
    }
    bdm = normalize_tool_args("BDM", query, dict(payload))
    fa = normalize_tool_args("FA", query, dict(payload))
    for out in (bdm, fa):
        assert out.get("building") == "Staff Canteen"
        assert out.get("is_aggregate") is False
        assert not out.get("group_by_columns")


def test_bdm_corrective_maintenance_in_the_system_clears_bogus_division():
    query = (
        "how many Corrective Maintenance BDM complaint entries exist in the system"
    )
    out = normalize_tool_args(
        "BDM",
        query,
        {
            "user_name": "poc",
            "user_id": "1",
            "complaint_type": "Corrective Maintenance",
            "division": "Corrective Maintenance Bdm Complaint Entries Exist In The System",
            "is_aggregate": False,
        },
    )
    assert out.get("complaint_type") == "Corrective Maintenance"
    assert "division" not in out
    assert out.get("is_aggregate") is False


def test_bdm_service_request_and_ana_approval_flow_filters():
    query = "how many Service Request BDM complaints are under ANA Approval Flow"
    out = normalize_tool_args(
        "BDM",
        query,
        {
            "user_name": "poc",
            "complaint_type": "Service Request",
            "complaint_header": "ANA Approval Flow",
            "stage": "ANA Approval Flow",
            "keyword": "Service Request ANA Approval Flow",
            "complaint_mode": "By Call",
        },
    )
    assert out.get("complaint_type") == "Service Request"
    assert out.get("complaint_header") == "ANA Approval Flow"
    assert "stage" not in out
    assert "keyword" not in out
    assert "complaint_mode" not in out


def test_aggregate_without_group_by_falls_back_to_normal_query():
    """LLM often sends is_aggregate=true + COUNT without group_by → API 400 without this fix."""
    query = "how many residential building BDM and FA complaints are registered"
    out = normalize_tool_args(
        "BDM",
        query,
        {
            "user_name": "poc",
            "building": "Building 1 - Residential High Rise",
            "is_aggregate": True,
            "aggregate_function": "COUNT",
        },
    )
    assert out.get("is_aggregate") is False
    assert "aggregate_function" not in out or out.get("aggregate_function") is None
    assert out.get("building") == "Building 1 - Residential High Rise"


def test_bdm_closed_still_uses_status():
    query = "how many Closed BDM and FA complaints are registered"
    out = normalize_tool_args(
        "BDM",
        query,
        {"user_name": "poc", "status": "Closed"},
    )
    assert out.get("status") == "Closed"


def test_fa_building_name_category_not_audit_category():
    query = "How many BuildingName Category present in FA complaints"
    out = normalize_tool_args(
        "FA",
        query,
        {
            "user_name": "poc",
            "category": "Category",
            "group_by_columns": ["RMCategoryName"],
        },
    )
    assert out.get("is_aggregate") is True
    assert "BuildingName" in out.get("group_by_columns", [])
    assert "RMCategoryName" not in out.get("group_by_columns", [])
    assert "category" not in out


def test_fa_audit_category_breakdown_unchanged():
    query = "how many FA complaints per audit category"
    out = normalize_tool_args("FA", query, {"user_name": "poc"})
    assert out.get("is_aggregate") is True
    assert "RMCategoryName" in out.get("group_by_columns", [])


def test_bdm_locality_en_dash_in_payload():
    query = "How many BDM complaints registered on Terminal – A2"
    out = normalize_tool_args(
        "BDM",
        query,
        {"user_name": "poc", "locality": "Terminal \u2013 A2"},
    )
    assert out.get("locality") == "Terminal - A2"


