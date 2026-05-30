from langchain_core.messages import HumanMessage, AIMessage

from app.state import cap_history, lc_memory_for_model, trim_session
from app.services.query_router_service import (
    QueryIntent,
    detect_query_intent,
    pre_model_response,
    remember_data_request,
    resolve_followup_query,
    facility_tools_allowed,
)
from app.services.scoped_memory_service import direct_memory_response


def test_lc_memory_for_model_zero_clears():
    lc = [
        HumanMessage(content="hi my name is sanjeevan"),
        AIMessage(content="Hi Sanjeevan"),
    ]
    assert lc_memory_for_model(lc, 0) == []


def test_lc_memory_for_model_zero_avoids_python_slice_quirk():
    """[-0:] returns the full list; our helper must not use that."""
    history = [{"query": "a", "assistant": "b"}] * 3
    assert cap_history(history, 0) == []


def test_trim_session_max_zero_clears_lc_memory_keeps_history():
    session = {
        "history": [{"query": "a", "assistant": "b"}],
        "lc_memory": [HumanMessage(content="x"), AIMessage(content="y")],
    }
    trim_session(session, 0)
    assert session["history"] == [{"query": "a", "assistant": "b"}]
    assert session["lc_memory"] == []


def test_lc_memory_for_model_keeps_last_n_pairs():
    lc = [
        HumanMessage(content="1"),
        AIMessage(content="1"),
        HumanMessage(content="2"),
        AIMessage(content="2"),
        HumanMessage(content="3"),
        AIMessage(content="3"),
    ]
    result = lc_memory_for_model(lc, 2)
    assert len(result) == 4
    assert result[0].content == "2"
    assert result[-1].content == "3"


def test_trim_session_only_trims_lc_memory_for_model():
    lc_memory = []
    for i in range(5):
        lc_memory.append(HumanMessage(content=str(i)))
        lc_memory.append(AIMessage(content=str(i)))
    session = {
        "history": [{"query": str(i), "assistant": str(i)} for i in range(5)],
        "lc_memory": lc_memory,
    }
    trim_session(session, 2)
    assert len(session["history"]) == 5
    assert len(session["lc_memory"]) == 4


def test_direct_memory_response_handles_previously_asked_phrase():
    session = {
        "history": [
            {
                "query": "hi",
                "assistant": "Hello! How can I help you today?",
            }
        ]
    }

    assert direct_memory_response("what i previously asked", session) == (
        'Your previous question was "hi".'
    )


def test_direct_memory_response_handles_previous_query_phrase():
    session = {
        "history": [
            {
                "query": "show open BDM complaints",
                "assistant": "I found 4 open BDM complaints.",
            }
        ]
    }

    assert direct_memory_response("what was my previous query", session) == (
        'Your previous question was "show open BDM complaints".'
    )


def test_pre_model_router_blocks_memory_question_before_tools():
    session = {
        "history": [
            {
                "query": "show assets",
                "assistant": "I found 3837 assets.",
            }
        ]
    }

    intent, answer = pre_model_response("what i previously asked", session)

    assert intent == QueryIntent.CONVERSATION_MEMORY
    assert answer == 'Your previous question was "show assets".'


def test_pre_model_router_blocks_smalltalk_before_tools():
    intent, answer = pre_model_response("hi", {"history": []})

    assert intent == QueryIntent.SMALLTALK
    assert answer == "Hello! How can I help you today?"


def test_pre_model_router_allows_facility_data_queries():
    intent, answer = pre_model_response("show open BDM complaints", {"history": []})

    assert intent == QueryIntent.FACILITY_DATA
    assert answer is None


def test_detect_query_intent_memory_wins_over_facility_words():
    assert (
        detect_query_intent("what was my previous asset question")
        == QueryIntent.CONVERSATION_MEMORY
    )


def test_pre_model_router_remembers_user_name():
    session = {"history": []}

    intent, answer = pre_model_response("my name is mega", session)

    assert intent == QueryIntent.USER_PROFILE
    assert answer == "Nice to meet you, Mega. How can I help you today?"
    assert session["profile"]["preferred_name"] == "Mega"


def test_pre_model_router_answers_user_name_from_profile():
    session = {"history": [], "profile": {"preferred_name": "Mega"}}

    intent, answer = pre_model_response("what is my name", session)

    assert intent == QueryIntent.USER_PROFILE
    assert answer == "Your name is Mega."


def test_pre_model_router_recovers_user_name_from_history():
    session = {
        "history": [
            {
                "query": "my name is mega",
                "assistant": "Nice to meet you, Mega.",
            }
        ]
    }

    intent, answer = pre_model_response("you don't know the name", session)

    assert intent == QueryIntent.USER_PROFILE
    assert answer == "Your name is Mega."


def test_pre_model_router_handles_hlo_as_smalltalk():
    intent, answer = pre_model_response("hlo", {"history": []})

    assert intent == QueryIntent.SMALLTALK
    assert answer == "Hello! How can I help you today?"


def test_followup_resolver_rewrites_vague_list_from_last_data_request():
    session = {}
    remember_data_request(
        session,
        "how many good condition assets are there",
        'There are 3830 assets matching "Good" in our records, filtered by Condition.',
    )

    resolved, answer = resolve_followup_query("list me", session)

    assert answer is None
    assert resolved == "list Good condition assets"


def test_followup_resolver_blocks_bare_yes_without_pending_action():
    resolved, answer = resolve_followup_query("yes", {})

    assert resolved == "yes"
    assert answer == "What would you like me to continue with?"


def test_followup_resolver_allows_yes_with_pending_table():
    resolved, answer = resolve_followup_query("yes", {"pending_table": [{"id": 1}]})

    assert resolved == "yes"
    assert answer is None


def test_facility_tools_allowed_requires_facility_entity():
    assert facility_tools_allowed("how many good condition assets are there") is True
    assert facility_tools_allowed("what was my first question") is False
    assert facility_tools_allowed("list me") is False
    assert facility_tools_allowed("yes") is False
