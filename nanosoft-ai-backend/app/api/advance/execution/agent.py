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


# ── Helpers: parse Gemini content blocks ──────────────────────────────────
def _extract_thinking(msg: AIMessage) -> str:
    """
    Attempt to extract Gemini's thinking/reasoning text.
    Note: LangChain's Google GenAI wrapper currently encrypts the thinking
    content in extras['signature'] and does not expose the raw text.
    Returns empty string if not available.
    """
    content = msg.content
    if not isinstance(content, list):
        return ""
    for item in content:
        if not isinstance(item, dict):
            continue
        # Format 1: dedicated thinking block (older LangChain versions)
        if item.get("type") == "thinking" and item.get("thinking"):
            return item["thinking"]
        # Format 2: extras dict with exposed thinking key
        extras = item.get("extras", {})
        if isinstance(extras, dict) and extras.get("thinking"):
            return extras["thinking"]
    return ""


def _extract_reasoning(msg: AIMessage) -> str:
    """
    Extract the LLM's visible text rationale from a tool-calling AIMessage.
    When the model calls tools it sometimes includes a short text explanation
    alongside the tool_calls. This is used as the WHY in the execution trace
    when the raw thinking block is not accessible.
    """
    thinking = _extract_thinking(msg)
    if thinking:
        return thinking
    # Fall back to visible text block
    return _extract_text(msg)


def _extract_text(msg: AIMessage) -> str:
    """Extract plain text from an AIMessage (handles list or str content)."""
    content = msg.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ).strip()
    return str(content)


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
    """
    Walk the full message history and build a detailed execution trace:

      agent_decides_tools  →  { step, thinking, tools: [{tool, args, output}] }
      final_answer         →  { thinking, text }

    Also keeps the flat tool_outputs list for backwards compat.
    """
    messages = state["messages"]

    # Build lookup: tool_call_id → parsed tool output
    tool_output_by_id: dict[str, dict] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            try:
                tool_output_by_id[msg.tool_call_id] = json.loads(msg.content)
            except Exception:
                tool_output_by_id[msg.tool_call_id] = {"raw": msg.content}

    # Build execution trace
    execution_trace = []
    decision_step = 0

    for msg in messages:
        if not isinstance(msg, AIMessage):
            continue

        if msg.tool_calls:
            # ── Agent decided to call tool(s) ────────────────────────────
            decision_step += 1
            thinking = _extract_reasoning(msg)

            tools_info = []
            for tc in msg.tool_calls:
                tools_info.append({
                    "tool":   tc["name"],
                    "args":   tc["args"],
                    "output": tool_output_by_id.get(tc["id"], {}),
                })
                logger.info(
                    "[TRACE] step=%d  tool=%s  args=%s",
                    decision_step, tc["name"], tc["args"],
                )

            execution_trace.append({
                "step":     decision_step,
                "type":     "agent_decides_tools",
                "thinking": thinking,
                "tools":    tools_info,
            })

        else:
            # ── Final answer (no more tool calls) ────────────────────────
            thinking  = _extract_thinking(msg)
            final_txt = _extract_text(msg)
            execution_trace.append({
                "type":     "final_answer",
                "thinking": thinking,
                "text":     final_txt,
            })
            logger.info("[TRACE] final answer produced")

    # Flat tool_outputs list (backwards compat)
    tool_results = list(tool_output_by_id.values())

    last_ai = next(
        (m for m in reversed(messages) if isinstance(m, AIMessage)),
        None,
    )

    return {
        "result": {
            "question":             state["question"],
            "tool_outputs":         tool_results,
            "agent_interpretation": _extract_text(last_ai) if last_ai else "",
            "execution_trace":      execution_trace,
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
