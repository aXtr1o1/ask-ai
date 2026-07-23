"""
FM Formatting Agent

This layer sits after execution and before the API/frontend response.
Its job is to normalize the raw pipeline output into a stable envelope that
the frontend can render consistently.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from google import genai
from app.config import settings
from app.api.advance.Formatting_agent.prompt import SYSTEM_PROMPT
from app.api.advance.Formatting_agent.tools import FORMATTING_TOOLS

logger = logging.getLogger("advance.formatting")


def _stringify_answer(answer: Any) -> str:
    if answer is None:
        return ""

    if isinstance(answer, str):
        return answer.strip()

    if isinstance(answer, (dict, list)):
        return json.dumps(answer, indent=2, default=str)

    return str(answer).strip()


def format_pipeline_response(
    response: dict,
    *,
    query: str | None = None,
    analysis_context: dict | None = None,
    default_response_type: str = "analytical-answer",
    default_reason: str = "Normalized by formatting agent",
) -> dict:
    """
    Format the pipeline output using an LLM that calls explicit layout tools.
    """
    formatted_answer = _stringify_answer(response.get("formatted_answer"))
    
    # Check if a layout was already hardcoded upstream (e.g. error)
    hardcoded_layout = (response.get("layout") or "").upper().strip()
    
    # If the caller explicitly gave us a layout, they don't need the LLM 
    # to invent a header or explanation. Return exactly what was requested.
    if hardcoded_layout:
        return {
            "response_type": response.get("response_type", default_response_type),
            "layout": hardcoded_layout,
            "format_reason": "Layout hardcoded by upstream pipeline",
            "formatted_answer": formatted_answer
        }

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.7,
        thinking_budget=512,
        include_thoughts=True,
    )
    llm_with_tools = llm.bind_tools(FORMATTING_TOOLS)

    execution_trace = response.get("execution_trace", "No trace provided.")
    step_results = response.get("step_results", {})

    # Inject context the formatter needs: query, execution trace, and data
    analysis_str = f"- Analysis Context:\n{json.dumps(analysis_context, indent=2)}\n" if analysis_context else ""
    human_content = (
        "Context for layout selection and explanation:\n"
        f"- Original user query: {query or 'None'}\n"
        f"{analysis_str}"
        f"- Execution Trace:\n{execution_trace}\n"
        f"- Step Results Data:\n{json.dumps(step_results, indent=2, default=str)}\n"
    )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=human_content),
    ]

    # Default fallback
    chosen_layout = "PLAIN_TEXT"
    chosen_response_type = default_response_type
    chosen_reason = default_reason
    chosen_explanation = ""

    try:
        # LLM analyzes and triggers a tool
        logger.info("[FORMATTING AGENT] Analyzing text to trigger a layout tool...")
        llm_response = llm_with_tools.invoke(messages)
        
        if llm_response.tool_calls:
            tool_call = llm_response.tool_calls[0]
            tool_name = tool_call["name"]
            logger.info(f"[FORMATTING AGENT] Triggered layout tool: {tool_name}")
            args = tool_call.get("args", {})
            
            tool_dict = {t.name: t for t in FORMATTING_TOOLS}
            tool_func = tool_dict.get(tool_name)
            
            if tool_func:
                # Dynamically invoke the tool to get its specific layout and response_type
                result = tool_func.invoke(args)
                chosen_layout = result.get("layout", chosen_layout)
                chosen_response_type = result.get("response_type", chosen_response_type)
                chosen_reason = result.get("format_reason", chosen_reason)
                chosen_explanation = result.get("explanation", chosen_explanation)

            else:
                logger.warning(f"Formatting LLM called unknown tool: {tool_name}")
                chosen_reason = args.get("format_reason", chosen_reason)
                chosen_explanation = args.get("explanation", chosen_explanation)
        else:
            logger.warning("Formatting LLM returned without calling a tool. Using fallback.")

    except Exception as e:
        logger.error("Formatting LLM failed: %s. Falling back to default.", e)
        chosen_reason = f"Fallback: LLM failed to format ({e})"

    # Extract thought
    thought = ""
    try:
        # If we have llm_response from llm_with_tools
        if 'llm_response' in locals() and llm_response:
            ak = getattr(llm_response, "additional_kwargs", {})
            rm = getattr(llm_response, "response_metadata", {})
            content = getattr(llm_response, "content", None)
            
            if "thought" in ak:
                thought = str(ak["thought"])
            elif "thought" in rm:
                thought = str(rm["thought"])
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") in ("thought", "thinking"):
                        thought = str(part.get("text") or part.get("thought", ""))
                        break
                    elif isinstance(part, dict) and "thought" in part:
                        thought = str(part["thought"])
                        break
            elif isinstance(content, str) and content.strip():
                import re
                m = re.search(r'<thought>(.*?)</thought>', content, re.DOTALL)
                if m:
                    thought = m.group(1).strip()
    except Exception as e:
        logger.warning(f"Failed to extract thought: {e}")

    return {
        "response_type": chosen_response_type,
        "layout": chosen_layout,
        "format_reason": chosen_reason,
        "explanation": chosen_explanation,
        "formatted_answer": formatted_answer,
        "thought": thought
    }
