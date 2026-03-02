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
    """Get or create the sync PostgreSQL connection."""
    global _client

    if _client is None or _client.closed:
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
    else:
        logger.debug("PostgreSQL client already initialized, returning existing instance")

    return _client
