"""
test_ppm.py — Tests for the /get-ppm route.
These tests check the normal query path, aggregate path, and DB error handling.
"""
import pytest
import json
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from app.api.routes.ppm import get_ppm
from app.api.models.schemas import PPMRequest


# Test 1: Check get_ppm returns p_list and p_count when DB has records
def test_get_ppm_normal():
    # Fake DB returns one PPM record
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = [
        json.dumps({
            "p_list": [{"WorkOrder": "WO-001", "StatusName": "Pending"}],
            "p_count": 1
        })
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("app.api.routes.ppm.get_pool", return_value=mock_conn):
        req = PPMRequest(user_name="testuser")
        result = get_ppm(req)

    # Result should have p_list with 1 record and p_count = 1
    assert result["p_count"] == 1
    assert result["p_list"][0]["WorkOrder"] == "WO-001"


# Test 2: Check aggregate mode calls sp_ppm_aggregate stored procedure
def test_get_ppm_aggregate():
    # Fake DB returns grouped summary data
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = [
        json.dumps({
            "p_list": [{"FrequencyName": "Monthly", "result": 20}],
            "p_count": 1
        })
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("app.api.routes.ppm.get_pool", return_value=mock_conn):
        req = PPMRequest(
            user_name="testuser",
            is_aggregate=True,
            group_by_columns=["FrequencyName"],
            aggregate_function="COUNT"
        )
        result = get_ppm(req)

    # sp_ppm_aggregate should have been called (not sp_ppm_query)
    mock_cursor.callproc.assert_called_once()
    called_proc = mock_cursor.callproc.call_args[0][0]
    assert called_proc == "sp_ppm_aggregate"


# Test 3: Check DB failure raises HTTP 500 with error message
def test_get_ppm_db_error():
    # Fake DB raises an exception
    mock_conn = MagicMock()
    mock_conn.cursor.side_effect = Exception("DB connection failed")

    with patch("app.api.routes.ppm.get_pool", return_value=mock_conn):
        req = PPMRequest(user_name="testuser")
        with pytest.raises(HTTPException) as exc_info:
            get_ppm(req)

    # Should raise HTTP 500
    assert exc_info.value.status_code == 500
    assert "DB connection failed" in exc_info.value.detail
    