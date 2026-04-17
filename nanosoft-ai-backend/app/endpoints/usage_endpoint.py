"""
app/endpoints/usage_endpoint.py
─────────────────────────────────
Usage and health endpoints:
    GET /api/usage/{external_user_id}/{user_name} → fetch usage stats
    GET /api/health                                → health check
"""

import asyncio
import logging
from fastapi import APIRouter, HTTPException

from app.user.profile_service import get_user_usage_stats

logger = logging.getLogger("endpoints.usage")

router = APIRouter(tags=["usage"])


@router.get("/usage/{external_user_id}/{user_name}")
async def get_usage_stats(external_user_id: str, user_name: str):
    if not external_user_id or not user_name:
        raise HTTPException(status_code=400, detail="external_user_id and user_name are required")

    try:
        stats = await asyncio.to_thread(
            get_user_usage_stats,
            external_user_id.strip(),
            user_name.strip(),
        )
        if not stats:
            raise HTTPException(
                status_code=404,
                detail=f"No usage data found for user: {user_name}",
            )
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[USAGE] get_usage_stats failed | user=%s | error=%s",
            user_name, e,
        )
        raise HTTPException(status_code=500, detail="Failed to fetch usage stats")


@router.get("/health")
def api_health():
    return {"status": "ok", "service": "Facility Management AI Assistant"}