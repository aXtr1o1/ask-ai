"""
test_assets.py — Tests for the /get-assets route.
These tests check the normal query path, aggregate path, and DB error handling.
"""
import pytest
import json
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from app.api.routes.assets import get_assets, format_response
from app.api.models.schemas import AssetRequest


# Test 1: Check get_assets returns p_list and p_count when DB has records
def test_get_assets_normal():
    # Fake DB returns one asset record
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = [
        json.dumps({
            "p_list": [{"AssetTagNo": "A001", "StatusName": "Active"}],
            "p_count": 1
        })
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("app.api.routes.assets.get_pool", return_value=mock_conn):
        req = AssetRequest(user_name="testuser")
        result = get_assets(req)

    # Result should have p_list with 1 record and p_count = 1
    assert result["p_count"] == 1
    assert result["p_list"][0]["AssetTagNo"] == "A001"


# Test 2: Check aggregate mode calls sp_asset_aggregate stored procedure
def test_get_assets_aggregate():
    # Fake DB returns grouped summary data
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = [
        json.dumps({
            "p_list": [{"DivisionName": "Electrical", "result": 10}],
            "p_count": 1
        })
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("app.api.routes.assets.get_pool", return_value=mock_conn):
        req = AssetRequest(
            user_name="testuser",
            is_aggregate=True,
            group_by_columns=["DivisionName"],
            aggregate_function="COUNT"
        )
        result = get_assets(req)

    # sp_asset_aggregate should have been called (not sp_asset_query)
    mock_cursor.callproc.assert_called_once()
    called_proc = mock_cursor.callproc.call_args[0][0]
    assert called_proc == "sp_asset_aggregate"


# Test 3: Check DB failure raises HTTP 500 with error message
def test_get_assets_db_error():
    # Fake DB raises an exception
    mock_conn = MagicMock()
    mock_conn.cursor.side_effect = Exception("DB connection failed")

    with patch("app.api.routes.assets.get_pool", return_value=mock_conn):
        req = AssetRequest(user_name="testuser")
        with pytest.raises(HTTPException) as exc_info:
            get_assets(req)

    # Should raise HTTP 500
    assert exc_info.value.status_code == 500
    assert "DB connection failed" in exc_info.value.detail


def test_get_assets_keyword_fallback_after_empty_field_match():
    """asset_type=Forklift with no rows → retry with keyword=Forklift."""
    empty_payload = json.dumps({"p_list": [], "p_count": 0})
    hit_payload = json.dumps({
        "p_list": [
            {
                "AssetTagNo": "A100",
                "AssetTypeName": "Forklift Truck",
                "_matched_fields": ["EquipmentName", "AssetTypeName"],
            }
        ],
        "p_count": 1,
        "keyword_search": {"term": "Forklift", "match_type": "word_boundary"},
    })
    mock_cursor = MagicMock()
    mock_cursor.fetchone.side_effect = [
        [empty_payload],
        [hit_payload],
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("app.api.routes.assets.get_pool", return_value=mock_conn):
        req = AssetRequest(user_name="testuser", asset_type="Forklift")
        result = get_assets(req)

    assert result["p_count"] == 1
    assert result["search_fallback"]["from_field"] == "asset_type"
    assert result["search_fallback"]["keyword"] == "Forklift"
    assert mock_cursor.callproc.call_count == 2
    retry_args = mock_cursor.callproc.call_args_list[1][0][1]
    assert retry_args[10] is None  # p_asset_type cleared
    assert retry_args[31] == "Forklift"  # p_keyword
