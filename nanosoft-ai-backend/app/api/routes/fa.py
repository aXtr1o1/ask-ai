from fastapi import APIRouter, HTTPException
import logging
import json
 
from app.api.models.schemas import FARequest
from app.api.database.postgres_client import get_pool
 
router = APIRouter()
 
logger = logging.getLogger("fa_route")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)
 
 
def format_response(data):
    if isinstance(data, dict):
        p_list  = data.get("p_list", [])
        p_count = data.get("p_count", 0)
        logger.info("📊 FA format_response | p_list_length=%s | p_count=%s", len(p_list), p_count)
        return {"p_list": p_list, "p_count": p_count}
    safe_list = data if isinstance(data, list) else []
    return {"p_list": safe_list, "p_count": len(safe_list)}
 
 
@router.post("/get-fa")
def get_fa(req: FARequest):
    logger.info(
        "📋 [GET-FA] Incoming | user_name=%s | limit=%s | offset=%s",
        req.user_name, req.limit, req.offset
    )
 
    # ── AGGREGATE PATH ──────────────────────────────────────────────────────
    if getattr(req, "is_aggregate", False) and req.group_by_columns:
        logger.info("📊 [GET-FA] AGGREGATE MODE → calling sp_fa_aggregate")
        try:
            conn   = get_pool()
            cursor = conn.cursor()
 
            group_by_str = ",".join(req.group_by_columns)
            agg_function = req.aggregate_function or "COUNT"
 
            logger.info("📊 [GET-FA] group_by=%s | function=%s", group_by_str, agg_function)
 
            cursor.callproc("sp_fa_aggregate", [
                req.user_name,
                req.user_id,
                req.division,
                req.building,
                req.floor,
                req.locality,
                req.priority,
                req.stage,
                req.category,
                req.frequency,
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
 
            formatted = format_response(raw)
            logger.info("✅ [GET-FA] Aggregate result | count=%s", formatted["p_count"])
            return formatted
 
        except Exception as e:
            logger.error("[GET-FA] Aggregate failed | error=%s", str(e), exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
 
    # ── NORMAL PATH ─────────────────────────────────────────────────────────
    logger.info("[GET-FA] Calling sp_fa_query")
    try:
        conn   = get_pool()
        cursor = conn.cursor()
 
        cursor.callproc("sp_fa_query", [
            req.user_name,
            req.user_id,
            req.complaint_no,
            req.priority,
            req.stage,
            req.category,
            req.category_sub,
            req.division,
            req.locality,
            req.building,
            req.floor,
            req.spot_name,
            req.contract,
            req.tech,
            req.frequency,
            req.request_desc,
            req.is_withdraw,
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
 
        formatted = format_response(raw)
        p_list = formatted.get("p_list", [])

        # Fallback interceptor: if 0 records found and locality was specified but spot_name was not,
        # retry the query mapping locality to spot_name.
        if not p_list and req.locality and not req.spot_name:
            logger.info("🔄 0 records found with locality='%s' in FA. Retrying query by mapping locality to spot_name...", req.locality)
            cursor = conn.cursor()
            cursor.callproc("sp_fa_query", [
                req.user_name,
                req.user_id,
                req.complaint_no,
                req.priority,
                req.stage,
                req.category,
                req.category_sub,
                req.division,
                None,  # p_locality cleared
                req.building,
                req.floor,
                req.locality,  # p_spot_name mapped
                req.contract,
                req.tech,
                req.frequency,
                req.request_desc,
                req.is_withdraw,
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
            formatted = format_response(raw)
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
                candidates = []
                val = " ".join(original_val.strip().split())
                no_dash = val.replace("-", " ")
                with_dash = val.replace(" ", "-")
                
                for text_val in [val, no_dash, with_dash]:
                    cleaned = " ".join(text_val.split())
                    candidates.append(cleaned)
                    words = cleaned.split()
                    if len(words) > 2:
                        candidates.append(" ".join(words[:2]))
                    if len(words) > 1:
                        w0, w1 = words[0], words[1]
                        is_generic_prefix = w1.isdigit() or len(w1) == 1
                        if not is_generic_prefix:
                            candidates.append(w0)
                
                seen = {original_val} if not is_keyword_mapping else set()
                unique_candidates = []
                for c in candidates:
                    if c and c not in seen:
                        seen.add(c)
                        unique_candidates.append(c)
                
                for candidate in unique_candidates:
                    logger.info(
                        "🔄 Retrying FA query mapping %s%s to candidate='%s'...",
                        "keyword to " if is_keyword_mapping else "",
                        field,
                        candidate
                    )
                    cursor = conn.cursor()
                    cursor.callproc("sp_fa_query", [
                        req.user_name,
                        req.user_id,
                        req.complaint_no,
                        req.priority,
                        req.stage,
                        req.category,
                        req.category_sub,
                        req.division,
                        candidate if field == "locality" else req.locality,
                        candidate if field == "building" else req.building,
                        req.floor,
                        candidate if field == "spot_name" else req.spot_name,
                        req.contract,
                        req.tech,
                        req.frequency,
                        req.request_desc,
                        req.is_withdraw,
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
                    formatted = format_response(raw_val)
                    p_list = formatted.get("p_list", [])
                    if p_list:
                        logger.info("✅ FA fallback retry succeeded with %s='%s'!", field, candidate)
                        formatted["fallback_applied"] = {"field": field, "value": candidate}
                        break
                if p_list:
                    break

        logger.info("[GET-FA] Fetched | count=%s", formatted["p_count"])
        return formatted
 
    except Exception as e:
        logger.error("[GET-FA] RPC failed | error=%s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))