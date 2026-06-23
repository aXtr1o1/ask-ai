"""
app/agents/services/__init__.py

Agent-specific service modules.

WHY this folder exists (separate from app/services/):
  app/services/   — Application-wide services (DB client, session, audio, quota, etc.)
                    Used by routes, websocket handlers, and other app layers.

  app/agents/services/ — Services that ONLY the agent pipeline uses.
                    These are not needed by routes or the rest of the app.
                    Keeping them here means anyone reading an agent file can find
                    its dependency in the same folder, not scattered in app/services/.

Current modules:
  enum_service.py — Fetches distinct filter enum values from DB for prompt injection.
"""
