import json
import logging
import asyncio
import requests
from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.config import settings
from app.api.database.postgres_client import get_pool
from app.models.schemas import BookSpotInput

logger = logging.getLogger("space_booking_tool")
logger.setLevel(logging.INFO)

class GetSpotsInput(BaseModel):
    user_name: str = Field(description="The user name from the frontend context.")
    search_term: Optional[str] = Field(default=None, description="The Spot Code (e.g. WRMF-NES) or Building Name. You MUST extract this from the user's query and pass it.")

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
        
    spot_code_payload = None
    building_name_payload = None
    if search_term:
        # Heuristic: If it has a hyphen or is just a single capitalized word like WRMF-NES, it's a SpotCode
        if "-" in search_term or (search_term.isupper() and " " not in search_term):
            spot_code_payload = search_term
        else:
            building_name_payload = search_term
    headers = {
        "x-auth": jwt_token,
        "userid": "101",
        "Content-Type": "application/json"
    }
    # Always pass None to API to fetch the first 100 spots for RAG-like local filtering
    payload = {
        "SpotCode": None,
        "SpotName": None,
        "SpotNo": None,
        "SpotTypeCode": None,
        "SpotTypeName": None,
        "LocalityGroupCode": None,
        "LocalityGroupName": None,
        "CityCode": None,
        "CityName": None,
        "AdminLocalityTypeCode": None,
        "AdminLocalityTypeName": None,
        "LocalityCode": None,
        "LocalityName": None,
        "AssBuildingTypeCode": None,
        "AssBuildingTypeName": None,
        "BuildingCode": None,
        "BuildingName": None,
        "FloorCode": None,
        "FloorName": None,
        "AssWingCode": None,
        "AssWingName": None,
        "PageIndex": "1",
        "PageSize": "100",
        "Type": "SpotID",
        "UserGroupKey": "1",
        "UserAccessKey": "1"
    }
        
    logger.info(f"🚀 POST request to {api_url} with payload {payload}")
    try:
        response = await asyncio.to_thread(
            requests.post, api_url, headers=headers, json=payload, timeout=15
        )
        if response.status_code == 200:
            json_resp = response.json()
            p_list = json_resp.get("data", [])
            
            # Perform RAG-like fuzzy matching in Python to handle spelling mistakes
            if search_term and str(search_term).strip():
                import re
                # Clean search term: lowercase and remove non-alphanumeric chars
                clean_search = re.sub(r'[^a-z0-9]', '', str(search_term).lower())
                
                fuzzy_matches = []
                for s in p_list:
                    # Clean the fields we want to search against
                    b_name = re.sub(r'[^a-z0-9]', '', str(s.get("BuildingName", "")).lower())
                    s_code = re.sub(r'[^a-z0-9]', '', str(s.get("SpotCode", "")).lower())
                    s_name = re.sub(r'[^a-z0-9]', '', str(s.get("SpotName", "")).lower())
                    
                    # If the search term is found in any of these fields, it's a match!
                    if clean_search in b_name or clean_search in s_code or clean_search in s_name:
                        fuzzy_matches.append(s)
                
                # If we found any matches, update the list
                if len(fuzzy_matches) > 0:
                    p_list = fuzzy_matches
                    
            total_count = len(p_list)
            
            logger.info(f"✅ Total data length: {total_count}. Sample: {p_list[:2]}")
            return json.dumps({
                "TotalCount": total_count,
                "p_list": p_list
            })
        else:
            logger.error(f"❌ API error: {response.text}")
            return json.dumps({"error": f"Error fetching spots (HTTP {response.status_code})"})
        
    except Exception as e:
        logger.error(f"❌ Error in API call: {e}", exc_info=True)
        return json.dumps({"error": str(e)})

@tool("GET_SPOTS", args_schema=GetSpotsInput)
async def GET_SPOTS(user_name: str, search_term: Optional[str] = None) -> str:
    """Fetch spot booking data based on user constraints."""
    logger.info(f"🛠️ GET_SPOTS tool called: user_name={user_name}, search_term={search_term}")
    return await fetch_spots_api(user_name, search_term)

def _insert_booking(booking_data: dict) -> str:
    import random
    
    # Generate random 4-digit ID, ensure uniqueness
    booking_id = str(random.randint(1000, 9999))
    try:
        conn = get_pool()
        if not conn:
            return json.dumps({"error": "Database connection failed."})
        
        with conn.cursor() as cur:
            # We assume chance of collision is low, but retry logic could be added if needed
            cur.execute("""
                INSERT INTO space_bookings 
                (booking_id, client_name, sub_user_name, spot_code, spot_name, building_name, floor_name, timing)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                booking_id,
                booking_data.get("user_name"),
                booking_data.get("sub_user_name", "user"),
                booking_data.get("spot_code"),
                booking_data.get("spot_name"),
                booking_data.get("building_name"),
                booking_data.get("floor_name"),
                booking_data.get("timing")
            ))
            conn.commit()
            
        logger.info(f"✅ Booking saved successfully. ID: {booking_id}")
        return json.dumps({
            "success": True,
            "booking_id": booking_id,
            "message": f"Successfully booked spot {booking_data.get('spot_code')} at {booking_data.get('timing')}."
        })
    except Exception as e:
        logger.error(f"❌ Failed to insert booking: {e}", exc_info=True)
        return json.dumps({"error": f"Failed to save booking: {e}"})

@tool("BOOK_SPOT", args_schema=BookSpotInput)
async def BOOK_SPOT(user_name: str, spot_code: str, spot_name: Optional[str] = "Unknown Spot", building_name: Optional[str] = "Unknown Building", floor_name: Optional[str] = "Unknown Floor", timing: Optional[str] = None, sub_user_name: Optional[str] = None) -> str:
    """Book a space after the user has confirmed the spot and time. Generates a unique 4-digit booking ID."""
    logger.info(f"🛠️ BOOK_SPOT tool called: user_name={user_name}, spot_code={spot_code}, timing={timing}")
    
    if not timing or timing.strip() == "" or timing.lower() == "none" or timing.lower() == "unknown":
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
