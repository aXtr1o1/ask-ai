"""
test_facility_tools.py — Tests for ASSETS, PPM, BDM LangChain tools.
These tests check payload building, date defaulting, and route calling.
"""
import pytest
import json
from unittest.mock import MagicMock, patch
from datetime import date, timedelta
from app.tools.facility_tools import ASSETS, PPM, BDM #, getTime


# Test 1: Check ASSETS tool returns error string when user_name is missing
def test_assets_missing_user_name():
    # Calling ASSETS without user_name should return an error string, not crash
    result = ASSETS.invoke({"user_name": None})
    assert "Error" in result
    assert "user_name is required" in result


# Test 2: Check ASSETS tool builds correct payload and calls get_assets successfully
def test_assets_normal_call():
    # Fake get_assets returns empty result
    with patch("app.tools.assets_tool.get_assets") as mock_get_assets:
        mock_get_assets.return_value = {"p_list": [], "p_count": 0}

        result = ASSETS.invoke({
            "user_name": "testuser",
            "status": "Active",
            "building": "Block A"
        })

        # get_assets should be called once
        mock_get_assets.assert_called_once()

        # Result should be a valid JSON string
        parsed = json.loads(result)
        assert "p_count" in parsed


# Test 3: Check aggregate mode passes is_aggregate=True correctly to get_assets
def test_assets_aggregate_mode():
    # Fake get_assets returns grouped summary
    with patch("app.tools.assets_tool.get_assets") as mock_get_assets:
        mock_get_assets.return_value = {
            "p_list": [{"DivisionName": "Electrical", "result": 10}],
            "p_count": 1
        }

        ASSETS.invoke({
            "user_name": "testuser",
            "is_aggregate": True,
            "group_by_columns": ["DivisionName"],
            "aggregate_function": "COUNT"
        })

        # Check the AssetRequest passed to get_assets has is_aggregate=True
        call_args = mock_get_assets.call_args[0][0]
        assert call_args.is_aggregate == True
        assert call_args.group_by_columns == ["DivisionName"]


# Test 4: Check getTime() auto-fills last 7 days when both dates are None
# def test_gettime_auto_fills_dates():
#     # When no dates given, should default to last 7 days
#     date_from, date_to = getTime(None, None)

#     today = date.today().isoformat()
#     expected_from = (date.today() - timedelta(days=6)).isoformat()

#     # date_from should be 6 days ago and date_to should be today
#     assert date_from == expected_from
#     assert date_to == today