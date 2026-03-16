"""
test_session_service.py — Tests for session fetch service.
These tests check fetching sessions, fetching chat history, and empty results.
All DB calls are mocked.
"""
import pytest
import json
from unittest.mock import MagicMock, patch
from app.services.session_service import get_sessions_for_user, get_chat_history_for_session
from datetime import datetime


# Test 1: Check get_sessions_for_user returns list of sessions for a user
@pytest.mark.anyio
async def test_get_sessions_for_user():
    # Fake DB returns 2 sessions
    now = datetime.now()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        ("sess-001", "Asset Query", now, now),
        ("sess-002", "PPM Check",   now, now),
    ]
    mock_cursor.description = [
        ("session_id",), ("title",), ("created_at",), ("updated_at",)
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("app.services.session_service.get_pool", return_value=mock_conn):
        result = await get_sessions_for_user("testuser")

    # Should return 2 sessions with correct fields
    assert len(result) == 2
    assert result[0]["session_id"] == "sess-001"
    assert result[0]["title"] == "Asset Query"


# Test 2: Check get_chat_history_for_session returns correct chat history
@pytest.mark.anyio
async def test_get_chat_history_for_session():
    # Fake DB returns chat history JSON
    history = [
        {"query": "show me assets", "assistant": "Found 1 asset.", "is_audio": False, "context": "summary"}
    ]
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (json.dumps(history),)
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("app.services.session_service.get_pool", return_value=mock_conn):
        result = await get_chat_history_for_session("testuser", "sess-001")

    # Should return history without the "context" field (stripped for frontend)
    assert len(result) == 1
    assert result[0]["query"] == "show me assets"
    assert result[0]["assistant"] == "Found 1 asset."
    assert "context" not in result[0]


# Test 3: Check empty result is returned when session is not found in DB
@pytest.mark.anyio
async def test_get_chat_history_session_not_found():
    # Fake DB returns no row for this session
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("app.services.session_service.get_pool", return_value=mock_conn):
        result = await get_chat_history_for_session("testuser", "nonexistent-session")

    # Should return empty list when session not found
    assert result == []