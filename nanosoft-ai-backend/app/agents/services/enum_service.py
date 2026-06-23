"""
app/agents/services/enum_service.py
-------------------------------------
Fetches actual distinct filter values from the DB for each facility module
and formats them as a text block for injection into the Retrieval Agent prompt.

WHY this service exists:
  The Retrieval Agent prompt must tell the LLM which exact strings are valid
  for filters (status, priority, stage, frequency, etc.). These values must
  match the DB exactly — the stored procedure does a string match.
  Fetching DISTINCT values live from the DB means no drift, no hardcoding.

WHY it lives in app/agents/services/ (not app/services/):
  Only the Retrieval Agent uses this. Agent-specific helpers live here,
  not in the global app/services/ folder.

HOW caching works:
  Values load once (lazy, on first get_enum_prompt_block() call).
  To refresh without restarting: call load_db_enums() again.

TABLE MAPPING (verified against actual DB schema):
  BDM          → public.bdm
  PPM          → public.ppm
  ASSETS       → public."Asset"   (quoted — mixed case table name)
  FA           → public."FacilityAudit"
  SB (SB/SB)   → public."ScheduleBased"
"""

import logging
from typing import Dict, List

from app.agents.log_config import setup_agent_logger

logger = setup_agent_logger("enum_service")

# Module-level cache — populated on first call to get_enum_prompt_block()
_ENUM_CACHE: Dict[str, List[str]] = {}
_LOADED = False


# ---------------------------------------------------------------------------
# SQL queries — verified against actual DB tables and column names
# ---------------------------------------------------------------------------
# WHY quoted table names ("Asset", "FacilityAudit", "ScheduleBased"):
#   PostgreSQL folds unquoted identifiers to lowercase. These tables were
#   created with mixed-case names, so they must be double-quoted in SQL.
#
# WHY one query per key:
#   Each module has its own table and its own valid values.
#   One query per key = independently debuggable, independently failable.
#   If one table is empty or missing, only that key is affected.

_QUERIES: Dict[str, str] = {
    # BDM table: public.bdm
    "bdm_status":         'SELECT DISTINCT "WoStatus"          FROM bdm            WHERE "WoStatus" IS NOT NULL          ORDER BY 1',
    "bdm_priority":       'SELECT DISTINCT "PriorityName"      FROM bdm            WHERE "PriorityName" IS NOT NULL      ORDER BY 1',
    "bdm_stage":          'SELECT DISTINCT "StageName"         FROM bdm            WHERE "StageName" IS NOT NULL         ORDER BY 1',
    "bdm_complaint_type": 'SELECT DISTINCT "ComplaintTypeName" FROM bdm            WHERE "ComplaintTypeName" IS NOT NULL  ORDER BY 1',
    "bdm_complaint_mode": 'SELECT DISTINCT "ComplaintModeName" FROM bdm            WHERE "ComplaintModeName" IS NOT NULL  ORDER BY 1',

    # PPM table: public.ppm
    "ppm_status":         'SELECT DISTINCT "PPMStatus"         FROM ppm            WHERE "PPMStatus" IS NOT NULL         ORDER BY 1',
    "ppm_stage":          'SELECT DISTINCT "PPMStageName"      FROM ppm            WHERE "PPMStageName" IS NOT NULL      ORDER BY 1',
    "ppm_frequency":      'SELECT DISTINCT "FrequencyName"     FROM ppm            WHERE "FrequencyName" IS NOT NULL     ORDER BY 1',

    # ASSETS table: public."Asset"  (mixed-case — must be quoted)
    "asset_status":       'SELECT DISTINCT "StatusName"        FROM "Asset"        WHERE "StatusName" IS NOT NULL        ORDER BY 1',
    "asset_priority":     'SELECT DISTINCT "PriorityName"      FROM "Asset"        WHERE "PriorityName" IS NOT NULL      ORDER BY 1',
    "asset_condition":    'SELECT DISTINCT "ConditionName"     FROM "Asset"        WHERE "ConditionName" IS NOT NULL     ORDER BY 1',

    # FA table: public."FacilityAudit"  (mixed-case — must be quoted)
    "fa_stage":           'SELECT DISTINCT "RMStageName"       FROM "FacilityAudit" WHERE "RMStageName" IS NOT NULL      ORDER BY 1',

    # SB table: public."ScheduleBased"  (mixed-case — must be quoted)
    "sb_stage":           'SELECT DISTINCT "PPMStageName"      FROM "ScheduleBased" WHERE "PPMStageName" IS NOT NULL     ORDER BY 1',
}


def load_db_enums() -> None:
    """
    Fetch all enum values from the DB and populate _ENUM_CACHE.
    Called lazily on first get_enum_prompt_block() call.

    WHY per-query error handling:
      A failed query logs a warning and stores an empty list for that key.
      The rest of the keys still load. An empty key shows "(not available)"
      in the prompt so the model knows there are no values for that field.
    """
    global _LOADED
    from app.api.database.postgres_client import get_pool

    try:
        conn = get_pool()
    except Exception as e:
        logger.error("|| enum_service: DB connection failed — enum values unavailable | %s", e)
        _LOADED = True
        return

    loaded = 0
    for key, sql in _QUERIES.items():
        try:
            conn.rollback()
            with conn.cursor() as cur:
                cur.execute(sql)
                _ENUM_CACHE[key] = [row[0] for row in cur.fetchall() if row[0]]
            loaded += 1
        except Exception as e:
            logger.warning("|| enum_service: '%s' query failed | %s", key, e)
            _ENUM_CACHE[key] = []
        conn.rollback()

    _LOADED = True
    logger.info("|| enum_service: loaded %d/%d enum keys from DB", loaded, len(_QUERIES))


def _fmt(values: List[str]) -> str:
    """Format a list as a quoted pipe-separated string for the LLM prompt."""
    return "  |  ".join(f'"{v}"' for v in values) if values else "(not available)"


def get_enum_prompt_block() -> str:
    """
    Return the formatted enum block for the Retrieval Agent system prompt.
    Lazy-loads from DB on first call, then returns cached values.
    """
    if not _LOADED:
        load_db_enums()

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "VALID FILTER VALUES — LIVE FROM DB — USE ONLY THESE EXACT STRINGS",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"BDM  status         : {_fmt(_ENUM_CACHE.get('bdm_status', []))}",
        f"BDM  priority       : {_fmt(_ENUM_CACHE.get('bdm_priority', []))}",
        f"BDM  stage          : {_fmt(_ENUM_CACHE.get('bdm_stage', []))}",
        f"BDM  complaint_type : {_fmt(_ENUM_CACHE.get('bdm_complaint_type', []))}",
        f"BDM  complaint_mode : {_fmt(_ENUM_CACHE.get('bdm_complaint_mode', []))}",
        "",
        f"PPM  status         : {_fmt(_ENUM_CACHE.get('ppm_status', []))}",
        f"PPM  stage          : {_fmt(_ENUM_CACHE.get('ppm_stage', []))}",
        f"PPM  frequency      : {_fmt(_ENUM_CACHE.get('ppm_frequency', []))}",
        "",
        f"ASSETS status       : {_fmt(_ENUM_CACHE.get('asset_status', []))}",
        f"ASSETS priority     : {_fmt(_ENUM_CACHE.get('asset_priority', []))}",
        f"ASSETS condition    : {_fmt(_ENUM_CACHE.get('asset_condition', []))}",
        "",
        f"FA   stage          : {_fmt(_ENUM_CACHE.get('fa_stage', []))}",
        f"SB   stage          : {_fmt(_ENUM_CACHE.get('sb_stage', []))}",
        "",
        "RULE: The stored procedure does an EXACT string match.",
        "      Pick the closest value from the lists above — never paraphrase or invent.",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    return "\n".join(lines)
