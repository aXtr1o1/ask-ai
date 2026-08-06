"""
Common Service
--------------
Shared utility functions used across multiple services.
Any service that needs to fetch client credentials (base_url, jwt_token, user_id)
from the client_sync_config table should import from here — not define its own copy.
"""
import logging
from app.api.database.postgres_client import get_pool

logger = logging.getLogger("common_service")
logger.setLevel(logging.INFO)
_ch = logging.StreamHandler()
_ch.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(_ch)


def get_client_config_sync(user_name: str) -> dict | None:
    """
    Fetch base_url, jwt_token, and user_id from client_sync_config by client_name.

    Args:
        user_name (str): The client_name to look up in the DB.

    Returns:
        dict with keys 'base_url', 'jwt_token', 'user_id' if found, else None.

    Usage:
        from app.services.common_service import get_client_config_sync
        config = get_client_config_sync(user_name)
    """
    conn = get_pool()
    if not conn:
        logger.error("❌ No DB connection available in get_client_config_sync")
        return None

    with conn.cursor() as cur:
        cur.execute(
            "SELECT base_url, jwt_token, user_id FROM client_sync_config WHERE client_name = %s",
            (user_name,)
        )
        row = cur.fetchone()
        if row:
            return {
                "base_url": row[0],
                "jwt_token": row[1],
                "user_id": str(row[2]) if row[2] is not None else "1"
            }

    logger.warning("⚠️ No config found in client_sync_config for client_name='%s'", user_name)
    return None
