"""
test_postgres_service.py — Tests for chat session persistence service.
These tests check save success, empty history skip, and DB error handling.
All DB and AI calls are mocked.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.postgres_service import save_session_to_postgres_service, generate_session_title


# Test 1: Check save_session saves correctly when history has records
@pytest.mark.anyio
async def test_save_session_success():
    # Fake history with one chat pair
    history = [
        {"query": "show me assets", "assistant": "Found 1 asset.", "is_audio": False}
    ]

    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("app.services.postgres_service.get_pool", return_value=mock_conn), \
         patch("app.services.postgres_service.generate_session_title", return_value="Asset Query Session"):

        # Should complete without raising any exception
        await save_session_to_postgres_service(
            session_id="sess-001",
            user_name="testuser",
            history=history
        )

    # conn.commit() should have been called to save the data
    mock_conn.commit.assert_called_once()


# Test 2: Check save_session skips saving when history is empty
@pytest.mark.anyio
async def test_save_session_empty_history():
    mock_conn = MagicMock()

    with patch("app.services.postgres_service.get_pool", return_value=mock_conn):
        # Empty history should return early without DB call
        await save_session_to_postgres_service(
            session_id="sess-001",
            user_name="testuser",
            history=[]
        )

    # DB should NOT be called when history is empty
    mock_conn.cursor.assert_not_called()


# Test 3: Check DB failure is handled without crashing the app
@pytest.mark.anyio
async def test_save_session_db_error():
    history = [
        {"query": "show me assets", "assistant": "Found 1 asset.", "is_audio": False}
    ]

    with patch("app.services.postgres_service.get_pool") as mock_pool, \
         patch("app.services.postgres_service.generate_session_title", return_value="Test"):

        # Simulate DB connection failure
        mock_pool.side_effect = Exception("DB connection failed")

        # Should NOT raise — errors are caught and logged internally
        await save_session_to_postgres_service(
            session_id="sess-001",
            user_name="testuser",
            history=history
        )
        
        