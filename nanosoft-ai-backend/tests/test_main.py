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

    with patch("app.api.routes.app_endpoints.get_pool", return_value=MagicMock()):
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

    with patch("app.api.routes.app_endpoints.get_pool", return_value=MagicMock()), \
         patch("app.api.routes.app_endpoints.get_sessions_for_user", new_callable=AsyncMock, return_value=mock_sessions):

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

    with patch("app.api.routes.app_endpoints.get_pool", return_value=MagicMock()), \
         patch("app.services.chat_websocket_handler.langchain_service.process_query", new_callable=AsyncMock, return_value=mock_response):

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


# Test 4: Check /api/advance/ask-ai/audio
def test_advance_ask_ai_audio():
    from app.main import chatbot_app

    mock_transcription = {"transcription": "show assets"}
    
    async def mock_stream(*args, **kwargs):
        yield "data: {\"status\": \"complete\", \"result\": \"mocked\"}\n\n"

    with patch("app.api.advance.routes.router.get_audio_duration_seconds", return_value=5), \
         patch("app.api.advance.routes.router.get_profile_name_by_external_user_id", return_value="test-profile"), \
         patch("app.api.advance.routes.router.get_credits_remaining", return_value=10), \
         patch("app.api.advance.routes.router.consume_audio_seconds_if_available", return_value=True), \
         patch("app.api.advance.routes.router.update_daily_history", return_value=True), \
         patch("app.api.advance.routes.router.convert_audio_to_text", new_callable=AsyncMock, return_value=mock_transcription), \
         patch("app.api.advance.routes.router.stream_advance_pipeline", side_effect=mock_stream):

        client = TestClient(chatbot_app)
        
        # Prepare dummy audio file bytes
        audio_file = ("test.ogg", b"dummy ogg audio content bytes", "audio/ogg")
        
        response = client.post(
            "/api/advance/ask-ai/audio",
            data={
                "session_id": "sess-abc",
                "user_name": "testuser",
                "user_id": "123",
                "audio_seconds": "5"
            },
            files={"file": audio_file}
        )

    # Should succeed and return event-stream
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "status" in response.text

            
            
            
