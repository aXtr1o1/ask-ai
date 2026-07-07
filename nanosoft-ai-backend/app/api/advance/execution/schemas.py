"""
Execution — Data Shapes

This file holds ALL data structure definitions used in the execution module.

  AgentState → TypedDict used by LangGraph to carry state through the agent graph
               Every node (ask_llm, run_tool, collect_result) reads from and writes to this.
               When routes are added later, RunRequest / RunResponse go here too.

Used by:
  agent.py → StateGraph(AgentState), ask_llm, collect_result
"""
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


# =============================================================================
# AGENT STATE — used by LangGraph to carry data through the agent graph
#
# Fields:
#   messages         → full conversation history (LangGraph appends to this automatically)
#   question         → the FM analytics question text
#   modules          → which data modules are loaded (e.g. ["bdm", "ppm"])
#   filter_fields    → metadata about each filter field → sent to LLM as context
#   filtered_records → actual data per module → tools read this, LLM NEVER sees it
#   result           → final structured answer (filled by collect_result at the end)
#
# Used by: agent.py → StateGraph(AgentState), ask_llm, collect_result
# =============================================================================
class AgentState(TypedDict):
    messages:             Annotated[list, add_messages]   # LangGraph manages appending to this
    question:             str
    modules:              list[str]
    filter_fields:        dict[str, Any]
    module_filter_values: dict[str, Any]
    filtered_records:     dict[str, list[dict]]
    result:               dict[str, Any]
