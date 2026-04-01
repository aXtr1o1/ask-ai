"""
Standalone sync runner — called by Windows Task Scheduler / Linux Cron
Loops every SYNC_INTERVAL_MINUTES minutes automatically.
"""
import logging
import sys
import os
import time
import tracemalloc

# ── so imports like 'app.services...' work ──
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.sync.engine import run_sync
from app.config import settings

# ─────────────────────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("sync_engine.log", mode="a", encoding="utf-8"),
    ],
)
log = logging.getLogger("sync_runner")


if __name__ == "__main__":

    log.info(f"🔁 Sync runner started — every {settings.SYNC_INTERVAL_MINUTES} minute(s)")

    while True:
        # ── memory tracking ──
        tracemalloc.start()

        # ── run sync ──
        run_sync()

        # ── memory report ──
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        log.info(f"🧠 Memory CURRENT : {current / 1024 / 1024:.2f} MB")
        log.info(f"🧠 Memory PEAK    : {peak    / 1024 / 1024:.2f} MB")

        if peak / 1024 / 1024 > 300:
            log.warning("⚠️  Memory spike! PEAK exceeded 300MB — check upsert batch sizes")

        # ── sleep until next sync ──
        time.sleep(settings.SYNC_INTERVAL_MINUTES * 60)