"""
dynamic/onboarding/routes/onboard_routes.py
────────────────────────────────────────────
Handles POST /api/client/onboard/service

Responsibility:
    Onboard ANY new client + service combination into the system.
    No hardcoding — everything is driven by the request payload.

3-Step Flow:
    Step 1 → Save client credentials     → client_registry
    Step 2 → Save service configuration  → client_service_registry
    Step 3 → Fetch + store all data      → client_service_data

After onboarding, the client can immediately start querying via the AI chatbot.
The dynamic tool builder and system prompt will auto-discover this new service.
"""

import logging
from fastapi import APIRouter, HTTPException

from app.dynamic.onboarding.schemas import OnboardServiceRequest
from app.dynamic.service import (
    get_conn,
    save_client_to_registry,
    save_service_to_registry,
    sync_service_data,
)

logger = logging.getLogger("dynamic.onboard_routes")

# ── Router — prefix matches the master router in __init__.py ─────────────────
router = APIRouter(prefix="/api/client", tags=["Dynamic Client - Onboarding"])


# ══════════════════════════════════════════════════════════════════════════════
# POST /onboard/service
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/onboard/service")
def onboard_service(req: OnboardServiceRequest):
    """
    Onboard ANY client + service. Completely dynamic — no hardcoding.

    What this endpoint does:
        1. Registers the client (name, token, base_url) in client_registry
        2. Registers the service config (fields, keywords, endpoint) in client_service_registry
        3. Fetches ALL records from the client's API and stores them in client_service_data

    After this endpoint succeeds:
        - The AI chatbot will auto-discover this service via the dynamic tool builder
        - The system prompt will include this service's routing keywords
        - Users can immediately query this service via the chatbot

    Example request body:
    {
        "client_name":  "poc",
        "user_id":      1,
        "base_url":     "https://poc.smartfm.cloud/askmeapi",
        "token":        "your_jwt_token",
        "service_key":  "assets",
        "service_name": "Asset Management",
        "description":  "Tracks physical equipment.",
        "endpoint":     "/getAssets",
        "unique_field": "AssetTagNo",
        "routing_keywords": ["asset", "equipment", "barcode"],
        "fields_config": {
            "DivisionName": { "type": "string",  "aggregatable": true,  "is_date": false },
            "PurDate":      { "type": "date",    "aggregatable": false, "is_date": true  }
        }
    }
    """
    logger.info(
        "🚀 [ONBOARD] Incoming request | client_name=%s | user_id=%s | service_key=%s | endpoint=%s",
        req.client_name, req.user_id, req.service_key, req.endpoint,
    )

    # Get a DB connection from the pool
    conn = get_conn()

    try:
        # ── STEP 1: Save client to client_registry ────────────────────────────
        # Upserts client credentials — safe to call multiple times
        logger.info("[ONBOARD] Step 1 → Saving client to client_registry | client_name=%s", req.client_name)
        save_client_to_registry(
            conn, req.client_name, req.token, req.base_url,
        )
        logger.info("[ONBOARD] ✅ Step 1 complete — client_registry updated | client_name=%s", req.client_name)

        # ── STEP 2: Save service config to client_service_registry ────────────
        # Convert FieldConfig Pydantic models → plain dicts for JSON storage
        fields_config_dict = {
            fname: fmeta.dict()
            for fname, fmeta in req.fields_config.items()
        }
        logger.info(
            "[ONBOARD] Step 2 → Saving service config | client_name=%s | service_key=%s | fields=%s",
            req.client_name, req.service_key, list(fields_config_dict.keys()),
        )
        save_service_to_registry(
            conn             = conn,
            client_name      = req.client_name,
            service_key      = req.service_key,
            service_name     = req.service_name,
            description      = req.description,
            routing_keywords = req.routing_keywords,
            fields_config    = fields_config_dict,
            endpoint         = req.endpoint,
            unique_field     = req.unique_field,
        )
        logger.info(
            "[ONBOARD] ✅ Step 2 complete — client_service_registry updated | service_key=%s",
            req.service_key,
        )

        # ── STEP 3: Fetch data from client API + store in client_service_data ─
        # Paginates through all pages and bulk inserts records as JSONB
        logger.info(
            "[ONBOARD] Step 3 → Fetching + storing data | url=%s%s",
            req.base_url, req.endpoint,
        )
        sync_summary = sync_service_data(
            conn         = conn,
            client_name  = req.client_name,
            user_id      = req.user_id,
            service_key  = req.service_key,
            base_url     = req.base_url,
            jwt_token    = req.token,
            endpoint     = req.endpoint,
            unique_field = req.unique_field,
        )
        logger.info(
            "[ONBOARD] ✅ Step 3 complete — data stored | inserted=%d | pages_fetched=%d",
            sync_summary["inserted"], sync_summary["pages_fetched"],
        )

        logger.info(
            "✅ [ONBOARD] All steps complete | client_name=%s | service_key=%s | total_records=%d",
            req.client_name, req.service_key, sync_summary["inserted"],
        )

        # Return summary so caller knows exactly what was done
        return {
            "status":           "success",
            "client_name":      req.client_name,
            "user_id":          req.user_id,
            "service_key":      req.service_key,
            "endpoint_called":  f"{req.base_url}{req.endpoint}",
            "records_inserted": sync_summary["inserted"],
            "pages_fetched":    sync_summary["pages_fetched"],
            "tables_populated": [
                "client_registry",
                "client_service_registry",
                "client_service_data",
            ],
            # Convenience URL to verify the inserted data
            "verify_url": f"/api/client/verify/{req.client_name}/{req.user_id}/{req.service_key}?limit=5",
        }

    except HTTPException:
        # Re-raise FastAPI HTTP exceptions without wrapping
        raise

    except Exception as e:
        logger.error(
            "❌ [ONBOARD] Failed | client_name=%s | service_key=%s | error=%s",
            req.client_name, req.service_key, e, exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e))