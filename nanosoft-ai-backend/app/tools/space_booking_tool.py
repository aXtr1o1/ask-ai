import json
import logging
import asyncio
import requests
from typing import Optional
from langchain_core.tools import tool

from app.config import settings
from app.api.database.postgres_client import get_pool
from app.models.schemas import BookSpotInput, GetSpotsInput, GetBookingStatusInput

logger = logging.getLogger("space_booking_tool")
logger.setLevel(logging.INFO)



def _get_client_config_sync(user_name: str):
    conn = get_pool()
    if not conn:
        return None
    with conn.cursor() as cur:
        cur.execute("SELECT base_url, jwt_token FROM client_sync_config WHERE client_name = %s", (user_name,))
        row = cur.fetchone()
        if row:
            return {"base_url": row[0], "jwt_token": row[1]}
    return None


async def fetch_spots_api(user_name: str, search_term: Optional[str] = None) -> str:
    row = await asyncio.to_thread(_get_client_config_sync, user_name)
    if not row:
        return json.dumps({"error": f"Configuration not found for user {user_name}."})
    base_url = row['base_url'].rstrip('/')
    jwt_token = row['jwt_token']

    if base_url.endswith('askmeapi'):
        api_url = f"{base_url}/getSpot"
    else:
        api_url = f"{base_url}/askmeapi/getSpot"

    headers = {
        "x-auth": jwt_token,
        "userid": "101",
        "Content-Type": "application/json"
    }
    # Always fetch all spots then filter client-side (RAG-like)
    payload = {
        "SpotCode": None, "SpotName": None, "SpotNo": None,
        "SpotTypeCode": None, "SpotTypeName": None,
        "LocalityGroupCode": None, "LocalityGroupName": None,
        "CityCode": None, "CityName": None,
        "AdminLocalityTypeCode": None, "AdminLocalityTypeName": None,
        "LocalityCode": None, "LocalityName": None,
        "AssBuildingTypeCode": None, "AssBuildingTypeName": None,
        "BuildingCode": None, "BuildingName": None,
        "FloorCode": None, "FloorName": None,
        "AssWingCode": None, "AssWingName": None,
        "PageIndex": "1", "PageSize": "100",
        "Type": "SpotID", "UserGroupKey": "1", "UserAccessKey": "1"
    }

    logger.info(f"🚀 POST request to {api_url}")
    try:
        response = await asyncio.to_thread(
            requests.post, api_url, headers=headers, json=payload, timeout=15
        )
        if response.status_code == 200:
            json_resp = response.json()
            p_list = json_resp.get("data", [])

            # Fuzzy matching — handles spelling variations
            if search_term and str(search_term).strip():
                import re
                clean_search = re.sub(r'[^a-z0-9]', '', str(search_term).lower())
                fuzzy_matches = []
                for s in p_list:
                    b_name = re.sub(r'[^a-z0-9]', '', str(s.get("BuildingName", "")).lower())
                    s_code = re.sub(r'[^a-z0-9]', '', str(s.get("SpotCode", "")).lower())
                    s_name = re.sub(r'[^a-z0-9]', '', str(s.get("SpotName", "")).lower())
                    if clean_search in b_name or clean_search in s_code or clean_search in s_name:
                        fuzzy_matches.append(s)
                if fuzzy_matches:
                    p_list = fuzzy_matches

            total_count = len(p_list)
            logger.info(f"✅ Spots fetched: {total_count}")
            return json.dumps({"TotalCount": total_count, "p_list": p_list})
        else:
            logger.error(f"❌ API error: {response.text}")
            return json.dumps({"error": f"Error fetching spots (HTTP {response.status_code})"})

    except Exception as e:
        logger.error(f"❌ Error in API call: {e}", exc_info=True)
        return json.dumps({"error": str(e)})


@tool("GET_SPOTS", args_schema=GetSpotsInput)
async def GET_SPOTS(user_name: str, search_term: Optional[str] = None) -> str:
    """Fetch available spots by building name or spot code."""
    logger.info(f"🛠️ GET_SPOTS: user_name={user_name}, search_term={search_term}")
    return await fetch_spots_api(user_name, search_term)


def _fetch_booking_sync(booking_id: str, user_name: str) -> str:
    """Query space_bookings table for a given booking_id."""
    try:
        conn = get_pool()
        if not conn:
            return json.dumps({"error": "Database connection failed."})
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT booking_id, client_name, sub_user_name,
                       spot_code, spot_name, building_name, floor_name, timing
                FROM space_bookings
                WHERE booking_id = %s
                """,
                (booking_id,)
            )
            row = cur.fetchone()
            if row:
                return json.dumps({
                    "found": True,
                    "booking_id":    row[0],
                    "client_name":   row[1],
                    "sub_user_name": row[2],
                    "spot_code":     row[3],
                    "spot_name":     row[4],
                    "building_name": row[5],
                    "floor_name":    row[6],
                    "timing":        row[7],
                    "status":        "Confirmed"
                })
            else:
                return json.dumps({"found": False, "booking_id": booking_id})
    except Exception as e:
        logger.error(f"❌ Failed to fetch booking {booking_id}: {e}", exc_info=True)
        return json.dumps({"error": str(e)})


@tool("GET_BOOKING_STATUS", args_schema=GetBookingStatusInput)
async def GET_BOOKING_STATUS(user_name: str, booking_id: str) -> str:
    """Look up an existing booking by its 4-digit booking ID and return its status."""
    logger.info(f"🛠️ GET_BOOKING_STATUS: booking_id={booking_id}, user_name={user_name}")
    return await asyncio.to_thread(_fetch_booking_sync, booking_id, user_name)


def _insert_booking(booking_data: dict) -> str:
    import random
    booking_id = str(random.randint(1000, 9999))
    try:
        conn = get_pool()
        if not conn:
            return json.dumps({"error": "Database connection failed."})

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO space_bookings
                (booking_id, client_name, sub_user_name, spot_code, spot_name, building_name, floor_name, timing)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    booking_id,
                    booking_data.get("user_name"),
                    booking_data.get("sub_user_name", "user"),
                    booking_data.get("spot_code"),
                    booking_data.get("spot_name"),
                    booking_data.get("building_name"),
                    booking_data.get("floor_name"),
                    booking_data.get("timing")
                )
            )
            conn.commit()

        logger.info(f"✅ Booking saved. ID: {booking_id}")
        return json.dumps({
            "success": True,
            "booking_id": booking_id,
            "spot_code": booking_data.get("spot_code"),
            "spot_name": booking_data.get("spot_name"),
            "building_name": booking_data.get("building_name"),
            "floor_name": booking_data.get("floor_name"),
            "timing": booking_data.get("timing"),
        })
    except Exception as e:
        logger.error(f"❌ Failed to insert booking: {e}", exc_info=True)
        return json.dumps({"error": f"Failed to save booking: {e}"})


@tool("BOOK_SPOT", args_schema=BookSpotInput)
async def BOOK_SPOT(
    user_name: str,
    spot_code: str,
    spot_name: Optional[str] = "Unknown Spot",
    building_name: Optional[str] = "Unknown Building",
    floor_name: Optional[str] = "Unknown Floor",
    timing: Optional[str] = None,
    sub_user_name: Optional[str] = None
) -> str:
    """Book a space after the user has confirmed the spot and provided their preferred time."""
    logger.info(f"🛠️ BOOK_SPOT: spot_code={spot_code}, timing={timing}")

    if not timing or timing.strip() == "" or timing.lower() in ("none", "unknown"):
        return json.dumps({
            "error_type": "missing_time",
            "spot_code": spot_code,
            "building_name": building_name
        })

    booking_data = {
        "user_name": user_name,
        "sub_user_name": sub_user_name,
        "spot_code": spot_code,
        "spot_name": spot_name,
        "building_name": building_name,
        "floor_name": floor_name,
        "timing": timing
    }
    return await asyncio.to_thread(_insert_booking, booking_data)
