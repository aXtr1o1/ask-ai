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


def fuzzy_filter_spots(search_term: str, p_list: list) -> list:
    if not search_term or not str(search_term).strip():
        return p_list

    clean_term = str(search_term).strip().lower()

    # 1. Exact match on SpotCode (highest priority)
    exact_matches = [s for s in p_list if str(s.get("SpotCode", "")).strip().lower() == clean_term]
    if exact_matches:
        return exact_matches
        
    # 2. Exact match on SpotName
    exact_names = [s for s in p_list if str(s.get("SpotName", "")).strip().lower() == clean_term]
    if exact_names:
        return exact_names

    import re
    from difflib import SequenceMatcher

    def tokenize(text):
        cleaned = re.sub(r'[^a-z0-9\s]', ' ', str(text).lower())
        return [w for w in cleaned.split() if w]

    q_tokens = tokenize(clean_term)
    if not q_tokens:
        return p_list

    fuzzy_matches = []
    for s in p_list:
        def get_val(s_dict, key):
            for k, v in s_dict.items():
                if k.lower() == key.lower() and v:
                    return str(v)
            return ''

        combined_target = f"{get_val(s, 'BuildingName')} {get_val(s, 'SpotCode')} {get_val(s, 'SpotName')} {get_val(s, 'FloorName')}"
        t_tokens = tokenize(combined_target)

        if not t_tokens:
            continue

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
                    # Penalize short substrings (like "b" matching "labour")
                    if len(qw) <= 2:
                        best_sub = max(best_sub, 0.3)
                    else:
                        best_sub = max(best_sub, min(len(qw), len(tw)) / max(len(qw), len(tw)))
                else:
                    best_sub = max(best_sub, SequenceMatcher(None, qw, tw).ratio())
            sub_ratios.append(best_sub)

        avg_sub_ratio = sum(sub_ratios) / len(sub_ratios) if sub_ratios else 0.0
        similarity_score = max(token_ratio, avg_sub_ratio)
        
        # 100% Guarantee: If the search term is an exact substring, force max score
        if clean_term in combined_target.lower().replace(" ", ""):
            similarity_score = 1.0
            
        # Unified threshold to prevent silently dropping valid 2-letter acronyms
        threshold = 0.60
        if similarity_score >= threshold:
            fuzzy_matches.append((similarity_score, s))

    fuzzy_matches.sort(key=lambda x: x[0], reverse=True)
    return [match[1] for match in fuzzy_matches]


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

            # Apply robust fuzzy matching logic
            p_list = fuzzy_filter_spots(search_term, p_list)

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
    """Query space_bookings table for a given booking_id, or all bookings if ID is empty."""
    try:
        conn = get_pool()
        if not conn:
            return json.dumps({"error": "Database connection failed."})
        with conn.cursor() as cur:
            if booking_id:
                cur.execute(
                    """
                    SELECT booking_id, client_name, sub_user_name,
                           spot_code, spot_name, building_name, floor_name, start_time, end_time
                    FROM space_bookings
                    WHERE booking_id = %s AND client_name = %s
                    """,
                    (booking_id, user_name)
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
            else:
                from datetime import datetime
                current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cur.execute(
                    """
                    SELECT booking_id, client_name, sub_user_name,
                           spot_code, spot_name, building_name, floor_name, start_time, end_time
                    FROM space_bookings
                    WHERE client_name = %s AND end_time >= %s
                    ORDER BY start_time ASC
                    """,
                    (user_name, current_time_str)
                )
                rows = cur.fetchall()
                bookings = []
                for row in rows:
                    bookings.append({
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
                return json.dumps({"found": True, "bookings": bookings, "total": len(bookings)})
    except Exception as e:
        logger.error(f"❌ Failed to fetch booking(s): {e}", exc_info=True)
        return json.dumps({"error": str(e)})


@tool("GET_BOOKING_STATUS", args_schema=GetBookingStatusInput)
async def GET_BOOKING_STATUS(user_name: str, booking_id: Optional[str] = None) -> str:
    """Look up an existing booking by its 4-digit booking ID, or list all bookings if no ID is provided."""
    booking_id_val = str(booking_id).strip() if booking_id else ""
    logger.info(f"🛠️ GET_BOOKING_STATUS: booking_id={booking_id_val}, user_name={user_name}")
    return await asyncio.to_thread(_fetch_booking_sync, booking_id_val, user_name)


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
                WHERE client_name = %s 
                  AND spot_code = %s
                  AND (start_time < %s)
                  AND (end_time > %s)
                """,
                (
                    booking_data.get("user_name"),
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
                    "error": f"The spot is already booked from {overlap[1]} to {overlap[2]}. Please choose a different spot or select another time range."
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
    start_time: str,
    end_time: str,
    spot_name: Optional[str] = "Unknown Spot",
    building_name: Optional[str] = "Unknown Building",
    floor_name: Optional[str] = "Unknown Floor",
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
    start_dt = None
    end_dt = None
    try:
        from datetime import datetime
        cleaned_time_str = start_time.strip()
        
        # Try multiple common formats including DD/MM/YYYY
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %I:%M %p",
            "%Y-%m-%d %I:%M%p",
            "%Y-%m-%d %I %p",
            "%Y-%m-%d %I%p",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y %I:%M %p",
            "%d/%m/%Y %I:%M%p",
            "%d/%m/%Y %I %p",
            "%d/%m/%Y %I%p",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y %I:%M %p",
            "%m/%d/%Y %I:%M%p",
            "%m/%d/%Y %I %p",
            "%m/%d/%Y %I%p",
        ]
        for fmt in formats:
            try:
                start_dt = datetime.strptime(cleaned_time_str, fmt)
                break
            except ValueError:
                continue
        
        if start_dt is None:
            start_dt = datetime.fromisoformat(cleaned_time_str)
            
        # India Time is UTC+5:30. timedelta avoids ZoneInfo KeyError on Windows (no tzdata).
        from datetime import timezone, timedelta
        now_naive = (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).replace(tzinfo=None)
        if start_dt < now_naive:
            logger.warning(f"⚠️ BOOK_SPOT: Blocked booking for past date/time: {start_time}")
            return json.dumps({
                "success": False,
                "error": "You cannot create a booking for a past date. Please select a present or future date."
            })
            
        if end_time and end_time.strip() and end_time.lower() not in ("none", "unknown"):
            # Full datetime formats (do NOT strip spaces — they are part of "YYYY-MM-DD HH:MM")
            for fmt in formats:
                try:
                    end_dt = datetime.strptime(end_time.strip(), fmt)
                    break
                except ValueError:
                    continue
            
            # Time-only formats (use cleaned of spaces for patterns like "10:00AM")
            if end_dt is None:
                cleaned_end_time_str = end_time.strip().replace(" ", "")
                time_formats = ["%I:%M%p", "%H:%M", "%H:%M:%S", "%I%p"]
                for t_fmt in time_formats:
                    try:
                        parsed_t = datetime.strptime(cleaned_end_time_str, t_fmt).time()
                        end_dt = datetime.combine(start_dt.date(), parsed_t)
                        break
                    except ValueError:
                        continue

            if end_dt is None:
                try:
                    end_dt = datetime.fromisoformat(end_time.strip())
                except ValueError:
                    pass
        
        if end_dt is None:
            logger.warning(f"⚠️ BOOK_SPOT: Could not parse end_time '{end_time}', rejecting booking")
            return json.dumps({
                "error_type": "missing_time",
                "spot_code": spot_code,
                "building_name": building_name,
                "message": "Could not determine the end time. Please use the calendar to select a valid end time."
            })
            
        # Reject if end is before or equal to start — do NOT silently swap
        if end_dt <= start_dt:
            return json.dumps({
                "success": False,
                "error": "The end time must be after the start time. Please select a valid time range."
            })
            
        import os
        min_duration_str = os.getenv("MIN_BOOKING_DURATION_MINUTES", "15")
        try:
            min_duration = int(min_duration_str)
        except ValueError:
            min_duration = 15
            
        # Enforce minimum booking duration dynamically
        duration_minutes = (end_dt - start_dt).total_seconds() / 60
        if duration_minutes < min_duration:
            return json.dumps({
                "success": False,
                "error": f"Bookings must be for a minimum duration of {min_duration} minutes. Please select a longer time range."
            })
            
        standard_start_time = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        standard_end_time = end_dt.strftime("%Y-%m-%d %H:%M:%S")
            
    except Exception as e:
        logger.error(f"Failed to parse or validate start_time '{start_time}': {e}")
        return json.dumps({
            "success": False,
            "error": "You cannot create a booking for a past date. Please select a present or future date."
        })

    booking_data = {
        "user_name": user_name,
        "sub_user_name": sub_user_name,
        "spot_code": spot_code,
        "spot_name": spot_name,
        "building_name": building_name,
        "floor_name": floor_name,
        "start_time": standard_start_time,
        "end_time": standard_end_time,
    }
    return await asyncio.to_thread(_insert_booking, booking_data)




