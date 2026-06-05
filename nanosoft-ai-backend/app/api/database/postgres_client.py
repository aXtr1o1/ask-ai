"""
PostgreSQL client (sync psycopg2 connection).
"""
import logging
import psycopg2
from psycopg2.extensions import connection
from app.config import settings

logger = logging.getLogger("postgres_client")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(ch)

_client: connection | None = None


def get_pool() -> connection:
    """Get or create the sync PostgreSQL connection.

    Handles stale/timed-out connections by explicitly closing and
    reconnecting so queries never fail silently on a zombie connection.
    """
    global _client

    # Check if client is None, closed, or if the connection is "dead" (stale/timed out)
    is_dead = False
    if _client and not _client.closed:
        try:
            # Perform a quick liveness check (ping)
            with _client.cursor() as cur:
                cur.execute("SELECT 1")
        except Exception as ping_err:
            logger.warning("⚠️ PostgreSQL connection ping failed (%s) — will reconnect", ping_err)
            is_dead = True
            # Explicitly close the stale connection before replacing it
            try:
                _client.close()
            except Exception:
                pass
            _client = None

    if _client is None or (hasattr(_client, 'closed') and _client.closed) or is_dead:
        if not all([settings.PG_HOST, settings.PG_DATABASE, settings.PG_USER, settings.PG_PASSWORD]):
            logger.critical("Database credentials not set in environment variables")
            raise RuntimeError("Database credentials not set in environment variables")

        logger.info("🔄 Creating new PostgreSQL connection...")
        _client = psycopg2.connect(
            host     = settings.PG_HOST,
            port     = settings.PG_PORT,
            dbname   = settings.PG_DATABASE,
            user     = settings.PG_USER,
            password = settings.PG_PASSWORD,
        )
        logger.info("✅ PostgreSQL client initialized successfully")
    else:
        logger.debug("PostgreSQL client already initialized, returning existing instance")

    return _client
