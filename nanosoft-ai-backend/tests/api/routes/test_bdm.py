"""
test_bdm.py — Tests for the /get-bdm route.
These tests check the normal query path, aggregate path, and DB error handling.
"""
import pytest
import json
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from app.api.routes.bdm import get_bdm
from app.api.models.schemas import BDMRequest


# Test 1: Check get_bdm returns p_list and p_count when DB has records
def test_get_bdm_normal():
    # Fake DB returns one complaint record
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = [
        json.dumps({
            "p_list": [{"ComplaintNo": "CMP-001", "StatusName": "Open"}],
            "p_count": 1
        })
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("app.api.routes.bdm.get_pool", return_value=mock_conn):
        req = BDMRequest(user_name="testuser")
        result = get_bdm(req)

    # Result should have p_list with 1 record and p_count = 1
    assert result["p_count"] == 1
    assert result["p_list"][0]["ComplaintNo"] == "CMP-001"


# Test 2: Check aggregate mode calls sp_bdm_aggregate stored procedure
def test_get_bdm_aggregate():
    # Fake DB returns grouped summary data
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = [
        json.dumps({
            "p_list": [{"PriorityName": "High", "result": 5}],
            "p_count": 1
        })
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("app.api.routes.bdm.get_pool", return_value=mock_conn):
        req = BDMRequest(
            user_name="testuser",
            is_aggregate=True,
            group_by_columns=["PriorityName"],
            aggregate_function="COUNT"
        )
        result = get_bdm(req)

    # sp_bdm_aggregate should have been called (not sp_bdm_query)
    mock_cursor.callproc.assert_called_once()
    called_proc = mock_cursor.callproc.call_args[0][0]
    assert called_proc == "sp_bdm_aggregate"


def test_get_bdm_local_aggregate_for_complaint_header_with_type_filter():
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = [
        json.dumps({
            "p_list": [
                {"ComplaintTypeName": "Service Request", "ComplaintHeaderName": "ANA Approval Flow"},
                {"ComplaintTypeName": "Service Request", "ComplaintHeaderName": "ANA Approval Flow"},
                {"ComplaintTypeName": "Service Request", "ComplaintHeaderName": "Without Approval Flow"},
            ],
            "p_count": 3,
        })
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("app.api.routes.bdm.get_pool", return_value=mock_conn):
        req = BDMRequest(
            user_name="testuser",
            complaint_type="Service Request",
            is_aggregate=True,
            group_by_columns=["ComplaintHeaderName"],
            aggregate_function="COUNT",
        )
        result = get_bdm(req)

    called_proc = mock_cursor.callproc.call_args[0][0]
    assert called_proc == "sp_bdm_query"
    assert result["local_aggregate"] is True
    assert result["p_count"] == 2
    assert result["p_list"][0] == {"ComplaintHeaderName": "ANA Approval Flow", "result": 2}


# Test 3: Aggregate without group_by returns 400
def test_get_bdm_aggregate_missing_group_by():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        get_bdm(BDMRequest(user_name="testuser", is_aggregate=True, group_by_columns=None))
    assert exc.value.status_code == 400


# Test 4: Check DB failure raises HTTP 500 with error message
def test_get_bdm_db_error():
    # Fake DB raises an exception
    mock_conn = MagicMock()
    mock_conn.cursor.side_effect = Exception("DB connection failed")

    with patch("app.api.routes.bdm.get_pool", return_value=mock_conn):
        req = BDMRequest(user_name="testuser")
        with pytest.raises(HTTPException) as exc_info:
            get_bdm(req)

    # Should raise HTTP 500
    assert exc_info.value.status_code == 500
    assert "DB connection failed" in exc_info.value.detail
    
    
