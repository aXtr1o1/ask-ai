"""
test_langchain_service.py — Tests for LangChain AI service process_query().
These tests check tool call path, no tool path, and error handling.
All AI model calls are mocked so no real Gemini API is called.
"""
import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage


# Test 1: Check process_query returns response when model makes a tool call
@pytest.mark.asyncio
async def test_process_query_with_tool_call():
    # Mock the entire LangChainService to avoid real Gemini init
    with patch("app.services.langchain_service.ChatGoogleGenerativeAI") as mock_llm:

        # First call — model decides to use ASSETS tool
        first_ai_msg = MagicMock()
        first_ai_msg.tool_calls = [{
            "name": "ASSETS",
            "id": "tool-call-1",
            "args": {"user_name": "testuser", "status": "Active"}
        }]
        first_ai_msg.usage_metadata = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}

        # Intent call — model says "list"
        intent_msg = MagicMock()
        intent_msg.content = "list"
        intent_msg.usage_metadata = {"input_tokens": 5, "output_tokens": 1, "total_tokens": 6}

        # Final answer call — model returns formatted response
        final_msg = MagicMock()
        final_msg.content = "Found 1 asset. | AssetTagNo | StatusName |\n|---|---|\n| A001 | Active |"
        final_msg.usage_metadata = {"input_tokens": 20, "output_tokens": 30, "total_tokens": 50}

        mock_model_instance = MagicMock()
        mock_model_instance.invoke.side_effect = [first_ai_msg, intent_msg, final_msg]
        mock_model_instance.bind_tools.return_value = mock_model_instance
        mock_llm.return_value = mock_model_instance

        # Mock ASSETS tool to return fake data
        with patch("app.services.langchain_service.ASSETS") as mock_assets_tool:
            mock_assets_tool.invoke.return_value = json.dumps({
                "p_list": [{"AssetTagNo": "A001", "StatusName": "Active"}],
                "p_count": 1
            })

            from app.services.langchain_service import LangChainService
            service = LangChainService()

            messages = [HumanMessage(content="show me assets")]
            result, context_summary, _ = await service.process_query(
                messages, user_name="testuser", session_id="sess-001"
            )

        # Response should contain asset data
        assert result is not None
        assert len(result) > 0


# Test 2: Check process_query returns direct response when no tool call needed
@pytest.mark.asyncio
async def test_process_query_no_tool_call():
    # Mock the entire LangChainService
    with patch("app.services.langchain_service.ChatGoogleGenerativeAI") as mock_llm:

        # Model responds directly without tool call (e.g. greeting)
        direct_msg = MagicMock()
        direct_msg.tool_calls = []
        direct_msg.content = "Hello! How can I help you today?"
        direct_msg.usage_metadata = {"input_tokens": 5, "output_tokens": 10, "total_tokens": 15}

        mock_model_instance = MagicMock()
        mock_model_instance.invoke.return_value = direct_msg
        mock_model_instance.bind_tools.return_value = mock_model_instance
        mock_llm.return_value = mock_model_instance

        from app.services.langchain_service import LangChainService
        service = LangChainService()

        messages = [HumanMessage(content="Hello")]
        result, context_summary, _ = await service.process_query(
            messages, user_name="testuser", session_id="sess-001"
        )

    # Direct response should be returned as-is
    assert result == "Hello! How can I help you today?"
    assert context_summary == result


# Test 3: Check process_query raises error when user_name is missing
@pytest.mark.asyncio
async def test_process_query_missing_user_name():
    with patch("app.services.langchain_service.ChatGoogleGenerativeAI") as mock_llm:
        mock_model_instance = MagicMock()
        mock_model_instance.bind_tools.return_value = mock_model_instance
        mock_llm.return_value = mock_model_instance

        from app.services.langchain_service import LangChainService
        service = LangChainService()

        messages = [HumanMessage(content="show me assets")]

        # Missing user_name should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            await service.process_query(messages, user_name=None, session_id="sess-001")

        assert "user_name is required" in str(exc_info.value)