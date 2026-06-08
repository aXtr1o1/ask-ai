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


async def _fetch_all_spots_from_api(user_name: str) -> list:
    """
    Fetch ALL spot records from the API using pagination (PageSize=200).
    Uses the same fetching pattern as services/sync/fetcher.py.
    Returns a flat list of raw spot dicts.
    Called only when the vector store is not yet loaded for this client.
    """
    row = await asyncio.to_thread(_get_client_config_sync, user_name)
    if not row:
        logger.error(f"❌ No config found for '{user_name}' — cannot fetch spots")
        return []

    base_url  = row["base_url"].rstrip("/")
    jwt_token = row["jwt_token"]

    if base_url.endswith("askmeapi"):
        api_url = f"{base_url}/getSpot"
    else:
        api_url = f"{base_url}/askmeapi/getSpot"

    headers = {
        "x-auth":       jwt_token,
        "userid":       "101",
        "Content-Type": "application/json",
    }

    # Base payload — all filters null, only pagination changes per page
    base_payload = {
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
        "PageSize": "200",
        "Type": "SpotID", "UserGroupKey": "1", "UserAccessKey": "1",
    }

    all_spots  = []
    page_index = 1

    while True:
        payload = {**base_payload, "PageIndex": str(page_index)}
        logger.info(f"📄 Fetching spot page {page_index} from {api_url} ...")

        try:
            response = await asyncio.to_thread(
                requests.post, api_url, headers=headers, json=payload, timeout=30
            )
        except Exception as e:
            logger.error(f"❌ Network error fetching spot page {page_index}: {e}", exc_info=True)
            break

        if response.status_code != 200:
            logger.error(
                f"❌ Spot fetch page {page_index} returned HTTP {response.status_code}: "
                f"{response.text[:200]}"
            )
            break

        try:
            json_resp = response.json()
        except Exception as e:
            logger.error(f"❌ Invalid JSON on spot page {page_index}: {e}")
            break

        records = json_resp.get("data", [])
        if not records:
            logger.info(
                f"✅ Spot pagination complete at page {page_index} — "
                f"total fetched: {len(all_spots)}"
            )
            break

        all_spots.extend(records)
        logger.info(
            f"   Page {page_index} → {len(records)} records | running total: {len(all_spots)}"
        )

        # Early-exit: if TotalCount is embedded in records, use it
        total_count = records[0].get("TotalCount", 0) if records else 0
        if total_count and len(all_spots) >= int(total_count):
            logger.info(f"✅ All {total_count} spots fetched (TotalCount reached)")
            break

        page_index += 1

    return all_spots


async def fetch_spots_api(user_name: str, search_term: Optional[str] = None, list_buildings_only: bool = False) -> str:
    """
    Semantic spot search backed by an in-memory TF-IDF vector store.

    Lifecycle:
      1. First call for a client  → paginate API to fetch ALL spots
                                  → build TF-IDF index in SpotVectorStore
      2. Subsequent calls         → query the in-memory index (no API call)

    search_term handling:
      - Provided  → top-15 semantically closest spots (handles typos, partial)
      - Empty     → return all spots (user wants to browse everything)
    list_buildings_only:
      - True → return unique building names only (no spot detail tiles)
    """
    from app.services.spot_vector_store import spot_store

    # ── Load vector store on first call for this client ───────────────────────
    if not spot_store.is_loaded(user_name):
        logger.info(
            f"🔄 Vector store not loaded for '{user_name}' — "
            f"fetching all spots from API ..."
        )
        raw_spots = await _fetch_all_spots_from_api(user_name)
        if not raw_spots:
            return json.dumps({"error": f"No spots available for {user_name}."})
        spot_store.load(user_name, raw_spots)
    else:
        logger.info(f"⚡ Vector store already loaded for '{user_name}' — skipping API call")

    # ── Buildings-only mode ────────────────────────────────────────────────────
    if list_buildings_only:
        all_spots = spot_store.get_all(user_name)  # full list
        seen = set()
        unique_buildings = []
        for spot in all_spots:
            b = spot.get("BuildingName", "").strip()
            if b and b not in seen:
                seen.add(b)
                unique_buildings.append({"BuildingName": b})
        logger.info(f"🏢 Buildings-only mode | client='{user_name}' | unique_buildings={len(unique_buildings)}")
        return json.dumps({"type": "buildings_list", "p_list": unique_buildings})

    # ── Semantic search ────────────────────────────────────────────────────────
    # For empty query: return ALL spots (user wants to browse everything).
    # For specific query: get ALL spots then filter locally so every matching
    # result is returned — not just the top-15 similarity hits.
    import re as _re

    if not search_term or not str(search_term).strip():
        # Browse all: return full list
        results = spot_store.get_all(user_name)
        total_count = len(results)
        logger.info(f"📋 No search_term — returning all {total_count} spots for '{user_name}'")
    else:
        # Filtered search: get ALL spots, filter by search term across key fields
        all_spots = spot_store.get_all(user_name)
        clean_q = _re.sub(r'[^a-z0-9]', '', str(search_term).lower())
        results = [
            s for s in all_spots
            if clean_q in _re.sub(r'[^a-z0-9]', '', str(s.get("BuildingName", "")).lower())
            or clean_q in _re.sub(r'[^a-z0-9]', '', str(s.get("SpotCode", "")).lower())
            or clean_q in _re.sub(r'[^a-z0-9]', '', str(s.get("SpotName", "")).lower())
            or clean_q in _re.sub(r'[^a-z0-9]', '', str(s.get("FloorName", "")).lower())
        ]
        # If no exact substring match, fall back to top-15 vector similarity search
        if not results:
            results = spot_store.search(user_name, search_term, top_k=15)
            logger.info(f"🔍 Fallback vector search | query='{search_term}' | hits={len(results)}")
        else:
            logger.info(f"🔎 Local filter | query='{search_term}' | matches={len(results)}")
        total_count = len(results)

    logger.info(f"✅ Spot search done | user='{user_name}' | query='{search_term}' | results={total_count}")
    return json.dumps({"TotalCount": total_count, "p_list": results})


@tool("GET_SPOTS", args_schema=GetSpotsInput)
async def GET_SPOTS(user_name: str, search_term: Optional[str] = None, list_buildings_only: Optional[bool] = False) -> str:
    """Fetch available spots by building name or spot code, or list unique buildings."""
    logger.info(f"🛠️ GET_SPOTS: user_name={user_name}, search_term={search_term}, list_buildings_only={list_buildings_only}")
    return await fetch_spots_api(user_name, search_term, list_buildings_only=bool(list_buildings_only))


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
    """Insert a booking with:
    - Bug 1 fix: retry loop to avoid duplicate booking_id collision
    - Bug 3 fix: overlap check — prevent double-booking the same spot at same time
    """
    import random
    try:
        import psycopg2.errors as _pg_errors
    except ImportError:
        _pg_errors = None

    conn = get_pool()
    if not conn:
        return json.dumps({"error": "Database connection failed."})

    spot_code  = booking_data.get("spot_code")
    start_time = booking_data.get("start_time")
    end_time   = booking_data.get("end_time")

    # ── Bug 3 Fix: Overlap check ─────────────────────────────────────────────
    # Reject if another booking for the same spot overlaps the requested window.
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT booking_id FROM space_bookings
                WHERE spot_code = %s
                  AND NOT (end_time <= %s OR start_time >= %s)
                LIMIT 1
                """,
                (spot_code, start_time, end_time)
            )
            conflict = cur.fetchone()
        if conflict:
            logger.warning(
                "⚠️ Overlap conflict for spot %s (%s → %s) — existing booking %s",
                spot_code, start_time, end_time, conflict[0]
            )
            return json.dumps({
                "error": (
                    f"Sorry, {spot_code} is already booked during that time slot. "
                    "Please choose a different time or spot."
                )
            })
    except Exception as overlap_err:
        logger.error(f"❌ Overlap check failed: {overlap_err}", exc_info=True)

    # ── Bug 1 Fix: Retry loop for unique booking_id ──────────────────────────
    for attempt in range(10):
        booking_id = str(random.randint(1000, 9999))
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO space_bookings
                    (booking_id, client_name, sub_user_name, spot_code, spot_name,
                     building_name, floor_name, start_time, end_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        booking_id,
                        booking_data.get("user_name"),
                        booking_data.get("sub_user_name", "user"),
                        spot_code,
                        booking_data.get("spot_name"),
                        booking_data.get("building_name"),
                        booking_data.get("floor_name"),
                        start_time,
                        end_time,
                    )
                )
                conn.commit()
            logger.info(f"✅ Booking saved. ID: {booking_id} (attempt {attempt + 1})")
            return json.dumps({
                "success": True,
                "booking_id": booking_id,
                "spot_code": spot_code,
                "spot_name": booking_data.get("spot_name"),
                "building_name": booking_data.get("building_name"),
                "floor_name": booking_data.get("floor_name"),
                "start_time": start_time,
                "end_time": end_time,
            })
        except Exception as e:
            # Check for unique-constraint violation on booking_id
            err_str = str(e).lower()
            if "unique" in err_str or "duplicate" in err_str:
                logger.warning(
                    f"⚠️ Booking ID {booking_id} already exists — retrying (attempt {attempt + 1})"
                )
                try:
                    conn.rollback()
                except Exception:
                    pass
                continue  # retry with a new ID
            logger.error(f"❌ Failed to insert booking: {e}", exc_info=True)
            return json.dumps({"error": f"Failed to save booking: {e}"})

    return json.dumps({"error": "Could not generate a unique Booking ID after 10 attempts. Please try again."})


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
    from datetime import datetime as _dt
    logger.info(f"🛠️ BOOK_SPOT: spot_code={spot_code}, start_time={start_time}, end_time={end_time}")

    # ── Bug 6 & 7 Fix: start_time required ───────────────────────────────────
    if not start_time or start_time.strip() == "" or start_time.lower() in ("none", "unknown"):
        return json.dumps({
            "error_type": "missing_time",
            "spot_code": spot_code,
            "building_name": building_name
        })

    # ── Bug 6 & 7 Fix: end_time required (no silent fallback) ────────────────
    if not end_time or end_time.strip() == "" or end_time.lower() in ("none", "unknown"):
        return json.dumps({
            "error_type": "missing_time",
            "message": "End time is required. Please provide a valid end time.",
            "spot_code": spot_code,
            "building_name": building_name
        })

    # ── Bug 4 Fix: Reject past dates ─────────────────────────────────────────
    try:
        # Attempt to parse the start_time as a datetime (supports "YYYY-MM-DD HH:MM" format)
        start_dt = _dt.fromisoformat(start_time.replace("T", " ").strip())
        if start_dt < _dt.now():
            return json.dumps({
                "error": (
                    "Bookings cannot be made for past dates or times. "
                    "Please select today or a future date and time."
                )
            })
    except ValueError:
        # If parsing fails, fall through — the DB constraint will catch it
        logger.warning(f"⚠️ Could not parse start_time '{start_time}' for past-date check")

    # ── Bug 6 & 7 Fix: start_time must be strictly before end_time ───────────
    try:
        start_dt_cmp = _dt.fromisoformat(start_time.replace("T", " ").strip())
        end_dt_cmp   = _dt.fromisoformat(end_time.replace("T", " ").strip())
        if start_dt_cmp >= end_dt_cmp:
            return json.dumps({
                "error": (
                    "End time must be later than start time. "
                    "Please select a valid time range where the end time comes after the start time."
                )
            })
    except ValueError:
        logger.warning(
            f"⚠️ Could not compare start_time '{start_time}' and end_time '{end_time}'"
        )

    booking_data = {
        "user_name": user_name,
        "sub_user_name": sub_user_name,
        "spot_code": spot_code,
        "spot_name": spot_name,
        "building_name": building_name,
        "floor_name": floor_name,
        "start_time": start_time,
        "end_time": end_time,           # Bug 6 fix: no longer silently falls back to start_time
    }
    return await asyncio.to_thread(_insert_booking, booking_data)




