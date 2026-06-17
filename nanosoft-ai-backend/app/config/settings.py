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
PG_PASSWORD = os.getenv("PG_PASSWORD", "testpass") 

# Google AI
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "fake-api-key-for-testing")  
GOOGLE_AI_MODEL = os.getenv("GOOGLE_AI_MODEL", "gemini-2.5-flash").strip()
GOOGLE_SPACE_BOOKING_MODEL = os.getenv("GOOGLE_SPACE_BOOKING_MODEL", "gemini-2.5-flash").strip()

# ── Multi-Agent Pipeline (Phase 1) ─────────────────────────────────────────
MULTI_AGENT_MODEL = os.getenv("MULTI_AGENT_MODEL", "gemini-2.5-flash").strip()
THINKING_BUDGET_TOKENS = int(os.getenv("THINKING_BUDGET_TOKENS", "3000"))

# App Config
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "5"))
DATABASE_API_URL = os.getenv("DATABASE_API_URL", "http://localhost:8000")
L1_TTL_SECONDS = int(os.getenv("L1_TTL_SECONDS", "120"))
L2_TTL_SECONDS = int(os.getenv("L2_TTL_SECONDS", "120"))
L1_SIZE_THRESHOLD = int(os.getenv("L1_SIZE_THRESHOLD", "5"))
WS_SESSION_TIMEOUT = int(os.getenv("WS_SESSION_TIMEOUT", "120"))   
WS_PING_INTERVAL = int(os.getenv("WS_PING_INTERVAL", "30"))

# Sync Config
SYNC_INTERVAL_MINUTES = int(os.getenv("SYNC_INTERVAL_MINUTES", "20"))
SYNC_PAGE_SIZE = int(os.getenv("SYNC_PAGE_SIZE", "1000"))
LOGIN_USERNAME = os.getenv("SYNC_LOGIN_USERNAME", "test_user")  
LOGIN_PASSWORD = os.getenv("SYNC_LOGIN_PASSWORD", "test_pass")
