# app/state.py
from app.config import settings

MAX_HISTORY: int = settings.MAX_HISTORY
memory_store: dict = {}
frontend_saved_sessions: set = set()