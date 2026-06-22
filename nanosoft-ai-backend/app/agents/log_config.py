"""
log_config.py — Shared logger factory for all pipeline agents.

Usage in any agent file:
    from app.agents.log_config import setup_agent_logger
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
