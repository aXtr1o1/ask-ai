"""
Execution — LangGraph Agent

Graph:  START → agent → [tool_node → agent]* → END

State:
  - question:          str   — the FM analytics question (sent to LLM)
  - filter_fields:     dict  — metadata about filters applied (sent to LLM)
  - filtered_records:  dict  — actual data per module (NEVER sent to LLM, injected into tools via state)
  - messages:          list  — LangGraph message history
  - result:            dict  — final structured answer

The LLM sees: question + filter_fields only.
The tools see: filtered_records (via InjectedState) + operation params from LLM.
"""
import json
import logging
import os
from typing import Annotated, Any, Optional, TypedDict

from app.config import settings

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.api.advance.execution.prompts import SYSTEM_PROMPT
from app.api.advance.execution.tools import ALL_TOOLS

logger = logging.getLogger("advance.execution.agent")


# ── State ──────────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    messages:          Annotated[list, add_messages]
    question:          str
    modules:           list[str]                       # which data modules are loaded (e.g. ["bdm"])
    filter_fields:     dict[str, Any]                 # metadata — goes to LLM as context
    filtered_records:  dict[str, list[dict]]          # data — accessed only by tools via InjectedState
    result:            dict[str, Any]


# ── LLM — Gemini 2.5 Flash (hardcoded) ──────────────────────────────────
def _build_model() -> "ChatGoogleGenerativeAI":
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=1,
        thinking_budget=3000,
    ).bind_tools(ALL_TOOLS)


# ── Node: agent ───────────────────────────────────────────────────────────
def agent_node(state: AgentState) -> dict:
    """
    Sends the question + filter metadata to the LLM.
    LLM decides formula → calls the appropriate tool(s).

    Message ordering (Gemini requirement):
      First call:      [SystemMessage, HumanMessage]           → AIMessage(tool_calls)
      Subsequent call: [SystemMessage, HumanMessage, AIMessage, ToolMessage] → AIMessage(final)
    """
    llm = _build_model()
    existing = list(state["messages"])

    if not existing:
        # ── First call: build human message ──────────────────────────────
        filter_context = (
            json.dumps(state["filter_fields"], indent=2)
            if state["filter_fields"]
            else "No filters applied."
        )
        human_msg = HumanMessage(content=(
            f"Question: {state['question']}\n\n"
            f"Data modules loaded for this question: {state.get('modules', [])}\n"
            f"(Use only these module names when calling tools)\n\n"
            f"Filter fields applied to scope the data:\n{filter_context}\n\n"
            f"Determine the formula and call the appropriate tool(s) to compute the answer."
        ))
        messages_to_send = [SystemMessage(content=SYSTEM_PROMPT), human_msg]
        response = llm.invoke(messages_to_send)
        # Store BOTH human_msg + AI response so subsequent calls have full history
        return {"messages": [human_msg, response]}
    else:
        # ── Subsequent calls: history already has HumanMessage + tool results ─
        messages_to_send = [SystemMessage(content=SYSTEM_PROMPT)] + existing
        response = llm.invoke(messages_to_send)
        return {"messages": [response]}



# ── Routing: continue to tool or end ─────────────────────────────────────
def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "end"


# ── Node: extract final result from messages ──────────────────────────────
def extract_result(state: AgentState) -> dict:
    """Collect all tool outputs into the result dict."""
    tool_outputs = [
        m for m in state["messages"]
        if isinstance(m, ToolMessage)
    ]
    last_ai = next(
        (m for m in reversed(state["messages"]) if isinstance(m, AIMessage)),
        None,
    )

    tool_results = []
    for tm in tool_outputs:
        try:
            tool_results.append(json.loads(tm.content))
        except Exception:
            tool_results.append({"raw": tm.content})

    return {
        "result": {
            "question": state["question"],
            "tool_outputs": tool_results,
            "agent_interpretation": last_ai.content if last_ai else "",
        }
    }


# ── Build the graph ───────────────────────────────────────────────────────
def build_agent():
    tool_node = ToolNode(ALL_TOOLS)

    builder = StateGraph(AgentState)
    builder.add_node("agent",          agent_node)
    builder.add_node("tools",          tool_node)
    builder.add_node("extract_result", extract_result)

    builder.add_edge(START,   "agent")
    builder.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": "extract_result"})
    builder.add_edge("tools", "agent")          # tool result → back to agent
    builder.add_edge("extract_result", END)

    return builder.compile()


# Singleton
_agent = None

def get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent
