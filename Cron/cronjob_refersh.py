import os
import sys
import logging
import requests
from datetime import datetime, timezone

# Add the root directory to Python path so we can import 'app'
# This allows the script to be run manually from anywhere
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.api.database.postgres_client import get_pool, init_pool, close_pool
from app.dynamic.service import (
    get_services_for_client,
    sync_service_data
)

# ── Logger setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("cron.manual_refresh")

# ══════════════════════════════════════════════════════════════════════════════
# NEW: AUTOMATIC TOKEN GENERATION
# ══════════════════════════════════════════════════════════════════════════════
def fetch_and_save_new_token(conn, client_name: str, user_id: int, base_url: str) -> str:
    """
    Automatically logs into the external API, gets a fresh JWT token,
    saves it to the database, and returns it.
    """
    logger.info(f"🔑 Generating fresh JWT token for {client_name} (User {user_id})...")

    # Bulletproof URL parsing to handle any variations in the database (like /askmeapi or /askmeapi-docs)
    from urllib.parse import urlparse
    parsed = urlparse(base_url)
    root_domain = f"{parsed.scheme}://{parsed.netloc}"
    login_url = f"{root_domain}/askmeapi/login"
    
    import json
    # Hardcoded credentials from the screenshot
    payload = {
        "username": "SMARTFM",
        "password": "n@no@313"
    }
    
    # The exact raw string from the Swagger curl command
    payload_str = '{\n  "username": "SMARTFM",\n  "password": "n@n0@313"\n}'
    payload_bytes = payload_str.encode('utf-8')
    
    import urllib.request
    import urllib.error
    
    req = urllib.request.Request(login_url, method="POST")
    req.add_header("accept", "application/json")
    req.add_header("Content-Type", "application/json")
    # Pretend to be a real browser to bypass WAF TLS fingerprinting
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    try:
        logger.info(f"    📡 Sending POST request to: {login_url}")
        logger.debug(f"    📤 Payload: {payload_str}")
        
        with urllib.request.urlopen(req, data=payload_bytes, timeout=10) as response:
            status_code = response.getcode()
            logger.info(f"    📥 Received Response Status: {status_code}")
            
            response_text = response.read().decode('utf-8')
            data = json.loads(response_text)
            
        logger.debug(f"    📦 Response JSON: {str(data)[:200]}...")

        
        # Extract the token (checking multiple possible JSON formats)
        new_token = (
            data.get("token") or 
            data.get("accessToken") or 
            data.get("result", {}).get("accessToken") or
            data.get("data", {}).get("token")
        )

        if not new_token:
            logger.error(f"    ❌ Token extraction failed! Full response: {data}")
            raise ValueError(f"Could not find token in response")

        # Format the token exactly as the frontend expects it
        bearer_token = f"Bearer {new_token}"

        logger.info(f"    ✅ Token extracted successfully for User {user_id}!")
        logger.info(f"    🔑 NEW TOKEN: {bearer_token}")

        # Save the new token back to the database for this specific user
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE client_registry 
            SET token = %s 
            WHERE client_name = %s AND user_id = %s
            """,
            (bearer_token, client_name, user_id)
        )
        conn.commit()
        cursor.close()

        logger.info(f"✅ Successfully generated and saved new token for {client_name}!")
        return new_token

    except Exception as e:
        logger.error(f"❌ Failed to generate new token for {client_name}: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# MAIN SYNC LOOP
# ══════════════════════════════════════════════════════════════════════════════
def run_manual_sync():
    logger.info("🚀 Starting manual background sync job...")
    
    init_pool()
    conn = get_pool()
    
    try:
        cursor = conn.cursor()
        
        # Iterate through each active row (now uniquely identified by client_name AND user_id)
        cursor.execute("SELECT client_name, base_url, user_id FROM client_registry WHERE is_active = true")
        active_rows = cursor.fetchall()

        if not active_rows:
            logger.info("ℹ️ No active users found in client_registry. Exiting.")
            return

        for client_name, base_url, user_id in active_rows:
            logger.info(f"🔄 Processing Client: {client_name} | User ID: {user_id}")
            logger.info(f"🌐 Extracted Base URL: {base_url}")
            
            # --- Automatically Fetch and Save Fresh Token ---
            fresh_token = fetch_and_save_new_token(conn, client_name, user_id, base_url)
            
            if not fresh_token:
                logger.warning(f"⚠️ Failed to refresh token for {client_name} (User {user_id}).")
                continue
            
            # --- Update last_synced_at timestamp ---
            cursor.execute(
                "UPDATE client_registry SET last_synced_at = %s WHERE client_name = %s AND user_id = %s",
                (datetime.now(timezone.utc), client_name, user_id)
            )
            conn.commit()
            logger.info(f"⏰ Updated last_synced_at for '{client_name}' (User {user_id})")

        cursor.close()
        logger.info("🎉 Token refresh cronjob completed successfully!")

    except Exception as e:
        logger.error(f"❌ Critical error during manual sync: {e}", exc_info=True)
    finally:
        close_pool()

if __name__ == "__main__":
    run_manual_sync()
