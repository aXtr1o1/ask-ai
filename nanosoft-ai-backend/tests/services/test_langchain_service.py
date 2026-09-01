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

    classify_result = {
        "intent": "db_query",
        "query_summary": "list of active assets",
        "modules": ["assets"],
        "response_format": "PLAIN_TEXT",
        "user_specified_format": False,
        "general_response": None,
        "web_search_summary": None,
        "token_usage": {},
    }

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

        with patch("app.services.langchain_service.ASSETS") as mock_assets_tool, \
             patch(
                 "app.services.langchain_service.classify_query",
                 return_value=classify_result,
             ):
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
async def test_multi_tool_count_query_does_not_report_no_records():
    """Count queries across BDM+FA must not short-circuit when p_list is cleared.

    Current flow (see langchain_service.process_query): classify_query()
    (Understanding Agent) decides intent/modules -> _check_level() (one
    self.model.invoke call) -> _run_module() per module (one self.model.invoke
    call each, then the module function is called directly, not via .invoke())
    -> _handle_multi_module() (one more self.model.invoke call for the summary).
    """
    from app.services.langchain_service import LangChainService

    classify_result = {
        "intent": "db_query",
        "query_summary": "count of closed BDM and FA complaints",
        "modules": ["bdm", "fa"],
        "response_format": "PLAIN_TEXT",
        "user_specified_format": False,
        "general_response": None,
        "web_search_summary": None,
        "token_usage": {},
    }

    level_msg = MagicMock()
    level_msg.content = '{"level": 1}'
    level_msg.usage_metadata = {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7}

    bdm_payload_msg = MagicMock()
    bdm_payload_msg.content = '{"is_aggregate": false, "response_type": "count", "filters": {"status": "Closed"}}'
    bdm_payload_msg.usage_metadata = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}

    fa_payload_msg = MagicMock()
    fa_payload_msg.content = '{"is_aggregate": false, "response_type": "count", "filters": {"stage": "Closed"}}'
    fa_payload_msg.usage_metadata = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}

    summary_msg = MagicMock()
    summary_msg.content = (
        "There are 12 closed BDM complaints and 8 closed FA complaints registered."
    )
    summary_msg.usage_metadata = {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30}

    with patch("app.services.langchain_service.ChatGoogleGenerativeAI") as mock_llm:
        mock_model_instance = MagicMock()
        mock_model_instance.invoke.side_effect = [
            level_msg, bdm_payload_msg, fa_payload_msg, summary_msg,
        ]
        mock_model_instance.bind_tools.return_value = mock_model_instance
        mock_llm.return_value = mock_model_instance

        mock_bdm = MagicMock(return_value=json.dumps({"p_list": [], "p_count": 12}))
        mock_fa = MagicMock(return_value=json.dumps({"p_list": [], "p_count": 8}))

        with patch(
            "app.services.langchain_service.classify_query", return_value=classify_result
        ), patch.dict(
            # MODULE_TOOL_MAP is built once at import time with direct references
            # to the real BDM/FA functions — patching the module-level names
            # "BDM"/"FA" doesn't touch what's already bound inside this dict, so
            # the dict entries themselves must be patched instead.
            "app.services.langchain_service.MODULE_TOOL_MAP",
            {"bdm": mock_bdm, "fa": mock_fa},
        ):
            # BDM/FA are plain functions called directly (tool_fn(**payload)),
            # not LangChain @tool objects — no .invoke().

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
    """Test direct response for a general-intent query (no module/tool involved).

    'No tool call' in the current architecture means classify_query()
    (Understanding Agent) classified the query as intent='general' — process_query
    returns its general_response immediately, before self.model / any module
    function is ever touched.
    """
    from app.services.langchain_service import LangChainService

    classify_result = {
        "intent": "general",
        "query_summary": None,
        "modules": [],
        "response_format": None,
        "user_specified_format": False,
        "general_response": "Hello! How can I help you today?",
        "web_search_summary": None,
        "token_usage": {},
    }

    with patch("app.services.langchain_service.ChatGoogleGenerativeAI") as mock_llm:
        mock_model_instance = MagicMock()
        mock_model_instance.bind_tools.return_value = mock_model_instance
        mock_llm.return_value = mock_model_instance

        with patch(
            "app.services.langchain_service.classify_query", return_value=classify_result
        ):
            service = LangChainService()
            messages = [HumanMessage(content="Hello")]
            result, context_summary, _ = await service.process_query(
                messages, user_name="testuser", session_id="sess-001"
            )

    assert result == "Hello! How can I help you today?"
    assert context_summary == "Hello! How can I help you today?"


@pytest.mark.asyncio
async def test_process_query_missing_user_name():
    """Test error handling when user_name is missing"""

    from app.services.langchain_service import LangChainService

    service = LangChainService()
    messages = [HumanMessage(content="show me assets")]

    with pytest.raises(ValueError) as exc_info:
        await service.process_query(messages, user_name=None, session_id="sess-001")

    assert "user_name is required" in str(exc_info.value)