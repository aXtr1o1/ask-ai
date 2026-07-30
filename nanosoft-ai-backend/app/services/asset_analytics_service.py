"""
Asset Analytics Service
Fetches asset history and lifecycle data from two external API endpoints
using credentials stored in the client_sync_config database table.
"""
import logging
import asyncio
import requests
from app.services.common_service import get_client_config_sync

logger = logging.getLogger("asset_analytics_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(ch)


# ℹ️  get_client_config_sync is imported from common_service — no local copy needed.


def _build_api_url(base_url: str, endpoint_path: str) -> str:
    """Build the full API URL, handling both base_url formats."""
    base = base_url.rstrip("/")
    if base.endswith("askmeapi"):
        # base_url already ends with /askmeapi  → strip suffix then append
        base_root = base[: -len("askmeapi")].rstrip("/")
        return f"{base_root}/askmeapi/{endpoint_path.lstrip('/')}"
    else:
        return f"{base}/askmeapi/{endpoint_path.lstrip('/')}"


def _call_asset_api(api_url: str, headers: dict, payload: dict) -> dict:
    """Make a POST request to the external asset API."""
    logger.info("🚀 POST %s | payload=%s", api_url, payload)
    try:
        resp = requests.post(api_url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        logger.error("❌ HTTP error calling %s: %s", api_url, e)
        return {"error": f"HTTP {resp.status_code}: {str(e)}"}
    except requests.exceptions.ConnectionError as e:
        logger.error("❌ Connection error calling %s: %s", api_url, e)
        return {"error": f"Connection error: {str(e)}"}
    except requests.exceptions.Timeout:
        logger.error("❌ Timeout calling %s", api_url)
        return {"error": "Request timed out"}
    except Exception as e:
        logger.error("❌ Unexpected error calling %s: %s", api_url, e)
        return {"error": str(e)}


async def fetch_asset_analytics(barcode: str, user_name: str) -> dict:
    """
    Fetch data from both asset analytics endpoints concurrently.

    Returns a dict with:
      - history: data from /askmeapi/AssetHistoryCard
      - lifecycle: data from /askmeapi/AssetLifeCycle
      - error: top-level error string if config is missing
    """
    # 1. Get client configuration from the database
    config = await asyncio.to_thread(get_client_config_sync, user_name)
    if not config:
        logger.error("❌ No config found for user: %s", user_name)
        return {"error": f"Configuration not found for client '{user_name}'."}

    base_url  = config["base_url"]
    jwt_token = config["jwt_token"]
    user_id   = config["user_id"]

    # 2. Build endpoint URLs
    history_url   = _build_api_url(base_url, "AssetHistoryCard")
    lifecycle_url = _build_api_url(base_url, "AssetLifeCycle")

    # 3. Build headers and request body
    headers = {
        "x-auth": jwt_token,
        "userid": user_id,
        "Content-Type": "application/json",
    }
    payload = {
        "BarcodeNo": barcode,
        "UserID": user_id,
    }

    logger.info(
        "🔍 Fetching asset analytics | user=%s | barcode=%s | history_url=%s | lifecycle_url=%s",
        user_name, barcode, history_url, lifecycle_url
    )

    # 4. Call both endpoints concurrently via asyncio threads
    history_result, lifecycle_result = await asyncio.gather(
        asyncio.to_thread(_call_asset_api, history_url,   headers, payload),
        asyncio.to_thread(_call_asset_api, lifecycle_url, headers, payload),
    )

    # Check if the asset was actually found
    history_output = history_result.get("Output", {})
    history_data = history_output.get("data", [])
    
    # Check if we have at least one array with at least one item
    has_asset_data = False
    if history_data and isinstance(history_data, list) and len(history_data) > 0:
        if isinstance(history_data[0], list) and len(history_data[0]) > 0:
            has_asset_data = True

    if not has_asset_data:
        # Check if the API returned an explicit error status, otherwise generic "not found"
        status_msg = history_output.get("status", {}).get("message", "No asset found with the given barcode number.")
        if status_msg.lower() == "success" or not status_msg:
            status_msg = "No asset found with the given barcode number."
        
        logger.warning("⚠️ Asset not found for barcode=%s. Returning error: %s", barcode, status_msg)
        return {
            "error": status_msg,
            "history": history_result,
            "lifecycle": lifecycle_result
        }

    logger.info("✅ Asset analytics fetch complete | user=%s | barcode=%s", user_name, barcode)

    return {
        "history":   history_result,
        "lifecycle": lifecycle_result,
    }
