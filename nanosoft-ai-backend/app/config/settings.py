from pathlib import Path
from dotenv import load_dotenv
import os

# .env is inside the app folder
BASE_DIR = Path(__file__).resolve().parent.parent 
load_dotenv(dotenv_path=BASE_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase URL or Key not set in environment variables")

# Redis, Google API, Session config as before
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT"))
REDIS_USERNAME = os.getenv("REDIS_USERNAME")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_AI_MODEL = os.getenv("GOOGLE_AI_MODEL")
MAX_HISTORY = int(os.getenv("MAX_HISTORY"))
DATABASE_API_URL = os.getenv("DATABASE_API_URL")
L1_TTL_SECONDS   =int(os.getenv("L1_TTL_SECONDS"))
L2_TTL_SECONDS   =int(os.getenv("L2_TTL_SECONDS")) 
L1_SIZE_THRESHOLD =int(os.getenv("L1_SIZE_THRESHOLD"))
WS_SESSION_TIMEOUT = int(os.getenv("WS_SESSION_TIMEOUT", "120"))   
WS_PING_INTERVAL   = int(os.getenv("WS_PING_INTERVAL", "30"))       


# if __name__ == "__main__":
#     print("✅ Loaded .env from:", BASE_DIR / ".env")
#     print("✅ Supabase URL:", SUPABASE_URL)
#     print("✅ Supabase Key loaded:", bool(SUPABASE_KEY))
#     print("✅ Redis Host:", REDIS_HOST)
