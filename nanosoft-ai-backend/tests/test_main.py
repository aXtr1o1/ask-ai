"""
test_main.py — Tests for main FastAPI app endpoints.
These tests check health check, session endpoint, and WebSocket chat.
All DB and AI calls are mocked.
"""
import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient


# Test 1: Check /api/health returns status ok
def test_health_check():
    from app.main import chatbot_app

    with patch("app.main.get_pool", return_value=MagicMock()):
        client = TestClient(chatbot_app)
        response = client.get("/api/health")

    # Health endpoint should return 200 with status ok
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# Test 2: Check /api/session returns sessions list for a valid user
def test_session_endpoint_fetch_sessions():
    from app.main import chatbot_app

    mock_sessions = [
        {"session_id": "sess-001", "title": "Asset Query", "created_at": "2024-01-01T00:00:00", "updated_at": "2024-01-01T00:00:00"}
    ]

    with patch("app.main.get_pool", return_value=MagicMock()), \
         patch("app.main.get_sessions_for_user", new_callable=AsyncMock, return_value=mock_sessions):

        client = TestClient(chatbot_app)
        response = client.post("/api/session", json={
            "userName": "testuser",
            "sessionId": ""
        })

    # Should return sessions list with type = "sessions"
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "sessions"
    assert len(data["sessions"]) == 1


# Test 3: Check WebSocket /api/chat handles text message correctly
def test_websocket_chat_text_message():
    from app.main import chatbot_app

    mock_response = ("Here are your assets.", "Found assets.", [])

    with patch("app.main.get_pool", return_value=MagicMock()), \
         patch("app.main.langchain_service.process_query", new_callable=AsyncMock, return_value=mock_response):

        client = TestClient(chatbot_app)

        with client.websocket_connect("/api/chat") as websocket:
            # Send a text message
            websocket.send_text(json.dumps({
                "userName": "testuser",
                "sessionId": "sess-001",
                "query": "show me assets",
                "isAudio": False,
                "isGraph": False
            }))

            # Receive the response
            response = websocket.receive_text()
            data = json.loads(response)

            # Should receive a response with session_id and response text
            assert "response" in data
            assert data["response"] == "Here are your assets."
            
            
            
            