from langchain_core.messages import HumanMessage, AIMessage

from app.state import cap_history, lc_memory_for_model, trim_session


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
