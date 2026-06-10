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
        "PageIndex": "1", "PageSize": "5000",
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

            # Similarity-based fuzzy matching to handle typos and spelling variations dynamically without hardcoding
            if search_term and str(search_term).strip():
                import re
                from difflib import SequenceMatcher

                # Tokenize and normalize text helper
                def tokenize(text):
                    cleaned = re.sub(r'[^a-z0-9\s]', ' ', str(text).lower())
                    return [w for w in cleaned.split() if w]

                q_tokens = tokenize(search_term)

                fuzzy_matches = []
                for s in p_list:
                    # Combine target fields for matching (includes Building, Code, Name, and Floor)
                    combined_target = f"{s.get('BuildingName', '')} {s.get('SpotCode', '')} {s.get('SpotName', '')} {s.get('FloorName', '')}"
                    t_tokens = tokenize(combined_target)

                    if not q_tokens or not t_tokens:
                        continue

                    # 1. Token Set Ratio
                    intersection = set(q_tokens).intersection(set(t_tokens))
                    diff_q = set(q_tokens).difference(set(t_tokens))
                    diff_t = set(t_tokens).difference(set(q_tokens))

                    sorted_inter = sorted(list(intersection))
                    sorted_diff_q = sorted(list(diff_q))
                    sorted_diff_t = sorted(list(diff_t))

                    base_inter = " ".join(sorted_inter)
                    base_q = base_inter + " " + " ".join(sorted_diff_q) if sorted_diff_q else base_inter
                    base_t = base_inter + " " + " ".join(sorted_diff_t) if sorted_diff_t else base_inter

                    r1 = SequenceMatcher(None, base_q.strip(), base_t.strip()).ratio()
                    r2 = SequenceMatcher(None, base_inter.strip(), base_q.strip()).ratio()
                    r3 = SequenceMatcher(None, base_inter.strip(), base_t.strip()).ratio()
                    token_ratio = max(r1, r2, r3)

                    # 2. Substring / Typo matching ratio
                    sub_ratios = []
                    q_squished = "".join(q_tokens)
                    t_squished = "".join(t_tokens)
                    sub_ratios.append(SequenceMatcher(None, q_squished, t_squished).ratio())

                    for qw in q_tokens:
                        best_sub = 0.0
                        for tw in t_tokens:
                            if qw == tw:
                                best_sub = 1.0
                            elif qw in tw or tw in qw:
                                best_sub = max(best_sub, min(len(qw), len(tw)) / max(len(qw), len(tw)))
                            else:
                                # character-level similarity between individual words
                                best_sub = max(best_sub, SequenceMatcher(None, qw, tw).ratio())
                        sub_ratios.append(best_sub)

                    avg_sub_ratio = sum(sub_ratios) / len(sub_ratios) if sub_ratios else 0.0

                    # Overall similarity score
                    similarity_score = max(token_ratio, avg_sub_ratio)

                    # Include matching spot if it meets the similarity threshold of 0.60
                    if similarity_score >= 0.60:
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
                       spot_code, spot_name, building_name, floor_name, start_time, end_time
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
                    "start_time":    row[7],
                    "end_time":      row[8],
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
    # Guard: if the model passed a blank/None booking_id, return an actionable error
    if not booking_id or not str(booking_id).strip():
        logger.warning("⚠️ GET_BOOKING_STATUS called with empty booking_id")
        return json.dumps({
            "found": False,
            "error": "booking_id_missing",
            "message": "No booking ID was provided. Please ask the user to share their booking ID."
        })
    logger.info(f"🛠️ GET_BOOKING_STATUS: booking_id={booking_id}, user_name={user_name}")
    return await asyncio.to_thread(_fetch_booking_sync, str(booking_id).strip(), user_name)


def _insert_booking(booking_data: dict) -> str:
    import random
    booking_id = str(random.randint(1000, 9999))
    try:
        conn = get_pool()
        if not conn:
            return json.dumps({"error": "Database connection failed."})

        with conn.cursor() as cur:
            # ── Check for duplicate / overlapping booking ──
            cur.execute(
                """
                SELECT booking_id, start_time, end_time
                FROM space_bookings
                WHERE spot_code = %s
                  AND (start_time::timestamp < %s::timestamp)
                  AND (end_time::timestamp > %s::timestamp)
                """,
                (
                    booking_data.get("spot_code"),
                    booking_data.get("end_time"),
                    booking_data.get("start_time"),
                )
            )
            overlap = cur.fetchone()
            if overlap:
                logger.warning(f"⚠️ Booking clash: spot {booking_data.get('spot_code')} overlaps with booking {overlap[0]} ({overlap[1]} to {overlap[2]})")
                return json.dumps({
                    "success": False,
                    "error": f"The spot is already booked from {overlap[1]} to {overlap[2]} (Booking ID: {overlap[0]}). Please choose a different spot or select another time range."
                })

            cur.execute(
                """
                INSERT INTO space_bookings
                (booking_id, client_name, sub_user_name, spot_code, spot_name, building_name, floor_name, start_time, end_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    booking_id,
                    booking_data.get("user_name"),
                    booking_data.get("sub_user_name", "user"),
                    booking_data.get("spot_code"),
                    booking_data.get("spot_name"),
                    booking_data.get("building_name"),
                    booking_data.get("floor_name"),
                    booking_data.get("start_time"),
                    booking_data.get("end_time"),
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
            "start_time": booking_data.get("start_time"),
            "end_time": booking_data.get("end_time"),
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
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    sub_user_name: Optional[str] = None
) -> str:
    """Book a space after the user has confirmed the spot and provided their start and end time."""
    logger.info(f"🛠️ BOOK_SPOT: spot_code={spot_code}, start_time={start_time}, end_time={end_time}")

    if not start_time or start_time.strip() == "" or start_time.lower() in ("none", "unknown"):
        return json.dumps({
            "error_type": "missing_time",
            "spot_code": spot_code,
            "building_name": building_name
        })

    if start_time and end_time and start_time.strip() == end_time.strip():
        logger.warning(f"⚠️ BOOK_SPOT: start_time and end_time are identical: {start_time}")
        return json.dumps({
            "error": "The start and end times cannot be the same. Please use the calendar to select a valid time range."
        })

    # ── Check if start_time is in the past ──
    try:
        from datetime import datetime
        cleaned_time_str = start_time.strip()
        if len(cleaned_time_str) == 16:
            start_dt = datetime.strptime(cleaned_time_str, "%Y-%m-%d %H:%M")
        elif len(cleaned_time_str) == 19:
            start_dt = datetime.strptime(cleaned_time_str, "%Y-%m-%d %H:%M:%S")
        else:
            start_dt = datetime.fromisoformat(cleaned_time_str)
            
        now_naive = datetime.now()
        if start_dt < now_naive:
            logger.warning(f"⚠️ BOOK_SPOT: Blocked booking for past date/time: {start_time}")
            return json.dumps({
                "success": False,
                "error": f"Bookings for past dates or times are not permitted. Current server time is {now_naive.strftime('%Y-%m-%d %H:%M')}. Please select a current or future time."
            })
    except Exception as e:
        logger.error(f"Failed to parse or validate start_time '{start_time}': {e}")

    booking_data = {
        "user_name": user_name,
        "sub_user_name": sub_user_name,
        "spot_code": spot_code,
        "spot_name": spot_name,
        "building_name": building_name,
        "floor_name": floor_name,
        "start_time": start_time,
        "end_time": end_time or start_time,  # fallback: same as start if end not given
    }
    return await asyncio.to_thread(_insert_booking, booking_data)




