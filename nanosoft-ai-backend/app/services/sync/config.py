"""
app/services/sync/config.py
────────────────────────────
Central constants for the sync engine.
Change PAGE_SIZE here — affects all fetches (assets, ppm, bdm).
"""

import logging

# ── Logging ───────────────────────────────────────────────────────────────────
log = logging.getLogger("sync.engine")

# ── HTTP fetch config ─────────────────────────────────────────────────────────
REQUEST_TIMEOUT = 30     # seconds to wait for client API response
MAX_RETRIES     = 3      # how many times to retry a failed page fetch
PAGE_SIZE       = 1000   # 10x fewer HTTP round trips)  