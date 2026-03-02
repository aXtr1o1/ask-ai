import psycopg2
import psycopg2.extras
from app.config import settings
import logging

log = logging.getLogger("sync_engine")

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=settings.PG_HOST,
            port=settings.PG_PORT,
            database=settings.PG_DATABASE,
            user=settings.PG_USER,
            password=settings.PG_PASSWORD,
        )
        log.info("✅ PostgreSQL connection successful")
        return conn
    except Exception as e:
        log.error(f"❌ PostgreSQL connection failed: {e}")
        raise