"""
test_postgres_service.py — Tests for chat session persistence.
Database is mocked by conftest.py.
"""
import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.asyncio
async def test_save_session_success():
    """Test successful session save"""
    from app.services.postgres_service import save_session_to_postgres_service
    
    history = [
        {"query": "show me assets", "assistant": "Found 1 asset.", "is_audio": False}
    ]

    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("app.services.postgres_service.get_pool", return_value=mock_conn), \
         patch("app.services.postgres_service.generate_session_title", return_value="Asset Query Session"):

        await save_session_to_postgres_service(
            session_id="sess-001",
            user_name="testuser",
            history=history
        )

    mock_conn.commit.assert_called_once()


@pytest.mark.asyncio
async def test_save_session_empty_history():
    """Test that empty history skips database save"""
    from app.services.postgres_service import save_session_to_postgres_service
    
    mock_conn = MagicMock()

    with patch("app.services.postgres_service.get_pool", return_value=mock_conn):
        await save_session_to_postgres_service(
            session_id="sess-001",
            user_name="testuser",
            history=[]
        )

    mock_conn.cursor.assert_not_called()


@pytest.mark.asyncio
async def test_save_session_db_error():
    """Test graceful handling of database errors"""
    from app.services.postgres_service import save_session_to_postgres_service
    
    history = [
        {"query": "show me assets", "assistant": "Found 1 asset.", "is_audio": False}
    ]

    with patch("app.services.postgres_service.get_pool") as mock_pool, \
         patch("app.services.postgres_service.generate_session_title", return_value="Test"):

        mock_pool.side_effect = Exception("DB connection failed")

        # Should not raise — errors are logged internally
        await save_session_to_postgres_service(
            session_id="sess-001",
            user_name="testuser",
            history=history
        )