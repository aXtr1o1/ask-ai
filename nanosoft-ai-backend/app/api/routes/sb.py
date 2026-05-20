from fastapi import APIRouter, HTTPException
import logging
import json
import difflib
 
from app.api.models.schemas import SBRequest
from app.api.database.postgres_client import get_pool
from .utils import generate_fallback_candidates

router_sb = APIRouter()
 
logger_sb = logging.getLogger("sb_route")
logger_sb.setLevel(logging.INFO)
ch2 = logging.StreamHandler()
ch2.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger_sb.handlers:
    logger_sb.addHandler(ch2)
 
 
def format_response_sb(data):
    if isinstance(data, dict):
        p_list  = data.get("p_list", [])
        p_count = data.get("p_count", 0)
        logger_sb.info("📊 SB format_response | p_list_length=%s | p_count=%s", len(p_list), p_count)
        return {"p_list": p_list, "p_count": p_count}
    safe_list = data if isinstance(data, list) else []
    return {"p_list": safe_list, "p_count": len(safe_list)}


def get_db_candidates(conn, field: str) -> list:
    column_map = {
        "building": "BuildingName",
        "locality": "LocalityName",
        "spot_name": "SpotName"
    }
    col = column_map.get(field)
    if not col:
        return []
    try:
        cursor = conn.cursor()
        query = f'SELECT DISTINCT "{col}" FROM public."ScheduleBased" WHERE "{col}" IS NOT NULL AND "{col}" <> \'\''
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        return [row[0] for row in rows if row[0]]
    except Exception as e:
        logger_sb.error("Error fetching DB candidates for %s: %s", field, str(e))
        return []


def find_close_matches(original_val: str, db_vals: list) -> list:
    if not original_val or not db_vals:
        return []
    val_map = {v.lower(): v for v in db_vals if v}
    matches = difflib.get_close_matches(original_val.lower(), list(val_map.keys()), n=3, cutoff=0.5)
    return [val_map[m] for m in matches]
 
 
@router_sb.post("/get-sb")
def get_sb(req: SBRequest):
    logger_sb.info(
        "🗓️ [GET-SB] Incoming | user_name=%s | limit=%s | offset=%s",
        req.user_name, req.limit, req.offset
    )
 
    # ── AGGREGATE PATH ──────────────────────────────────────────────────────
    if getattr(req, "is_aggregate", False) and req.group_by_columns:
        logger_sb.info("📊 [GET-SB] AGGREGATE MODE → calling sp_sb_aggregate")
        try:
            conn   = get_pool()
            cursor = conn.cursor()
 
            group_by_str = ",".join(req.group_by_columns)
            agg_function = req.aggregate_function or "COUNT"
 
            logger_sb.info("📊 [GET-SB] group_by=%s | function=%s", group_by_str, agg_function)
 
            cursor.callproc("sp_sb_aggregate", [
                req.user_name,
                req.user_id,
                req.division,
                req.discipline,
                req.building,
                req.floor,
                req.locality,
                req.stage,
                req.frequency,
                req.service_type,
                req.date_from,
                req.date_to,
                group_by_str,
                agg_function,
            ])
 
            row = cursor.fetchone()
            cursor.close()
 
            raw = row[0] if row else {}
            if isinstance(raw, str):
                raw = json.loads(raw)
 
            formatted = format_response_sb(raw)
            logger_sb.info("✅ [GET-SB] Aggregate result | count=%s", formatted["p_count"])
            return formatted
 
        except Exception as e:
            logger_sb.error("[GET-SB] Aggregate failed | error=%s", str(e), exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
 
    # ── NORMAL PATH ─────────────────────────────────────────────────────────
    logger_sb.info("[GET-SB] Calling sp_sb_query")
    try:
        conn   = get_pool()
        cursor = conn.cursor()
 
        cursor.callproc("sp_sb_query", [
            req.user_name,
            req.user_id,
            req.work_order,
            req.stage,
            req.division,
            req.discipline,
            req.locality,
            req.building,
            req.floor,
            req.spot_name,
            req.contract,
            req.frequency,
            req.service_type,
            req.tech,
            req.is_withdraw,
            req.is_reschedule,
            req.is_rework,
            req.is_active,
            req.keyword,
            req.date_from,
            req.date_to,
            req.comp_from,
            req.comp_to,
            req.limit,
            req.offset,
        ])
 
        row = cursor.fetchone()
        cursor.close()
 
        raw = row[0] if row else {}
        if isinstance(raw, str):
            raw = json.loads(raw)
 
        formatted = format_response_sb(raw)
        p_list = formatted.get("p_list", [])

        # Fallback interceptor: if 0 records found and locality was specified but spot_name was not,
        # retry the query mapping locality to spot_name.
        if not p_list and req.locality and not req.spot_name:
            logger_sb.info("🔄 0 records found with locality='%s' in SB. Retrying query by mapping locality to spot_name...", req.locality)
            cursor = conn.cursor()
            cursor.callproc("sp_sb_query", [
                req.user_name,
                req.user_id,
                req.work_order,
                req.stage,
                req.division,
                req.discipline,
                None,  # p_locality cleared
                req.building,
                req.floor,
                req.locality,  # p_spot_name mapped
                req.contract,
                req.frequency,
                req.service_type,
                req.tech,
                req.is_withdraw,
                req.is_reschedule,
                req.is_rework,
                req.is_active,
                req.keyword,
                req.date_from,
                req.date_to,
                req.comp_from,
                req.comp_to,
                req.limit,
                req.offset,
            ])
            row = cursor.fetchone()
            cursor.close()
            raw = row[0] if row else {}
            if isinstance(raw, str):
                raw = json.loads(raw)
            formatted = format_response_sb(raw)
            p_list = formatted.get("p_list", [])

        # Fallback 2: if 0 records found:
        # A) Try to simplify/trim any specified location filter (building, locality, spot_name).
        # B) Try mapping the keyword to location/entity fields (spot_name, building, locality),
        #    including simplifying/trimming the keyword value itself.
        if not p_list:
            fallback_items = []
            
            # Add specified location filters
            for field in ["building", "locality", "spot_name"]:
                original_val = getattr(req, field, None)
                if original_val:
                    fallback_items.append((field, original_val, False))
            
            # Add keyword mapping targets if keyword is provided
            if req.keyword:
                for field in ["spot_name", "building", "locality"]:
                    if not getattr(req, field, None):  # Only map to fields not already set
                        fallback_items.append((field, req.keyword, True))
            
            # Process each fallback item
            for field, original_val, is_keyword_mapping in fallback_items:
                unique_candidates = generate_fallback_candidates(original_val, is_keyword_mapping)
                
                # Fetch fuzzy candidates from DB values (only for actual location filters)
                if not is_keyword_mapping:
                    db_vals = get_db_candidates(conn, field)
                    fuzzy_matches = find_close_matches(original_val, db_vals)
                    for fm in fuzzy_matches:
                        if fm and fm not in unique_candidates and fm != original_val:
                            unique_candidates.append(fm)
                
                for candidate in unique_candidates:
                    logger_sb.info(
                        "🔄 Retrying SB query mapping %s%s to candidate='%s'...",
                        "keyword to " if is_keyword_mapping else "",
                        field,
                        candidate
                    )
                    cursor = conn.cursor()
                    cursor.callproc("sp_sb_query", [
                        req.user_name,
                        req.user_id,
                        req.work_order,
                        req.stage,
                        req.division,
                        req.discipline,
                        candidate if field == "locality" else req.locality,
                        candidate if field == "building" else req.building,
                        req.floor,
                        candidate if field == "spot_name" else req.spot_name,
                        req.contract,
                        req.frequency,
                        req.service_type,
                        req.tech,
                        req.is_withdraw,
                        req.is_reschedule,
                        req.is_rework,
                        req.is_active,
                        None if is_keyword_mapping else req.keyword,  # clear keyword if we map it
                        req.date_from,
                        req.date_to,
                        req.comp_from,
                        req.comp_to,
                        req.limit,
                        req.offset,
                    ])
                    row = cursor.fetchone()
                    cursor.close()
                    raw_val = row[0] if row else {}
                    if isinstance(raw_val, str):
                        raw_val = json.loads(raw_val)
                    formatted = format_response_sb(raw_val)
                    p_list = formatted.get("p_list", [])
                    if p_list:
                        logger_sb.info("✅ SB fallback retry succeeded with %s='%s'!", field, candidate)
                        formatted["fallback_applied"] = {"field": field, "value": candidate}
                        break
                if p_list:
                    break

        logger_sb.info("[GET-SB] Fetched | count=%s", formatted["p_count"])

        return formatted
 
    except Exception as e:
        logger_sb.error("[GET-SB] RPC failed | error=%s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))