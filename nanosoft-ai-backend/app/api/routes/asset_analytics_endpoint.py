"""
Asset Analytics API Endpoint
Provides a REST endpoint to fetch combined asset history and lifecycle data.
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.asset_analytics_service import fetch_asset_analytics

logger = logging.getLogger("asset_analytics_endpoint")
logger.setLevel(logging.INFO)

asset_analytics_router = APIRouter()


class AssetAnalyticsRequest(BaseModel):
    barcode: str
    userName: str


@asset_analytics_router.post("/asset-analytics")
async def asset_analytics_endpoint(request: AssetAnalyticsRequest):
    """
    Fetch combined asset analytics data for a given asset barcode / asset tag.
    Calls both /askmeapi/AssetHistoryCard and /askmeapi/AssetLifeCycle concurrently.
    """
    barcode   = request.barcode.strip()
    user_name = request.userName.strip()

    if not barcode:
        raise HTTPException(status_code=400, detail="barcode is required")

    if not user_name:
        raise HTTPException(status_code=400, detail="userName is required")

    logger.info("📊 Asset analytics request | user=%s | barcode=%s", user_name, barcode)

    result = await fetch_asset_analytics(barcode=barcode, user_name=user_name)

    if "error" in result and len(result) == 1:
        raise HTTPException(status_code=503, detail=result["error"])

    return result
