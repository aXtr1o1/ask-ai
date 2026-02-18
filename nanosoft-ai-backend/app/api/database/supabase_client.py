# app/api/database/supabase_client.py
import logging
from supabase import create_client, Client
from app.config import settings

# ===========================
# 1. SETUP LOGGER
# ===========================
logger = logging.getLogger("supabase_client")
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
# 2. SUPABASE CLIENT
# ===========================
_client: Client | None = None

def get_supabase_client() -> Client:
    global _client
    if _client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            logger.critical("Supabase URL or Key not set in environment variables")
            raise RuntimeError("Supabase URL or Key not set in environment variables")
        
        _client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )
        logger.info("✅ Supabase client initialized successfully")
    else:
        logger.debug("Supabase client already initialized, returning existing instance")
    return _client
