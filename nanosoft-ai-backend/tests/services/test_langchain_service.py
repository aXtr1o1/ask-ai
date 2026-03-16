"""
test_langchain_service.py — Tests for LangChain AI service.
All mocking is handled by conftest.py automatically.
"""
import pytest
import json
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage


@pytest.mark.asyncio
async def test_process_query_with_tool_call():
    """Test that process_query handles tool calls correctly"""
    
    # Import AFTER conftest has set up mocks
    from app.services.langchain_service import LangChainService
    
    with patch("app.services.langchain_service.ChatGoogleGenerativeAI") as mock_llm:
        # First call — model decides to use ASSETS tool
        first_ai_msg = MagicMock()
        first_ai_msg.tool_calls = [{
            "name": "ASSETS",
            "id": "tool-call-1",
            "args": {"user_name": "testuser", "status": "Active"}
        }]
        first_ai_msg.usage_metadata = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}

        # Intent call
        intent_msg = MagicMock()
        intent_msg.content = "list"
        intent_msg.usage_metadata = {"input_tokens": 5, "output_tokens": 1, "total_tokens": 6}

        # Final answer
        final_msg = MagicMock()
        final_msg.content = "Found 1 asset."
        final_msg.usage_metadata = {"input_tokens": 20, "output_tokens": 30, "total_tokens": 50}

        mock_model_instance = MagicMock()
        mock_model_instance.invoke.side_effect = [first_ai_msg, intent_msg, final_msg]
        mock_model_instance.bind_tools.return_value = mock_model_instance
        mock_llm.return_value = mock_model_instance

        with patch("app.services.langchain_service.ASSETS") as mock_assets_tool:
            mock_assets_tool.invoke.return_value = json.dumps({
                "p_list": [{"AssetTagNo": "A001", "StatusName": "Active"}],
                "p_count": 1
            })

            service = LangChainService()
            messages = [HumanMessage(content="show me assets")]
            result, context_summary, _ = await service.process_query(
                messages, user_name="testuser", session_id="sess-001"
            )

    assert result is not None
    assert len(result) > 0


@pytest.mark.asyncio
async def test_process_query_no_tool_call():
    """Test direct response without tool calls"""
    
    from app.services.langchain_service import LangChainService
    
    with patch("app.services.langchain_service.ChatGoogleGenerativeAI") as mock_llm:
        direct_msg = MagicMock()
        direct_msg.tool_calls = []
        direct_msg.content = "Hello! How can I help you today?"
        direct_msg.usage_metadata = {"input_tokens": 5, "output_tokens": 10, "total_tokens": 15}

        mock_model_instance = MagicMock()
        mock_model_instance.invoke.return_value = direct_msg
        mock_model_instance.bind_tools.return_value = mock_model_instance
        mock_llm.return_value = mock_model_instance

        service = LangChainService()
        messages = [HumanMessage(content="Hello")]
        result, context_summary, _ = await service.process_query(
            messages, user_name="testuser", session_id="sess-001"
        )

    assert result == "Hello! How can I help you today?"


@pytest.mark.asyncio
async def test_process_query_missing_user_name():
    """Test error handling when user_name is missing"""
    
    from app.services.langchain_service import LangChainService
    
    service = LangChainService()
    messages = [HumanMessage(content="show me assets")]

    with pytest.raises(ValueError) as exc_info:
        await service.process_query(messages, user_name=None, session_id="sess-001")

    assert "user_name is required" in str(exc_info.value)