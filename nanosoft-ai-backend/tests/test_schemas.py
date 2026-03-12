"""
test_schemas.py — Tests for Pydantic request/response models.
These tests check that fields are validated correctly and defaults are applied.
"""
import pytest
from pydantic import ValidationError
from app.api.models.schemas import AssetRequest, PPMRequest, BDMRequest
from app.models.schemas import ChatRequest, SessionRequest, ClientInsertionRequest


# Test 1: Check AssetRequest accepts valid fields and sets correct defaults
def test_asset_request_defaults():
    req = AssetRequest(user_name="testuser")
    # offset should default to 0
    assert req.offset == 0
    # is_aggregate should default to False
    assert req.is_aggregate == False
    # optional fields should be None
    assert req.limit is None
    assert req.group_by_columns is None
    assert req.aggregate_function is None


# Test 2: Check offset cannot be negative (Pydantic validation error expected)
def test_asset_request_negative_offset():
    with pytest.raises(ValidationError):
        AssetRequest(user_name="testuser", offset=-1)


# Test 3: Check PPMRequest SLA fields accept integer values correctly
def test_ppm_request_sla_fields():
    req = PPMRequest(
        user_name="testuser",
        sla_min=30,
        sla_max=120
    )
    # SLA min and max should be stored as integers
    assert req.sla_min == 30
    assert req.sla_max == 120


# Test 4: Check BDMRequest complaint-specific fields are stored correctly
def test_bdm_request_complaint_fields():
    req = BDMRequest(
        user_name="testuser",
        complaint_no="CMP-001",
        complaint_type="Electrical",
        priority="High"
    )
    # All complaint fields should be stored correctly
    assert req.complaint_no == "CMP-001"
    assert req.complaint_type == "Electrical"
    assert req.priority == "High"


# Test 5: Check SessionRequest defaults sessionId to empty string when not provided
def test_session_request_defaults():
    req = SessionRequest(userName="testuser")
    # sessionId should default to empty string
    assert req.sessionId == ""
    # chatHistory should default to None
    assert req.chatHistory is None