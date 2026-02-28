"""
Standalone sync runner — called by Windows Task Scheduler / Linux Cron
Zero changes to sync_service.py — just calls run_sync() and measures memory
"""
import logging
import sys
import os
import tracemalloc

# ── so imports like 'app.services...' work ──
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.sync_service import run_sync

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
log = logging.getLogger("sync_engine")


if __name__ == "__main__":

    # ── start memory tracking ──
    tracemalloc.start()
    log.info("🧠 Memory tracking started")

    # ── run sync ──
    run_sync()

    # ── measure memory after sync ──
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    log.info(f"🧠 Memory CURRENT : {current / 1024 / 1024:.2f} MB")
    log.info(f"🧠 Memory PEAK    : {peak    / 1024 / 1024:.2f} MB")

    if peak / 1024 / 1024 > 300:
        log.warning(f"⚠️  Memory spike detected! PEAK exceeded 300MB — check upsert batch sizes")