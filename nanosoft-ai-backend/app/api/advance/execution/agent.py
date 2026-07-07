"""
FM Analytics Agent

Each question is independent. No history between questions.

Flow:
  test_agent.py builds the question message and puts it in initial_state["messages"]
  START
    → ask_llm       : send messages to LLM → LLM picks a tool
    → run_tool      : LangGraph runs the tool on filtered data
    → ask_llm       : LLM reads tool result → gives final answer
    → collect_result: package tool output + answer into clean result
"""
import json
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.config import settings
from app.api.advance.execution.prompts import SYSTEM_PROMPT
from app.api.advance.execution.tools import ALL_TOOLS
from app.api.advance.execution.schemas import AgentState
from app.api.advance.execution.agent_logger import (
    log_question, log_why, log_tool_call, log_tool_result, log_answer
)

logger = logging.getLogger("advance.execution.agent")


# =============================================================================
# HELPER: read text from a Gemini AI message
#
# Gemini returns content in two formats:
#   1. Plain string       → normal text reply
#   2. List of blocks     → thinking mode (Gemini 2.5 Flash)
#      Each block is {"type": "thinking", "thinking": "..."} or {"type": "text", "text": "..."}
#
# This function always returns a plain string from either format.
# Called by: ask_llm, collect_result
# =============================================================================
def get_text_from_ai_message(msg: AIMessage) -> str:
    """Read the plain text out of a Gemini AI message."""
    content = msg.content

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        # Check for "text" block FIRST — this is the actual answer.
        # "thinking" is internal reasoning and should only be used as a last resort fallback.
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                return block["text"]
        # Fallback: if no text block found, return the thinking content
        for block in content:
            if isinstance(block, dict) and block.get("type") == "thinking" and block.get("thinking"):
                return block["thinking"]

    return str(content)


# =============================================================================
# NODE 1: ask_llm
#
# Sends all current messages to the LLM and returns its response.
# The question is already in state["messages"] (built by test_agent.py).
# After a tool runs, the tool result is also in state["messages"] automatically.
# =============================================================================
def ask_llm(state: AgentState) -> dict:
    """Send all current messages to the LLM and return its response."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=1,
        thinking_budget=3000,
    ).bind_tools(ALL_TOOLS)

    # Always send: [SystemMessage] + all current messages (question + any tool results)
    response = llm.invoke([SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"]))
    return {"messages": [response]}



# =============================================================================
# NODE 2: collect_result
#
# What it does:
#   After the agent is done, walks through all messages and builds a clean result:
#     - tool_outputs    : what each tool returned
#     - answer          : the LLM's final text answer
#     - execution_trace : step-by-step log (which tool was called, what it returned)
# =============================================================================
def collect_result(state: AgentState) -> dict:
    """Package tool outputs and the final answer into a clean structured result."""
    messages = state["messages"]

    log_question(state["question"], state.get("module_filter_values"))

    # Collect tool outputs keyed by tool_call_id
    tool_outputs_by_id: dict[str, dict] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            try:
                tool_outputs_by_id[msg.tool_call_id] = json.loads(msg.content)
            except Exception:
                tool_outputs_by_id[msg.tool_call_id] = {"raw": msg.content}

    # Build execution trace from AI messages
    execution_trace = []
    step = 0

    for msg in messages:
        if not isinstance(msg, AIMessage):
            continue

        if msg.tool_calls:
            step += 1
            reasoning = get_text_from_ai_message(msg)
            log_why(reasoning)

            tools_called = []
            for tc in msg.tool_calls:
                output = tool_outputs_by_id.get(tc["id"], {})
                log_tool_call(tc["name"], tc["args"])
                log_tool_result(output, tc["args"])
                tools_called.append({"tool": tc["name"], "args": tc["args"], "output": output})

            execution_trace.append({
                "step":      step,
                "type":      "llm_decides_tool",
                "reasoning": reasoning,
                "tools":     tools_called,
            })

        else:
            final_text = get_text_from_ai_message(msg)
            log_answer(final_text)
            execution_trace.append({"type": "final_answer", "answer": final_text})

    last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)

    return {
        "result": {
            "question":        state["question"],
            "tool_outputs":    list(tool_outputs_by_id.values()),
            "answer":          get_text_from_ai_message(last_ai) if last_ai else "",
            "execution_trace": execution_trace,
        }
    }


# =============================================================================
# GRAPH: wire the nodes together
#
# START → ask_llm
#   ↓ (LLM chose a tool)
# run_tool → ask_llm → (LLM gives final answer) → collect_result → END
# =============================================================================
def create_agent_graph():
    """Build and compile the LangGraph agent graph."""
    graph = StateGraph(AgentState)

    graph.add_node("ask_llm",        ask_llm)
    graph.add_node("run_tool",       ToolNode(ALL_TOOLS))
    graph.add_node("collect_result", collect_result)

    graph.add_edge(START, "ask_llm")

    # tools_condition (LangGraph built-in):
    #   last message has tool_calls? → go to run_tool
    #   last message is a plain answer? → go to collect_result
    graph.add_conditional_edges(
        "ask_llm",
        tools_condition,
        {"tools": "run_tool", END: "collect_result"}
    )

    graph.add_edge("run_tool", "ask_llm")      # tool result goes back to LLM
    graph.add_edge("collect_result", END)

    return graph.compile()


# =============================================================================
# SINGLETON: build the agent once, reuse on every call
# =============================================================================
_agent_instance = None

def get_agent():
    """Return the compiled agent (built once, reused on every call)."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = create_agent_graph()
    return _agent_instance
