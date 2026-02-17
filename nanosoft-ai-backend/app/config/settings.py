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
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_USERNAME = os.getenv("REDIS_USERNAME", "default")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", 86400))
MAX_HISTORY = int(os.getenv("MAX_HISTORY", 10))
DEFAULT_USER = os.getenv("DEFAULT_USER", "ram")
DATABASE_API_URL = os.getenv("DATABASE_API_URL", "http://127.0.0.1:8000")
# # Optional debug
# if __name__ == "__main__":
#     print("✅ Loaded .env from:", BASE_DIR / ".env")
#     print("✅ Supabase URL:", SUPABASE_URL)
#     print("✅ Supabase Key loaded:", bool(SUPABASE_KEY))
#     print("✅ Redis Host:", REDIS_HOST)
