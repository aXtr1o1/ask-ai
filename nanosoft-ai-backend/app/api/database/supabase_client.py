# app/api/database/supabase_client.py
from supabase import create_client, Client
from app.config import settings
_client: Client | None = None

def get_supabase_client() -> Client:
    global _client
    if _client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise RuntimeError("Supabase URL or Key not set in environment variables")
        
        _client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )
        print("✅ Supabase client initialized")
    return _client
