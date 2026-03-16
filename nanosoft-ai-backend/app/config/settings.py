from pathlib import Path
from dotenv import load_dotenv
import os

# .env is inside the app folder
BASE_DIR = Path(__file__).resolve().parent.parent 
load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)


# PostgreSQL (for chat_sessions)
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DATABASE = os.getenv("PG_DATABASE", "postgres")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_AI_MODEL = os.getenv("GOOGLE_AI_MODEL", "")
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "5"))
DATABASE_API_URL = os.getenv("DATABASE_API_URL", "")
L1_TTL_SECONDS = int(os.getenv("L1_TTL_SECONDS", "120"))
L2_TTL_SECONDS = int(os.getenv("L2_TTL_SECONDS", "120"))
L1_SIZE_THRESHOLD = int(os.getenv("L1_SIZE_THRESHOLD", "5"))
WS_SESSION_TIMEOUT = int(os.getenv("WS_SESSION_TIMEOUT", "120"))   
WS_PING_INTERVAL = int(os.getenv("WS_PING_INTERVAL", "30"))

# Sync Interval
SYNC_INTERVAL_MINUTES: int = int(os.getenv("SYNC_INTERVAL_MINUTES", "20"))
SYNC_PAGE_SIZE: int = int(os.getenv("SYNC_PAGE_SIZE", "1000"))
LOGIN_USERNAME = os.getenv("SYNC_LOGIN_USERNAME", "")
LOGIN_PASSWORD = os.getenv("SYNC_LOGIN_PASSWORD", "")
