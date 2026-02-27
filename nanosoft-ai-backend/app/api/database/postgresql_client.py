# app/api/database/postgresql_client.py
import logging
import os
import psycopg2
from psycopg2.extensions import connection
from dotenv import load_dotenv

from pathlib import Path
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# ===========================
# 1. SETUP LOGGER
# ===========================
logger = logging.getLogger("postgresql_client")
logger.setLevel(logging.INFO)  # Change to DEBUG if you want more details

# Console handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

# Add handler to logger (avoid adding multiple times)
if not logger.handlers:
    logger.addHandler(ch)

# ===========================
# 2. DATABASE CLIENT
# ===========================
_client: connection | None = None

def get_postgresql_client() -> connection:
    global _client

    if _client is None or _client.closed:
        db_host = os.getenv("DB_HOST")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME")
        db_user = os.getenv("DB_USER")
        db_pass = os.getenv("DB_PASS")

       

        if not all([db_host, db_name, db_user, db_pass]):
            logger.critical("Database credentials not set in environment variables")
            raise RuntimeError("Database credentials not set in environment variables")

        _client = psycopg2.connect(
            host     = db_host,
            port     = db_port,
            dbname   = db_name,
            user     = db_user,
            password = db_pass,
        )
        logger.info("✅ PostgreSQL client initialized successfully")
    else:
        logger.debug("PostgreSQL client already initialized, returning existing instance")

    return _client