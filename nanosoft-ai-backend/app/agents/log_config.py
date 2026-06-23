"""
log_config.py — Shared logger factory for all pipeline agents.

Usage in any agent file:
    from app.agents.log_config import setup_agent_logger, extract_token_counts
    logger = setup_agent_logger("understanding_agent")

Each agent logger writes to:
  1. Console (stdout)                        — same as before
  2. logs/<agent_name>.log                   — ONE file PER AGENT (easy to debug)
  3. logs/agents.log                         — combined file (full pipeline trace)

Log files created per agent:
  logs/understanding_agent.log
  logs/goal_planning_agent.log
  logs/retrieval_agent.log
  logs/validation_agent.log
  logs/filtering_agent.log
  logs/execution_agent.log
  logs/multi_agent_graph.log
"""

import logging
import os
import datetime
from logging.handlers import RotatingFileHandler
from typing import Any

# ── Log directory ─────────────────────────────────────────────────────────────
_LOG_DIR       = os.path.join(os.path.dirname(__file__), "logs")
_COMBINED_FILE = os.path.join(_LOG_DIR, "agents.log")       # full pipeline trace
_LOG_FMT       = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

# Ensure logs/ directory exists
os.makedirs(_LOG_DIR, exist_ok=True)

# Cache of file handlers so we don't create duplicates
_file_handlers: dict = {}


def _get_file_handler(filepath: str) -> RotatingFileHandler:
    """Return (and lazily create) a rotating file handler for the given path."""
    if filepath not in _file_handlers:
        fh = RotatingFileHandler(
            filepath,
            maxBytes=5 * 1024 * 1024,  # 5 MB per file
            backupCount=3,
            encoding="utf-8",
        )
        fh.setFormatter(logging.Formatter(_LOG_FMT))
        fh.setLevel(logging.DEBUG)
        _file_handlers[filepath] = fh
    return _file_handlers[filepath]


def setup_agent_logger(name: str) -> logging.Logger:
    """
    Create and return a configured logger for an agent.

    Writes to:
      - Console (stdout, UTF-8)
      - logs/<name>.log        ← AGENT-SPECIFIC file  (easy debugging)
      - logs/agents.log        ← COMBINED file         (full pipeline view)

    Does NOT propagate to the root logger (avoids duplicate lines).
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        import sys

        # ── 1. Console handler ────────────────────────────────────────────────
        console_handler = logging.StreamHandler()
        console_handler.stream = open(
            sys.stdout.fileno(),
            mode="w",
            encoding="utf-8",
            buffering=1,
            closefd=False,
        )
        console_handler.setFormatter(logging.Formatter(_LOG_FMT))
        console_handler.setLevel(logging.DEBUG)
        logger.addHandler(console_handler)

        # ── 2. Agent-specific log file ────────────────────────────────────────
        agent_log_path = os.path.join(_LOG_DIR, f"{name}.log")
        logger.addHandler(_get_file_handler(agent_log_path))

        # ── 3. Combined log file (all agents together) ────────────────────────
        logger.addHandler(_get_file_handler(_COMBINED_FILE))

    logger.propagate = False
    return logger


def extract_token_counts(response: Any) -> dict:
    """
    Extract thinking / input / output token counts from a LangChain model response.

    WHY this lives here (not in each agent):
      All 6 pipeline agents call a Gemini model and need the same token-count
      extraction. Without this helper, every agent file contains the identical
      6-line block. Centralising it here means:
        - A single place to update if langchain_google_genai changes its API
        - No risk of one agent using a stale copy while another has the fix

    WHY the key is "reasoning" not "thinking_tokens":
      In langchain_google_genai >= 4.2.0 the thinking token count moved to:
        response.usage_metadata["output_token_details"]["reasoning"]
      The old key "thinking_tokens" no longer exists. This comment documents
      that intentional choice so no future developer changes it back.

    Returns:
        {"thinking": int, "input": int, "output": int}
        All values default to 0 if the metadata is missing or malformed.
    """
    counts = {"thinking": 0, "input": 0, "output": 0}
    usage = getattr(response, "usage_metadata", None)
    if usage and isinstance(usage, dict):
        counts["input"]  = usage.get("input_tokens", 0) or 0
        counts["output"] = usage.get("output_tokens", 0) or 0
        out_details = usage.get("output_token_details") or {}
        if isinstance(out_details, dict):
            counts["thinking"] = out_details.get("reasoning", 0) or 0
    return counts


def parse_llm_text(response: Any) -> str:
    """
    Extract the plain text content from a LangChain model response,
    skipping any thinking/reasoning parts emitted by Gemini thinking mode.

    WHY this lives here (not in each agent):
      All 6 agents call a Gemini model and need to extract the text part of
      the response. Gemini thinking mode returns a list of content blocks;
      some are type='thinking' (internal reasoning) and some are type='text'
      (the actual output). Each agent used an identical 8-line block to do
      this — centralising it removes the duplication.

    WHY we skip blocks where type == 'thinking':
      The thinking blocks contain raw chain-of-thought reasoning. Including
      them in the text would pollute JSON parsing (thinking blocks contain
      prose, not JSON) and inflate log output.

    Returns:
        The joined plain-text output as a stripped string.
    """
    raw = response.content
    if isinstance(raw, list):
        parts = [
            p.get("text", "") if isinstance(p, dict) else str(p)
            for p in raw
            if not (isinstance(p, dict) and p.get("type") == "thinking")
        ]
        return "".join(parts).strip()
    return str(raw).strip()


def strip_json_fences(text: str) -> str:
    """
    Remove markdown code fences from a string so it can be parsed as JSON.

    WHY this lives here (not in each agent):
      Gemini sometimes wraps its JSON output in ```json ... ``` even when the
      prompt says "no markdown". Every agent that parses JSON from the LLM
      needs to strip these fences. Centralising avoids the identical 5-line
      block being duplicated across 5 agent files.

    Handles:
      ```json\\n{...}\\n```
      ```\\n{...}\\n```
      {... } (already clean — returned as-is)
    """
    t = text.strip()
    if t.startswith("```"):
        t = t[3:]                      # strip opening ```
        if t.startswith("json"):
            t = t[4:]                  # strip optional 'json' language tag
        if t.endswith("```"):
            t = t[:-3]                 # strip closing ```
    return t.strip()


def write_session_separator(label: str = "SESSION START") -> None:

    """
    Write a visible session separator to BOTH the combined log AND all
    existing per-agent logs. Called once at the start of each pipeline run.
    """
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = (
        f"\n{'=' * 70}\n"
        f"  {label}  |  {ts}\n"
        f"{'=' * 70}\n"
    )

    # Write to combined file
    combined_fh = _get_file_handler(_COMBINED_FILE)
    combined_fh.stream.write(separator)
    combined_fh.stream.flush()

    # Write to each per-agent file that already exists
    for filepath, fh in _file_handlers.items():
        if filepath != _COMBINED_FILE:
            fh.stream.write(separator)
            fh.stream.flush()
