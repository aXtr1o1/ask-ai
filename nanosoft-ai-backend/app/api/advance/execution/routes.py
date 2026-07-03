"""
Execution — Routes

POST /run  →  Full pipeline:
  1. Look up question definition  (analysis/questions.py)
  2. Load + filter records        (retrieval/retrieval.py)
  3. Run LangGraph agent          (agent.py)
     → Agent sees: question + filter_fields metadata ONLY
     → Tools see:  filtered_records via state (never reaches LLM)
  4. Return result
"""
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.advance.analysis.questions import QUESTIONS
from app.api.advance.retrieval.retrieval import get_filtered_records
from app.api.advance.execution.agent import get_agent

router = APIRouter()
logger = logging.getLogger("advance.execution.routes")


# ── Schemas ────────────────────────────────────────────────────────────────
class RunRequest(BaseModel):
    question_id:   str                        # "Q1" or "Q2"
    filter_values: Optional[dict[str, Any]] = {}  # e.g. {"locality": "Doha", "division": "HVAC System"}


class RunResponse(BaseModel):
    status:       dict
    question_id:  str
    question:     str
    modules_used: list[str]
    filter_fields:dict
    filter_values:dict
    record_counts:dict[str, int]
    result:       dict
    error:        Optional[str] = None


# ── POST /run ─────────────────────────────────────────────────────────────
@router.post("/run", response_model=RunResponse)
def run_agent(req: RunRequest):
    """
    Run the FM Analytics Agent for a predefined question.

    Steps:
      1. Resolve question definition (modules + filter_fields)
      2. Load + filter data from retrieval JSONs
      3. Pass question + filter metadata → LangGraph agent (no data to LLM)
      4. Agent decides formula → calls math tool (tool reads data from state)
      5. Return computed result
    """
    # ── 1. Resolve question ───────────────────────────────────────────────
    q_def = QUESTIONS.get(req.question_id)
    if not q_def:
        raise HTTPException(
            status_code=404,
            detail=f"Question ID '{req.question_id}' not found. Available: {list(QUESTIONS.keys())}",
        )

    logger.info(
        "[EXEC] question_id=%s | filters=%s",
        req.question_id, req.filter_values,
    )

    # ── 2. Retrieval — filter data ────────────────────────────────────────
    filtered_records = get_filtered_records(
        modules=q_def["modules"],
        filter_fields=q_def["filter_fields"],
        filter_values=req.filter_values or {},
    )

    record_counts = {m: len(recs) for m, recs in filtered_records.items()}
    logger.info("[EXEC] record_counts=%s", record_counts)

    # ── 3. Build initial agent state ──────────────────────────────────────
    initial_state = {
        "messages":         [],
        "question":         q_def["question"],
        "modules":          q_def["modules"],            # tells agent which modules to use
        "filter_fields":    q_def["filter_fields"],     # metadata → goes to LLM
        "filtered_records": filtered_records,            # data     → stays in state, goes to tools
        "result":           {},
    }

    # ── 4. Run agent ──────────────────────────────────────────────────────
    try:
        agent = get_agent()
        final_state = agent.invoke(initial_state)
        result = final_state.get("result", {})
    except Exception as e:
        logger.error("[EXEC] Agent error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    # ── 5. Return ─────────────────────────────────────────────────────────
    return RunResponse(
        status={"code": 200, "message": "Success"},
        question_id=req.question_id,
        question=q_def["question"],
        modules_used=q_def["modules"],
        filter_fields=q_def["filter_fields"],
        filter_values=req.filter_values or {},
        record_counts=record_counts,
        result=result,
    )


# ── GET /questions ────────────────────────────────────────────────────────
@router.get("/questions")
def list_questions():
    """List all available questions with their modules and filter fields."""
    return {
        "status":    {"code": 200, "message": "Success"},
        "questions": [
            {
                "id":            q["id"],
                "question":      q["question"],
                "modules":       q["modules"],
                "filter_fields": list(q["filter_fields"].keys()),
            }
            for q in QUESTIONS.values()
        ],
    }


# ── GET /status ───────────────────────────────────────────────────────────
@router.get("/status")
def status():
    return {
        "status": {"code": 200, "message": "Success"},
        "module": "execution",
        "agent":  "LangGraph FM Analytics Agent",
        "ready":  True,
    }
