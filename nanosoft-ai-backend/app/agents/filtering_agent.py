"""
Filtering Agent — Node 5 in the LangGraph multi-agent pipeline.
(Inserted between Mini Validation Agent and Execution Agent)

Responsibilities:
  - Receive validated retrieval results (raw, all fields)
  - Use LLM to decide which fields are relevant to answer the user's query
  - Python filters the raw data to only those fields
  - Pass the clean, precise filtered data to the Execution Agent

This keeps the Execution Agent focused — it only sees the data it needs.

Model: gemini-2.5-flash with LOW thinking budget (field selection is simple)
"""

import json
import logging
from typing import Dict, Any, List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.agents.prompts.filtering_prompt import (
    FILTERING_SYSTEM_PROMPT,
    FILTERING_USER_TEMPLATE,
)
from app.agents.log_config import setup_agent_logger
from app.config import settings

logger = setup_agent_logger("filtering_agent")


# ── Model initialisation ──────────────────────────────────────────────────────

def _build_model() -> ChatGoogleGenerativeAI:
    """Build the Filtering Agent model — low thinking budget, focused task."""
    return ChatGoogleGenerativeAI(
        model=settings.MULTI_AGENT_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=1,          # required for thinking mode
        thinking_budget=1000,   # low budget — field selection is a simple decision
    )


# ── Field filtering (pure Python) ────────────────────────────────────────────

def _filter_results(
    retrieval_results: List[Dict[str, Any]],
    keep_fields: List[str],
) -> List[Dict[str, Any]]:
    """
    Filter each result's data to only the specified fields.
    Preserves the result envelope (step_id, success, source, target, p_count).
    Only filters the records inside p_list.
    """
    if not keep_fields:
        return retrieval_results

    keep_set = set(keep_fields)
    filtered = []

    for result in retrieval_results:
        new_result = dict(result)

        # Keep envelope fields always
        # Filter p_list records if present
        data = result.get("data")
        if isinstance(data, dict):
            new_data = {}
            # Always keep p_count (aggregate count)
            if "p_count" in data:
                new_data["p_count"] = data["p_count"]

            # Filter p_list records
            p_list = data.get("p_list", [])
            if isinstance(p_list, list) and p_list:
                filtered_list = []
                for record in p_list:
                    if isinstance(record, dict):
                        filtered_record = {
                            k: v for k, v in record.items()
                            if k in keep_set
                        }
                        filtered_list.append(filtered_record)
                    else:
                        filtered_list.append(record)
                new_data["p_list"] = filtered_list
            elif "p_list" in data:
                new_data["p_list"] = data["p_list"]

            # Keep any other top-level data fields that are in keep_set
            for k, v in data.items():
                if k not in ("p_count", "p_list") and k in keep_set:
                    new_data[k] = v

            new_result["data"] = new_data

        elif isinstance(data, list):
            # Plain list of records
            filtered_list = []
            for record in data:
                if isinstance(record, dict):
                    filtered_record = {k: v for k, v in record.items() if k in keep_set}
                    filtered_list.append(filtered_record)
                else:
                    filtered_list.append(record)
            new_result["data"] = filtered_list

        filtered.append(new_result)

    return filtered


# ── Main agent node ───────────────────────────────────────────────────────────

async def filtering_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Filtering Agent.

    Reads:  state['user_query'], state['understood_intent'], state['goal_plan'],
            state['retrieval_results']
    Writes: state['filtered_results'], state['filtering_log'],
            state['filtering_thinking_tokens'], state['agent_trace']
    """
    user_query        = state.get("user_query", "").strip()
    understood_intent = state.get("understood_intent", {}) or {}
    goal_plan         = state.get("goal_plan", {}) or {}
    retrieval_results = state.get("retrieval_results", []) or []
    trace             = list(state.get("agent_trace", []))

    logger.info("=" * 66)
    logger.info("Filtering Agent -- START | query='%s'", user_query[:80])
    logger.info("=" * 66)

    # ── Short-circuit: no retrieval data → pass through empty ─────────────────
    if not retrieval_results:
        logger.info("|| No retrieval results to filter — passing through empty list")
        trace.append("[FilteringAgent] no data to filter | thinking_tokens=0")
        return {
            **state,
            "filtered_results":          [],
            "filtering_log":             "No retrieval results to filter.",
            "filtering_thinking_tokens": 0,
            "agent_trace":               trace,
        }

    # ── Short-circuit: DIRECT_ANSWER / CLARIFY ───────────────────────────────
    approach = goal_plan.get("approach", "")
    if approach in ("DIRECT_ANSWER", "CLARIFY"):
        logger.info("|| Approach is %s — no filtering needed", approach)
        trace.append(f"[FilteringAgent] approach={approach} | no filtering | thinking_tokens=0")
        return {
            **state,
            "filtered_results":          retrieval_results,
            "filtering_log":             f"No filtering needed — approach is {approach}",
            "filtering_thinking_tokens": 0,
            "agent_trace":               trace,
        }

    # ── Pre-filtering intention log ───────────────────────────────────────────
    total_raw_fields = 0
    for r in retrieval_results:
        data = r.get("data", {})
        if isinstance(data, dict):
            p_list = data.get("p_list", [])
            if p_list and isinstance(p_list, list) and isinstance(p_list[0], dict):
                total_raw_fields = len(p_list[0])
                break
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            total_raw_fields = len(data[0])
            break

    logger.info(
        "\n|| ============================================================\n"
        "||  FILTERING AGENT -- HOW I WILL FILTER\n"
        "|| ============================================================\n"
        "||  Raw Results    : %d retrieval step(s)\n"
        "||  Fields per Rec : ~%d (before filtering)\n"
        "||  I will         : Ask the LLM which fields are needed\n"
        "||                   Python then keeps ONLY those fields\n"
        "||                   Execution Agent gets clean, precise data\n"
        "|| ============================================================",
        len(retrieval_results), total_raw_fields
    )

    # ── Build prompt ──────────────────────────────────────────────────────────
    user_content = FILTERING_USER_TEMPLATE.format(
        user_query=user_query,
        understood_intent=json.dumps(understood_intent, indent=2),
        goal_plan=json.dumps(goal_plan, indent=2),
        retrieval_results=json.dumps(retrieval_results, indent=2),
    )

    messages = [
        SystemMessage(content=FILTERING_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    # ── Invoke model ──────────────────────────────────────────────────────────
    keep_fields: List[str] = []
    token_counts = {"thinking": 0, "input": 0, "output": 0}

    try:
        model = _build_model()
        response = await model.ainvoke(messages)

        # Extract token counts
        usage = getattr(response, "usage_metadata", None)
        if usage and isinstance(usage, dict):
            token_counts["input"]  = usage.get("input_tokens", 0) or 0
            token_counts["output"] = usage.get("output_tokens", 0) or 0
            out_details = usage.get("output_token_details") or {}
            if isinstance(out_details, dict):
                token_counts["thinking"] = out_details.get("reasoning", 0) or 0

        # Parse the field list from the LLM response
        raw_content = response.content
        if isinstance(raw_content, list):
            text_parts = [
                p.get("text", "") if isinstance(p, dict) else str(p)
                for p in raw_content
                if not (isinstance(p, dict) and p.get("type") == "thinking")
            ]
            raw_content = "".join(text_parts).strip()
        else:
            raw_content = str(raw_content).strip()

        # Strip markdown code fences if present
        if raw_content.startswith("```"):
            raw_content = raw_content.split("```")[1]
            if raw_content.startswith("json"):
                raw_content = raw_content[4:]
        raw_content = raw_content.strip()

        parsed = json.loads(raw_content)
        if isinstance(parsed, list):
            keep_fields = [str(f) for f in parsed if f]

    except (json.JSONDecodeError, Exception) as exc:
        logger.error("Filtering Agent error: %s", exc, exc_info=True)
        # On error: pass all data through unfiltered (safe fallback)
        keep_fields = []

    # ── Python filters the data ───────────────────────────────────────────────
    if keep_fields:
        filtered_results = _filter_results(retrieval_results, keep_fields)
        logger.info(
            "\n|| ============================================================\n"
            "||  FILTERING AGENT -- RESULT\n"
            "|| ============================================================\n"
            "||  Query          : %s\n"
            "||  Fields Kept    : %s\n"
            "||  Fields Removed : ~%d field(s) pruned per record\n"
            "||  Thinking Tokens: %s\n"
            "||  Input Tokens   : %s\n"
            "||  Output Tokens  : %s\n"
            "|| ============================================================",
            user_query[:80],
            keep_fields,
            max(0, total_raw_fields - len(keep_fields)),
            f"{token_counts['thinking']:,}",
            f"{token_counts['input']:,}",
            f"{token_counts['output']:,}",
        )
    else:
        # Fallback: no filtering, pass raw results through
        filtered_results = retrieval_results
        logger.info("|| Filtering Agent: no fields selected — passing raw results through")

    log_str = (
        f"Fields kept: {keep_fields} | "
        f"thinking_tokens={token_counts['thinking']} | "
        f"input_tokens={token_counts['input']}"
    )
    trace.append(
        f"[FilteringAgent] keep_fields={keep_fields} | "
        f"thinking_tokens={token_counts['thinking']}"
    )

    return {
        **state,
        "filtered_results":          filtered_results,
        "filtering_log":             log_str,
        "filtering_thinking_tokens": token_counts["thinking"],
        "agent_trace":               trace,
    }
