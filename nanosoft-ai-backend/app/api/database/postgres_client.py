"""
PostgreSQL client for chat_sessions (async pool).
"""
import logging
import asyncpg
from typing import Optional
from app.config import settings

logger = logging.getLogger("postgres_client")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(ch)

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """Get or create the async PostgreSQL connection pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=settings.PG_HOST,
            port=settings.PG_PORT,
            database=settings.PG_DATABASE,
            user=settings.PG_USER,
            password=settings.PG_PASSWORD,
            min_size=1,
            max_size=10,
            command_timeout=60,
        )
        logger.info("✅ PostgreSQL connection pool initialized")
    return _pool


async def close_pool() -> None:
    """Close the pool (e.g. on shutdown)."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL pool closed")
