"""
Formatting Agent — Node 8 (Final) in the LangGraph multi-agent pipeline.

Responsibilities:
  - Determine the semantic RESPONSE TYPE (what kind of answer this is:
    count, breakdown, list, comparison, report, analysis, summary, ranking, etc.)
  - Determine the LAYOUT (how to present it: TABLE, BULLET_LIST, MARKDOWN, etc.)
  - Transform the final_answer from the Execution Agent into that layout
  - Write a structured JSON envelope to state — this is what the API returns

OUTPUT SHAPE (always JSON):
  {
    "response_type": "<semantic type — e.g. breakdown, report, comparison>",
    "layout":        "<PLAIN_TEXT|BULLET_LIST|NUMBERED_LIST|TABLE|JSON|MARKDOWN>",
    "format_reason": "<why this type and layout>",
    "formatted_answer": "<content in the chosen layout>"
  }

WHY this is the last node (after overall_validation_agent):
  The pipeline order is: Execute → Validate Quality → Format.
  We validate quality BEFORE formatting because if the answer needs to be re-generated,
  we don't want to waste time formatting a bad answer that will be discarded.
  Only once overall_validation confirms the answer is good (or max retries reached)
  do we format it for the user.

WHY a separate formatting node (not baked into execution_agent):
  The Execution Agent produces correct, reasoning-focused natural language.
  Asking it to ALSO detect and apply user format preferences mixes two concerns,
  bloats its prompt, and risks format detection errors affecting answer correctness.
  A dedicated formatting agent is a clean post-processing step with its own prompt.

WHY this uses a lower thinking budget:
  Format detection and transformation is a structured task — not deep reasoning.
  The model reads the query for keywords and applies transformation rules.
  500 thinking tokens is sufficient. More would be wasteful.

Model: gemini-2.5-flash with thinking enabled (thinking_budget=500)
"""

import json
import time
from typing import Dict, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.agents.prompts.formatting_prompt import (
    FORMATTING_SYSTEM_PROMPT,
    FORMATTING_USER_TEMPLATE,
)
# WHY these helpers: see log_config.py for detailed explanations.
from app.agents.log_config import (
    setup_agent_logger,
    extract_token_counts,
    parse_llm_text,
    strip_json_fences,
)
from app.config import settings

logger = setup_agent_logger("formatting_agent")


# ── Model initialisation ──────────────────────────────────────────────────────

def _build_model() -> ChatGoogleGenerativeAI:
    """
    Build the Formatting Agent model with the lowest thinking budget in the pipeline.

    WHY thinking_budget=500 (lowest):
      Format detection = scan query for keywords (table, list, JSON, etc.)
      Format transformation = apply layout rules to existing text.
      Neither task requires deep multi-step reasoning. 500 tokens is sufficient.
      Using 8000 tokens here would be expensive and wasteful for a pattern-matching task.
    """
    return ChatGoogleGenerativeAI(
        model=settings.MULTI_AGENT_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=1,          # required for thinking mode (Gemini constraint)
        thinking_budget=500,
    )


# ── Console printer ───────────────────────────────────────────────────────────

def _print_formatting_log(
    response_type: str,
    layout: str,
    format_reason: str,
    formatted_answer_len: int,
    token_counts: dict,
    query: str,
    latency: float,
) -> str:
    """Print a clean structured log block matching the || format of all other agents."""
    log = (
        f"\n"
        f"|| ============================================================\n"
        f"||  FORMATTING AGENT -- RESULT\n"
        f"|| ============================================================\n"
        f"||  Query               : {query[:80]}\n"
        f"||  Response Type       : {response_type}\n"
        f"||  Layout              : {layout}\n"
        f"||  Format Reason       : {format_reason[:120]}\n"
        f"||  Formatted Answer Len: {formatted_answer_len} chars\n"
        f"||  Thinking Tokens     : {token_counts['thinking']:,}\n"
        f"||  Input Tokens        : {token_counts['input']:,}\n"
        f"||  Output Tokens       : {token_counts['output']:,}\n"
        f"||  Latency             : {latency:.3f}s\n"
        f"|| ============================================================"
    )
    logger.info(log)
    return log


# ── Main agent node ───────────────────────────────────────────────────────────

async def formatting_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Formatting Agent.

    Reads:  state['user_query'], state['conversation_history'], state['final_answer']
    Writes: state['formatted_answer'], state['detected_format'],
            state['formatting_log'], state['formatting_thinking_tokens'], state['agent_trace']
    """
    user_query           = state.get("user_query", "").strip()
    conversation_history = state.get("conversation_history", []) or []
    # WHY read final_answer (not formatted_answer): formatting_agent is always the
    # first (and only) agent to write formatted_answer. It reads the raw final_answer
    # from execution_agent and produces the formatted version.
    final_answer         = state.get("final_answer", "") or ""
    trace                = list(state.get("agent_trace", []))

    logger.info("=" * 66)
    logger.info(
        "Formatting Agent -- START | query='%s' | answer_len=%d",
        user_query[:80], len(final_answer),
    )
    logger.info("=" * 66)
    _t_start = time.perf_counter()

    # ── Graceful short-circuit: no answer to format ───────────────────────────
    # WHY: If execution_agent produced an empty answer (e.g. due to an error),
    # there's nothing to format. Return a safe fallback immediately.
    if not final_answer.strip():
        logger.warning("|| [FormattingAgent] final_answer is empty — returning as-is")
        latency = round(time.perf_counter() - _t_start, 3)
        trace.append(
            f"[FormattingAgent] detected_format=PLAIN_TEXT (empty answer) | latency={latency:.3f}s"
        )
        log_str = _print_formatting_log(
            detected_format="PLAIN_TEXT",
            format_reason="final_answer was empty — nothing to format",
            formatted_answer_len=0,
            token_counts={"thinking": 0, "input": 0, "output": 0},
            query=user_query,
            latency=latency,
        )
        return {
            **state,
            "formatted_answer":           final_answer,
            "detected_format":            "PLAIN_TEXT",
            "formatting_log":             log_str,
            "formatting_thinking_tokens": 0,
            "latency_formatting":         latency,
            "agent_trace":                trace,
        }

    # ── Build a compact conversation history string for the prompt ────────────
    # WHY: We only need the last 4 messages for format context.
    # Older messages are unlikely to change the expected format.
    recent_history = conversation_history[-4:] if conversation_history else []
    history_str = "\n".join(
        f"{msg.get('role', 'user').upper()}: {str(msg.get('content', ''))[:200]}"
        for msg in recent_history
    ) or "No prior conversation."

    # ── Log intention ─────────────────────────────────────────────────────────
    logger.info(
        "\n|| ============================================================\n"
        "||  FORMATTING AGENT -- HOW I WILL FORMAT\n"
        "|| ============================================================\n"
        "||  The model will reason about the user's query and content\n"
        "||  to determine:\n"
        "||    1. RESPONSE TYPE  — what kind of answer this semantically is\n"
        "||    2. LAYOUT         — how to present it visually\n"
        "||  Output is always a JSON envelope with type + layout + content.\n"
        "|| ============================================================"
    )

    user_content = FORMATTING_USER_TEMPLATE.format(
        user_query=user_query,
        conversation_history=history_str,
        final_answer=final_answer,
    )

    messages = [
        SystemMessage(content=FORMATTING_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    # ── Invoke model ──────────────────────────────────────────────────────────
    try:
        model    = _build_model()
        response = await model.ainvoke(messages)

        token_counts   = extract_token_counts(response)
        raw_text       = parse_llm_text(response)
        raw_text       = strip_json_fences(raw_text)
        result_json       = json.loads(raw_text)

        response_type     = result_json.get("response_type", "general")
        layout            = result_json.get("layout", "MARKDOWN")
        format_reason     = result_json.get("format_reason", "")
        formatted_answer  = result_json.get("formatted_answer", final_answer)

        # Validate layout value — model may return unexpected strings
        valid_layouts = {"PLAIN_TEXT", "BULLET_LIST", "NUMBERED_LIST", "TABLE", "JSON", "MARKDOWN"}
        if layout not in valid_layouts:
            logger.warning(
                "|| [FormattingAgent] unexpected layout='%s' — defaulting to MARKDOWN",
                layout,
            )
            layout = "MARKDOWN"

        # Fallback if formatted_answer is empty
        if not formatted_answer or not str(formatted_answer).strip():
            logger.warning(
                "|| [FormattingAgent] formatted_answer empty — falling back to final_answer"
            )
            formatted_answer = final_answer

        # Build the structured JSON envelope that downstream systems consume
        json_envelope = {
            "response_type":    response_type,
            "layout":           layout,
            "format_reason":    format_reason,
            "formatted_answer": str(formatted_answer),
        }

        logger.info(
            "|| [FormattingAgent] JSON envelope | response_type=%s | layout=%s",
            response_type, layout,
        )

    except (json.JSONDecodeError, Exception) as exc:
        logger.error("Formatting Agent error: %s", exc, exc_info=True)
        response_type    = "general"
        layout           = "MARKDOWN"
        format_reason    = "Formatting agent encountered an error — returning final_answer as-is"
        formatted_answer = final_answer
        token_counts     = {"thinking": 0, "input": 0, "output": 0}
        json_envelope    = {
            "response_type":    response_type,
            "layout":           layout,
            "format_reason":    format_reason,
            "formatted_answer": str(formatted_answer),
        }

    # ── Result log ────────────────────────────────────────────────────────────
    latency = round(time.perf_counter() - _t_start, 3)
    logger.info("|| [FormattingAgent] latency=%.3f s | response_type=%s | layout=%s", latency, response_type, layout)

    preview = str(formatted_answer)[:200].replace("\n", " ") + ("..." if len(str(formatted_answer)) > 200 else "")
    logger.info("|| [FormattingAgent] formatted_answer preview: %s", preview)
    logger.info("|| [FormattingAgent] JSON envelope: %s", json.dumps(json_envelope, ensure_ascii=False)[:400])

    log_str = _print_formatting_log(
        response_type=response_type,
        layout=layout,
        format_reason=format_reason,
        formatted_answer_len=len(str(formatted_answer)),
        token_counts=token_counts,
        query=user_query,
        latency=latency,
    )

    trace.append(
        f"[FormattingAgent] response_type={response_type} | layout={layout} | "
        f"formatted_len={len(str(formatted_answer))} | "
        f"thinking={token_counts['thinking']} | latency={latency:.3f}s"
    )

    return {
        **state,
        "formatted_answer":           json.dumps(json_envelope, ensure_ascii=False),
        "detected_format":            layout,
        "formatting_log":             log_str,
        "formatting_thinking_tokens": token_counts["thinking"],
        "total_input_tokens":  state.get("total_input_tokens", 0) + token_counts.get("input", 0),
        "total_output_tokens": state.get("total_output_tokens", 0) + token_counts.get("output", 0),
        "total_thinking_tokens": state.get("total_thinking_tokens", 0) + token_counts.get("thinking", 0),
        "latency_formatting":         latency,
        "agent_trace":                trace,
    }
