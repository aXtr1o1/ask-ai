import os
import sys
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone
from urllib.parse import urlparse

import psycopg2

# Add nanosoft-ai-backend root to Python path for settings import
_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

from app.config import settings

# ── Logger setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("cron.token_refresh")

# ── Hardcoded login credentials ───────────────────────────────────────────────
LOGIN_USERNAME = "SMARTFM"
LOGIN_PASSWORD = "n@n0@313"


# ══════════════════════════════════════════════════════════════════════════════
# HELPER: Build DB connection (only dbname differs)
# ══════════════════════════════════════════════════════════════════════════════
def get_db_connection(dbname: str):
    """Create a psycopg2 connection using settings credentials, hardcoded dbname."""
    conn = psycopg2.connect(
        host=settings.PG_HOST,
        port=settings.PG_PORT,
        dbname=dbname,
        user=settings.PG_USER,
        password=settings.PG_PASSWORD,
    )
    logger.info(f"✅ Connected to database: {dbname}")
    return conn


# ══════════════════════════════════════════════════════════════════════════════
# HELPER: Call login API and return fresh raw JWT token
# ══════════════════════════════════════════════════════════════════════════════
def fetch_fresh_token(base_url: str, label: str) -> str | None:
    """
    Calls the login endpoint derived from base_url.
    Returns the raw JWT token string (without 'Bearer' prefix), or None on failure.
    """
    parsed = urlparse(base_url)
    root_domain = f"{parsed.scheme}://{parsed.netloc}"
    login_url = f"{root_domain}/askmeapi/login"

    payload_str = json.dumps({
        "username": LOGIN_USERNAME,
        "password": LOGIN_PASSWORD
    }, indent=2)
    payload_bytes = payload_str.encode("utf-8")

    req = urllib.request.Request(login_url, method="POST")
    req.add_header("accept", "application/json")
    req.add_header("Content-Type", "application/json")
    req.add_header(
        "User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    try:
        logger.info(f"    📡 [{label}] POST → {login_url}")
        with urllib.request.urlopen(req, data=payload_bytes, timeout=10) as response:
            status_code = response.getcode()
            logger.info(f"    📥 [{label}] Response status: {status_code}")
            data = json.loads(response.read().decode("utf-8"))

        raw_token = (
            data.get("token") or
            data.get("accessToken") or
            data.get("result", {}).get("accessToken") or
            data.get("data", {}).get("token")
        )

        if not raw_token:
            logger.error(f"    ❌ [{label}] Token not found in response: {data}")
            return None

        logger.info(f"    ✅ [{label}] Token fetched successfully.")
        return raw_token

    except Exception as e:
        logger.error(f"    ❌ [{label}] Login API call failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 1 — nanosoft_ask → client_sync_config
# ══════════════════════════════════════════════════════════════════════════════
def refresh_tokens_nanosoft_ask():
    """
    Connects to nanosoft_ask DB.
    Loops all rows in client_sync_config.
    For each row: fetches fresh JWT via login API, logs old vs new, updates jwt_token + last_synced_at.
    """
    logger.info("=" * 70)
    logger.info("🔄 STARTING TOKEN REFRESH — nanosoft_ask → client_sync_config")
    logger.info("=" * 70)

    conn = get_db_connection("nanosoft_ask")

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, client_name, base_url, user_id, jwt_token FROM public.client_sync_config"
        )
        rows = cursor.fetchall()

        if not rows:
            logger.info("ℹ️  No rows found in client_sync_config. Skipping.")
            return

        logger.info(f"📋 Found {len(rows)} row(s) in client_sync_config.")

        for row_id, client_name, base_url, user_id, old_token in rows:
            label = f"nanosoft_ask | client={client_name} | user_id={user_id}"
            logger.info(f"\n{'─'*60}")
            logger.info(f" Processing: {label}")
            logger.info(f"     Base URL  : {base_url}")
            logger.info(f"     OLD TOKEN : {old_token}")

            raw_token = fetch_fresh_token(base_url, label)

            if not raw_token:
                logger.warning(f"    ⚠️  Skipping update for {label} — token fetch failed.")
                continue

            new_bearer_token = f"Bearer {raw_token}"
            logger.info(f"    🆕 NEW TOKEN : {new_bearer_token}")

            cursor.execute(
                """
                UPDATE public.client_sync_config
                SET jwt_token = %s, last_synced_at = %s
                WHERE id = %s
                """,
                (new_bearer_token, datetime.now(timezone.utc), row_id)
            )
            conn.commit()
            logger.info(f"    💾 DB updated successfully for {label}")

        cursor.close()
        logger.info("\n🎉 nanosoft_ask token refresh completed!")

    except Exception as e:
        logger.error(f"❌ Critical error in refresh_tokens_nanosoft_ask: {e}", exc_info=True)
        conn.rollback()
    finally:
        conn.close()
        logger.info("🔌 nanosoft_ask DB connection closed.")


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 2 — nanosoft_voice → users
# ══════════════════════════════════════════════════════════════════════════════
def refresh_tokens_nanosoft_voice():
    """
    Connects to nanosoft_voice DB.
    Loops all rows in users.
    For each row: fetches fresh JWT via login API, logs old vs new, updates jwt_token.
    """
    logger.info("=" * 70)
    logger.info("🔄 STARTING TOKEN REFRESH — nanosoft_voice → users")
    logger.info("=" * 70)

    conn = get_db_connection("nanosoft_voice")

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, client_id, name, base_url, jwt_token FROM public.users"
        )
        rows = cursor.fetchall()

        if not rows:
            logger.info("ℹ️  No rows found in users. Skipping.")
            return

        logger.info(f"📋 Found {len(rows)} row(s) in users.")

        for row_id, client_id, name, base_url, old_token in rows:
            label = f"nanosoft_voice | client_id={client_id} | name={name}"
            logger.info(f"\n{'─'*60}")
            logger.info(f" Processing: {label}")
            logger.info(f"    Base URL  : {base_url}")
            logger.info(f"     OLD TOKEN : {old_token}")

            if not base_url:
                logger.warning(f"    ⚠️  base_url is empty for {label}. Skipping.")
                continue

            raw_token = fetch_fresh_token(base_url, label)

            if not raw_token:
                logger.warning(f"    ⚠️  Skipping update for {label} — token fetch failed.")
                continue

            new_bearer_token = f"Bearer {raw_token}"
            logger.info(f"    🆕 NEW TOKEN : {new_bearer_token}")

            cursor.execute(
                """
                UPDATE public.users
                SET jwt_token = %s
                WHERE id = %s
                """,
                (new_bearer_token, row_id)
            )
            conn.commit()
            logger.info(f"    💾 DB updated successfully for {label}")

        cursor.close()
        logger.info("\n🎉 nanosoft_voice token refresh completed!")

    except Exception as e:
        logger.error(f"❌ Critical error in refresh_tokens_nanosoft_voice: {e}", exc_info=True)
        conn.rollback()
    finally:
        conn.close()
        logger.info("🔌 nanosoft_voice DB connection closed.")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    logger.info("🚀 Cron job started — refreshing tokens for all databases...")

    refresh_tokens_nanosoft_ask()
    refresh_tokens_nanosoft_voice()

    logger.info("\n✅ All token refresh jobs completed successfully!")