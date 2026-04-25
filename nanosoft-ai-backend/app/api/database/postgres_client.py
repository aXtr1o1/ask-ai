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


def init_pool() -> None:
    """Initialize the PostgreSQL connection on startup."""
    global _client
    if not all([settings.PG_HOST, settings.PG_DATABASE, settings.PG_USER, settings.PG_PASSWORD]):
        logger.critical("Database credentials not set in environment variables")
        raise RuntimeError("Database credentials not set in environment variables")

    _client = psycopg2.connect(
        host     = settings.PG_HOST,
        port     = settings.PG_PORT,
        dbname   = settings.PG_DATABASE,
        user     = settings.PG_USER,
        password = settings.PG_PASSWORD,
    )
    logger.info("✅ PostgreSQL client initialized successfully")


def close_pool() -> None:
    """Close the PostgreSQL connection on shutdown."""
    global _client
    if _client and not _client.closed:
        _client.close()
        logger.info("🛑 PostgreSQL connection closed")
        _client = None


def get_pool() -> connection:
    """Get the existing connection, initializing if needed. Tests connection validity."""
    global _client
    if _client is None or _client.closed:
        logger.warning("Connection not initialized or closed, re-initializing...")
        init_pool()
    else:
        # Ping the server to ensure the connection hasn't been silently dropped by timeout
        try:
            with _client.cursor() as cur:
                cur.execute("SELECT 1")
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            logger.warning("Connection ping failed (likely timed out), re-initializing...")
            init_pool()

    return _client


def release_conn(conn: connection) -> None:
    """
    Release/return the connection.
    Since this is a single shared connection (not a pool),
    this is a no-op — kept for API compatibility with callers.
    """
    logger.debug("release_conn called — no-op for single connection mode")