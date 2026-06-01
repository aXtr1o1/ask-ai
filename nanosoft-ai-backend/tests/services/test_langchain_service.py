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


def test_complaint_clear_when_bdm_and_fa_named():
    from app.services.langchain_service import _complaint_query_is_clear

    assert _complaint_query_is_clear(
        "give me Closed BDM and FA complaints are registered", []
    )
    assert _complaint_query_is_clear(
        "show me how many Closed BDM and FA complaints are registered", []
    )
    assert not _complaint_query_is_clear("give me closed complaints", [])


def test_infer_intent_show_me_how_many_is_list():
    from app.services.langchain_service import _infer_intent_from_query, _query_wants_list_display

    q = "show me how many Closed BDM and FA complaints are registered"
    assert _query_wants_list_display(q) is True
    assert _infer_intent_from_query(q) == "list"


def test_infer_intent_how_many_only_is_count():
    from app.services.langchain_service import _infer_intent_from_query, _query_wants_list_display

    q = "how many Closed BDM and FA complaints are registered"
    assert _query_wants_list_display(q) is False
    assert _infer_intent_from_query(q) == "count"


def test_strip_redundant_table_offer():
    from app.services.langchain_service import _strip_redundant_table_offer

    text = (
        "I found 1 BDM and 12 FA complaints for Corridor. "
        "Would you like to view this data as a markdown table for better understanding?"
    )
    assert "markdown table" not in _strip_redundant_table_offer(text).lower()
    assert "1 BDM" in _strip_redundant_table_offer(text)


@pytest.mark.asyncio
async def test_multi_tool_count_query_does_not_report_no_records():
    """Count queries across BDM+FA must not short-circuit when p_list is cleared."""
    from app.services.langchain_service import LangChainService

    with patch("app.services.langchain_service.ChatGoogleGenerativeAI") as mock_llm:
        first_ai_msg = MagicMock()
        first_ai_msg.tool_calls = [
            {
                "name": "BDM",
                "id": "tool-call-bdm",
                "args": {"user_name": "poc", "status": "Closed"},
            },
            {
                "name": "FA",
                "id": "tool-call-fa",
                "args": {"user_name": "poc", "stage": "Closed"},
            },
        ]
        first_ai_msg.usage_metadata = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}

        summary_msg = MagicMock()
        summary_msg.content = (
            "There are 12 closed BDM complaints and 8 closed FA complaints registered."
        )
        summary_msg.usage_metadata = {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30}

        mock_model_instance = MagicMock()
        mock_model_instance.invoke.side_effect = [first_ai_msg, summary_msg]
        mock_model_instance.bind_tools.return_value = mock_model_instance
        mock_llm.return_value = mock_model_instance

        with patch("app.services.langchain_service.BDM") as mock_bdm, patch(
            "app.services.langchain_service.FA"
        ) as mock_fa:
            mock_bdm.invoke.return_value = json.dumps({"p_list": [], "p_count": 12})
            mock_fa.invoke.return_value = json.dumps({"p_list": [], "p_count": 8})

            service = LangChainService()
            messages = [
                HumanMessage(
                    content="how many Closed BDM and FA complaints are registered"
                )
            ]
            result, context_summary, _ = await service.process_query(
                messages, user_name="poc", session_id="sess-multi-count"
            )

    assert "No records were found" not in result
    assert "No records were found" not in context_summary
    assert "12" in result or "BDM" in result or "closed" in result.lower()
    
    parsed_result = json.loads(result)
    assert parsed_result["type"] == "multiple_datasets"
    assert parsed_result["context_summary"] == context_summary
    assert len(parsed_result["datasets"]) == 2


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