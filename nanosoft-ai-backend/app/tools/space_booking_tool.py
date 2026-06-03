import json
import logging
import asyncio
import requests
from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.config import settings
from app.api.database.postgres_client import get_pool

logger = logging.getLogger("space_booking_tool")
logger.setLevel(logging.INFO)

class GetSpotsInput(BaseModel):
    user_name: str = Field(description="The user name from the frontend context.")
    building_name: Optional[str] = Field(default=None, description="Optional building name. Use if user asks for spots in a specific building.")
    spot_id: Optional[int] = Field(default=None, description="Optional Spot ID (SpotIDPK). Use if user provides an exact spot ID.")

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

async def fetch_spots_api(user_name: str, building_name: Optional[str] = None, spot_id: Optional[int] = None) -> str:
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
        "BuildingName": building_name if building_name else None,
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
            
            # If the user provided a spot_id, filter the results in Python!
            if spot_id is not None:
                p_list = [s for s in p_list if s.get("SpotIDPK") == spot_id]
                
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
async def GET_SPOTS(user_name: str, building_name: Optional[str] = None, spot_id: Optional[int] = None) -> str:
    """Fetch spot booking data based on user constraints."""
    logger.info(f"🛠️ GET_SPOTS tool called: user_name={user_name}, building={building_name}, spot_id={spot_id}")
    return await fetch_spots_api(user_name, building_name, spot_id)
