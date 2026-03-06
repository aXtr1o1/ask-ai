from pathlib import Path
from dotenv import load_dotenv
import os

# .env is inside the app folder
BASE_DIR = Path(__file__).resolve().parent.parent 
load_dotenv(dotenv_path=BASE_DIR / ".env")


# PostgreSQL (for chat_sessions)
PG_HOST = os.getenv("PG_HOST")
PG_PORT = int(os.getenv("PG_PORT"))
PG_DATABASE = os.getenv("PG_DATABASE")
PG_USER = os.getenv("PG_USER")
PG_PASSWORD = os.getenv("PG_PASSWORD")
if not all([PG_HOST, PG_DATABASE, PG_USER, PG_PASSWORD]):
    raise RuntimeError("PostgreSQL credentials not set in environment variables")



# Redis, Google API, Session config as before
# REDIS_HOST = os.getenv("REDIS_HOST")
# REDIS_PORT = int(os.getenv("REDIS_PORT"))
# REDIS_USERNAME = os.getenv("REDIS_USERNAME")
# REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_AI_MODEL = os.getenv("GOOGLE_AI_MODEL")
MAX_HISTORY = int(os.getenv("MAX_HISTORY"))
DATABASE_API_URL = os.getenv("DATABASE_API_URL")
L1_TTL_SECONDS   =int(os.getenv("L1_TTL_SECONDS"))
L2_TTL_SECONDS   =int(os.getenv("L2_TTL_SECONDS")) 
L1_SIZE_THRESHOLD =int(os.getenv("L1_SIZE_THRESHOLD"))
WS_SESSION_TIMEOUT = int(os.getenv("WS_SESSION_TIMEOUT", "120"))   
WS_PING_INTERVAL   = int(os.getenv("WS_PING_INTERVAL", "30"))       

PG_HOST: str = os.getenv("PG_HOST")
PG_PORT: int = int(os.getenv("PG_PORT"))
PG_DATABASE: str = os.getenv("PG_DATABASE")
PG_USER: str = os.getenv("PG_USER")
PG_PASSWORD: str = os.getenv("PG_PASSWORD")

# Sync Interval
SYNC_INTERVAL_MINUTES: int = int(os.getenv("SYNC_INTERVAL_MINUTES"))

SYNC_PAGE_SIZE: int = int(os.getenv("SYNC_PAGE_SIZE"))

SYNC_INTERVAL_MINUTES: int = int(os.getenv("SYNC_INTERVAL_MINUTES"))
SYNC_PAGE_SIZE: int = int(os.getenv("SYNC_PAGE_SIZE"))
LOGIN_USERNAME = os.getenv("SYNC_LOGIN_USERNAME")
LOGIN_PASSWORD = os.getenv("SYNC_LOGIN_PASSWORD")
