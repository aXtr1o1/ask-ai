"""
Redis Service — 2-Layer Cache (L1 In-Memory + L2 Redis)
========================================================
L1 = In-Memory  (per user, fast, small results only)
L2 = Redis      (per user, shared across instances, all results)

Key format  :  {user_id}:{tool_name}:{canonical_args}
Data TTL    :  L1_TTL_SECONDS / L2_TTL_SECONDS  (default 4 min)
Stale TTL   :  Data is NEVER deleted on expiry.
               Instead, a "stale" flag key is set with the TTL.
               When the flag expires → data is stale → background refresh.
               User always gets data immediately (zero latency on expiry).

The system checks L1 first, then L2, and finally the database—always returning data as fast as possible while refreshing stale data in the background.


"""

import asyncio
import json
import logging
import time
from typing import Any, Callable, Optional

import redis

from app.config import settings

# ─────────────────────────────────────────────────────────────────────────────
# LOGGER
# ─────────────────────────────────────────────────────────────────────────────
logger = logging.getLogger("redis_service")
logger.setLevel(logging.INFO)
_ch = logging.StreamHandler()
_ch.setFormatter(logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s"))
if not logger.handlers:
    logger.addHandler(_ch)


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG  (edit here whenever needed)
# ─────────────────────────────────────────────────────────────────────────────
L1_TTL_SECONDS   = settings.L1_TTL_SECONDS   # 2 min — how long data stays "fresh" in memory
L2_TTL_SECONDS   = settings.L2_TTL_SECONDS   # 2 min — how long data stays "fresh" in Redis
L1_SIZE_THRESHOLD = settings.L1_SIZE_THRESHOLD   # store in L1 only when len(p_list) <= this value as of now 50

# Stale key suffix — a cheap flag key whose expiry drives the refresh trigger
#simple this for to check whether the ttl is expired or not .
_STALE_SUFFIX = ":stale_flag"


# this function is used to make the key , so that we can  use the key comparison method for retrival of data form the memory 

def _make_key(tool_name: str, user_id: str, args: dict) -> str:
    """
    Deterministic cache key: {user_id}:{tool_name}:{canonical_args}
    Pagination / identity args (user_id, limit, offset) are excluded so that
    e.g. limit=10 and limit=None map to the same cache entry.
    """
    EXCLUDE_KEYS = {"user_id"}
    args_clean = {
        k: (v.lower() if isinstance(v, str) else v)
        for k, v in args.items()
        if k not in EXCLUDE_KEYS and v is not None
    }
    canonical = json.dumps(args_clean, sort_keys=True)
    return f"{user_id}:{tool_name}:{canonical}"

#calcuating the length of the data so that i seted the threshold  to allow whether the data  can be allowed in the memory or not

def _result_count(entry: Any) -> int:
    """Return number of rows in an entry (handles both indexed-dict and raw formats)."""
    if isinstance(entry, dict):
        if all(k.isdigit() for k in entry.keys()):
            return len(entry)
        return len(entry.get("p_list", []))
    if isinstance(entry, list):
        return len(entry)
    return 999

#convertd the data p[]={(....),(...)}into indexed format 
def _wrap(result: Any) -> dict:
    """Convert raw DB result → indexed format  {"1": row, "2": row, ...}"""
    if isinstance(result, dict):
        p_list = result.get("p_list", [])
    elif isinstance(result, list):
        p_list = result
    else:
        return {}
    return {str(i + 1): row for i, row in enumerate(p_list)}


# L1 — IN-MEMORY CACHE  (stale-while-revalidate variant)
# if the ttl expries(whihc meeans the stale is true) then the db gets triggerd and update the new data 
#but the user gets the current data present in the memory only . 


class L1Cache:
    """
    Thread-safe in-process dict cache.

    Each record holds:
        entry      — the indexed data dict
        expires_at — unix timestamp after which the entry is "stale"
                     (but still returned; a background refresh is triggered)
    """

    def __init__(self):
        self._store: dict[str, dict] = {}

    # ── public ────────────────────────────────────────────────────────────────

    def get(self, key: str) -> tuple[Optional[Any], bool]:
        """
        Returns (entry, is_stale).
        entry    = None  → cache miss (not present at all)
        is_stale = True  → entry exists but TTL has expired; caller should refresh
        """
        record = self._store.get(key)
        if record is None:
            return None, False
        is_stale = time.time() > record["expires_at"]
        if is_stale:
            logger.debug("L1 | STALE key=%s  (expired %.0fs ago)", key, time.time() - record["expires_at"])
        return record["entry"], is_stale

    def set(self, key: str, entry: Any, ttl: int = L1_TTL_SECONDS):
        now = time.time()
        self._store[key] = {
            "entry":      entry,
            "expires_at": now + ttl,
            "stored_at":  now,    # timestamp saved in memory — updated every time data is refreshed
        }
        logger.debug("L1 | SET key=%s  ttl=%ds  rows=%d  stored_at=%s", key, ttl, _result_count(entry), now)

    def delete(self, key: str):
        self._store.pop(key, None)

    # ── diagnostics ───────────────────────────────────────────────────────────
    #for logging purpose 
    def log_state(self):
        now = time.time()
        if not self._store:
            logger.info("L1 | STATE  (empty)")
            return
        logger.info("L1 | STATE  total_keys=%d", len(self._store))
        for key, record in self._store.items():
            remaining = max(0, record["expires_at"] - now)
            stale     = time.time() > record["expires_at"]
            count     = _result_count(record["entry"])
            stored_at  = record.get("stored_at")
            # convert unix timestamp to readable format
            stored_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stored_at)) if stored_at else "unknown"
            logger.info(
                "L1 |   key=%-55s  rows=%4d  ttl_left=%5.0fs  stale=%-5s  stored_at=%s",
                key, count, remaining, stale, stored_str,
            )


# ─────────────────────────────────────────────────────────────────────────────
# L2 — REDIS CACHE  (stale-while-revalidate variant)
# ─────────────────────────────────────────────────────────────────────────────
class L2Cache:
    #If you store data with a normal Redis TTL, when TTL expires — data is deleted. User gets nothing. 
    # That is what we want to avoid. for that we use this method |

    """
    Redis cache.

    Strategy: two Redis keys per logical cache entry.
        data_key   = "{key}"         — the actual payload, persists forever
        stale_key  = "{key}:stale_flag" — a cheap TTL flag; expiry = stale signal

    get() checks stale_key TTL to determine freshness without removing data.
    set() stores data_key (no expiry) + stale_key (with TTL).
    """

    def __init__(self):
        try:
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                decode_responses=True,
                username=settings.REDIS_USERNAME,
                password=settings.REDIS_PASSWORD,
            )
            self.client.ping()
            logger.info("L2 | Redis connection OK  host=%s  port=%s", settings.REDIS_HOST, settings.REDIS_PORT)
        except Exception as e:
            logger.critical("L2 | Redis connection FAILED: %s", e, exc_info=True)
            raise

    # ── public ────────────────────────────────────────────────────────────────

    def get(self, key: str) -> tuple[Optional[Any], bool]:
        """
        Returns (entry, is_stale).
        entry    = None  → cache miss
        is_stale = True  → data exists but stale_flag TTL expired; caller refreshes
        """
        try:
            raw = self.client.get(key)
            if raw is None:
                return None, False                      # full miss — data never stored

            entry     = json.loads(raw)
            stale_ttl = self.client.ttl(f"{key}{_STALE_SUFFIX}")
            # ttl == -2 → key missing (flag expired) → stale
            # ttl == -1 → key exists, no expiry (should not happen)
            # ttl >=  0 → key exists, still fresh
            is_stale = stale_ttl == -2
            if is_stale:
                logger.debug("L2 | STALE  key=%s  (stale_flag missing → TTL exceeded)", key)
            return entry, is_stale
        except Exception as e:
            logger.error("L2 | GET error  key=%s  error=%s", key, e)
            return None, False

    def set(self, key: str, entry: Any, ttl: int = L2_TTL_SECONDS):
        """Store data (no expiry) + stale flag (TTL expiry) + stored_at timestamp (no expiry, always visible in Redis)."""
        try:
            now = time.time()
            self.client.set(key, json.dumps(entry))                        # data — never expires
            self.client.set(f"{key}{_STALE_SUFFIX}", "1", ex=ttl)         # flag — expires after TTL
            self.client.set(f"{key}:stored_at", str(now))                  # timestamp — never expires, always visible in Redis
            logger.debug("L2 | SET key=%s  ttl=%ds  rows=%d  stored_at=%s", key, ttl, _result_count(entry), now)
        except Exception as e:
            logger.error("L2 | SET error  key=%s  error=%s", key, e)

    # ── diagnostics ───────────────────────────────────────────────────────────

    def log_state(self, pattern: str = "*"):
        """Log all data keys (excluding stale-flag keys) with freshness info."""
        try:
            all_keys  = self.client.keys(pattern)
            # exclude stale_flag keys and stored_at keys — show only actual data keys
            data_keys = [k for k in all_keys if not k.endswith(_STALE_SUFFIX) and not k.endswith(":stored_at")]
            if not data_keys:
                logger.info("L2 | STATE  (empty)")
                return
            logger.info("L2 | STATE  total_keys=%d", len(data_keys))
            for key in data_keys:
                raw = self.client.get(key)
                if not raw:
                    continue
                entry     = json.loads(raw)
                count     = _result_count(entry)
                stale_ttl  = self.client.ttl(f"{key}{_STALE_SUFFIX}")
                is_stale   = stale_ttl == -2
                ttl_str    = f"{stale_ttl}s" if stale_ttl >= 0 else "EXPIRED"
                # read the stored_at timestamp from Redis and convert to readable format
                stored_raw = self.client.get(f"{key}:stored_at")
                stored_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(stored_raw))) if stored_raw else "unknown"
                logger.info(
                    "L2 |   key=%-55s  rows=%4d  ttl_left=%10s  stale=%-5s  stored_at=%s",
                    key, count, ttl_str, is_stale, stored_str,
                )
        except Exception as e:
            logger.error("L2 | STATE log error: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# CACHE MANAGER
# ─────────────────────────────────────────────────────────────────────────────
class CacheManager:
    """
    Orchestrates L1 → L2 → DB with stale-while-revalidate on both layers.

    Stale-while-revalidate behaviour:
        When a key's TTL has expired, the *existing* (stale) data is returned
        immediately to the caller so there is zero additional latency.
        A background asyncio task is then fired to hit the DB, update L2,
        and re-populate L1 — so the *next* request gets fresh data.
    """

    def __init__(self):
        self.l1 = L1Cache()
        self.l2 = L2Cache()

    # ── main entry point ──────────────────────────────────────────────────────

    def get_or_fetch(
        self,
        tool_name: str,
        user_id: str,
        args: dict,
        fetch_fn: Callable,
    ) -> Any:
        """
        Synchronous cache-or-fetch.  Returns indexed entry dict.
        Background refreshes are scheduled via asyncio when data is stale.
        """
        key = _make_key(tool_name, user_id, args)

        logger.info(
            "CACHE | LOOKUP  tool=%-8s  user=%s  key=%s",
            tool_name, user_id, key,
        )

        # ── Step 1: L1 Check ─────────────────────────────────────────────────
        l1_entry, l1_stale = self.l1.get(key)

        if l1_entry is not None:
            count = _result_count(l1_entry)
            if not l1_stale:
                logger.info(
                    "CACHE | L1 HIT (FRESH)  tool=%-8s  user=%s  rows=%d  → returning immediately, DB skipped",
                    tool_name, user_id, count,
                )
                self._log_pipeline("L1_FRESH")
                return l1_entry

            # L1 stale — serve immediately, background refresh
            logger.info(
                "CACHE | L1 HIT (STALE)  tool=%-8s  user=%s  rows=%d  → serving stale data, background refresh triggered",
                tool_name, user_id, count,
            )
            self._log_pipeline("L1_STALE")
            self._schedule_refresh(key, tool_name, user_id, fetch_fn)
            return l1_entry

        logger.info("CACHE | L1 MISS  tool=%-8s  user=%s", tool_name, user_id)

        # ── Step 2: L2 Check ─────────────────────────────────────────────────
        l2_entry, l2_stale = self.l2.get(key)

        if l2_entry is not None:
            count = _result_count(l2_entry)
            if not l2_stale:
                logger.info(
                    "CACHE | L2 HIT (FRESH)  tool=%-8s  user=%s  rows=%d  → returning from Redis",
                    tool_name, user_id, count,
                )
                # Promote to L1 if small enough
                if count <= L1_SIZE_THRESHOLD:
                    self.l1.set(key, l2_entry)
                    logger.info(
                        "CACHE | L1 PROMOTE  tool=%-8s  user=%s  rows=%d  (threshold=%d)",
                        tool_name, user_id, count, L1_SIZE_THRESHOLD,
                    )
                else:
                    logger.info(
                        "CACHE | L1 PROMOTE SKIPPED  tool=%-8s  user=%s  rows=%d > threshold=%d",
                        tool_name, user_id, count, L1_SIZE_THRESHOLD,
                    )
                self._log_pipeline("L2_FRESH")
                return l2_entry

            # L2 stale — serve immediately, background refresh
            logger.info(
                "CACHE | L2 HIT (STALE)  tool=%-8s  user=%s  rows=%d  → serving stale data, background refresh triggered",
                tool_name, user_id, count,
            )
            self._log_pipeline("L2_STALE")
            self._schedule_refresh(key, tool_name, user_id, fetch_fn)
            return l2_entry

        logger.info("CACHE | L2 MISS  tool=%-8s  user=%s", tool_name, user_id)

        # ── Step 3: DB Hit ────────────────────────────────────────────────────
        logger.info(
            "CACHE | DB HIT  tool=%-8s  user=%s  → calling endpoint now",
            tool_name, user_id,
        )
        result  = fetch_fn()
        indexed = _wrap(result)
        count   = _result_count(indexed)
        logger.info(
            "CACHE | DB RESPONSE  tool=%-8s  user=%s  rows=%d",
            tool_name, user_id, count,
        )

        # Store L2 (always)
        self.l2.set(key, indexed)
        logger.info("CACHE | L2 STORED  tool=%-8s  user=%s  ttl=%ds", tool_name, user_id, L2_TTL_SECONDS)

        # Store L1 (only if small)
        if count <= L1_SIZE_THRESHOLD:
            self.l1.set(key, indexed)
            logger.info(
                "CACHE | L1 STORED  tool=%-8s  user=%s  ttl=%ds  rows=%d  (threshold=%d)",
                tool_name, user_id, L1_TTL_SECONDS, count, L1_SIZE_THRESHOLD,
            )
        else:
            logger.info(
                "CACHE | L1 STORE SKIPPED  tool=%-8s  user=%s  rows=%d > threshold=%d",
                tool_name, user_id, count, L1_SIZE_THRESHOLD,
            )

        self._log_pipeline("DB_HIT")
        self._log_both_states()

        return indexed

    # ── background refresh ────────────────────────────────────────────────────

    def _schedule_refresh(self, key: str, tool_name: str, user_id: str, fetch_fn: Callable):
        """
        Fire-and-forget asyncio task.  Updates L2 and L1 without blocking the caller.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._background_refresh(key, tool_name, user_id, fetch_fn))
                logger.info(
                    "CACHE | BG REFRESH SCHEDULED  tool=%-8s  user=%s  key=%s",
                    tool_name, user_id, key,
                )
            else:
                logger.warning(
                    "CACHE | BG REFRESH SKIPPED (no running loop)  tool=%s  user=%s",
                    tool_name, user_id,
                )
        except RuntimeError:
            logger.warning(
                "CACHE | BG REFRESH SKIPPED (RuntimeError)  tool=%s  user=%s",
                tool_name, user_id,
            )

    async def _background_refresh(self, key: str, tool_name: str, user_id: str, fetch_fn: Callable):
        """Async task: hits DB, stores fresh data in L2 and L1."""
        try:
            logger.info("CACHE | BG REFRESH START  tool=%-8s  user=%s  key=%s", tool_name, user_id, key)
            result  = await asyncio.to_thread(fetch_fn)
            indexed = _wrap(result)
            count   = _result_count(indexed)

            self.l2.set(key, indexed)
            logger.info("CACHE | BG REFRESH L2 UPDATED  tool=%-8s  user=%s  rows=%d", tool_name, user_id, count)

            if count <= L1_SIZE_THRESHOLD:
                self.l1.set(key, indexed)
                logger.info("CACHE | BG REFRESH L1 UPDATED  tool=%-8s  user=%s  rows=%d", tool_name, user_id, count)
            else:
                # Data too large for L1 — evict stale L1 entry if present
                self.l1.delete(key)
                logger.info(
                    "CACHE | BG REFRESH L1 EVICTED (too large)  tool=%-8s  user=%s  rows=%d > threshold=%d",
                    tool_name, user_id, count, L1_SIZE_THRESHOLD,
                )

            logger.info("CACHE | BG REFRESH COMPLETE  tool=%-8s  user=%s", tool_name, user_id)
        except Exception as e:
            logger.error("CACHE | BG REFRESH FAILED  tool=%s  user=%s  error=%s", tool_name, user_id, e, exc_info=True)

    # ── pipeline log ──────────────────────────────────────────────────────────

    def _log_pipeline(self, stage: str):
        STAGES = {
            "L1_FRESH":  ["✅ L1 → FRESH HIT",   "⏭  L2 → SKIPPED",    "⏭  DB → SKIPPED"  ],
            "L1_STALE":  ["⚠️  L1 → STALE HIT",   "⏭  L2 → SKIPPED",    "⏭  DB → BG REFRESH"],
            "L2_FRESH":  ["❌ L1 → MISS",          "✅ L2 → FRESH HIT",   "⏭  DB → SKIPPED"  ],
            "L2_STALE":  ["❌ L1 → MISS",          "⚠️  L2 → STALE HIT",  "⏭  DB → BG REFRESH"],
            "DB_HIT":    ["❌ L1 → MISS",          "❌ L2 → MISS",        "🔴 DB → HIT & CACHED"],
        }
        steps = STAGES.get(stage, [])
        logger.info("CACHE | PIPELINE  %s  |  %s  |  %s", *steps)

    def _log_both_states(self):
        # prints the current in-memory (L1) state — so you can see what is stored in memory right now
        self._log_l1_memory()
        self.l1.log_state()
        self.l2.log_state()

    def _log_l1_memory(self):
        # detailed view of every record sitting in L1 in-memory right now
        # shows the key, how many rows, ttl remaining, and whether it is stale or fresh
        store = self.l1._store
        now   = time.time()
        if not store:
            logger.info("L1 MEMORY | (empty — nothing stored in memory right now)")
            return
        logger.info("L1 MEMORY | total_entries=%d", len(store))
        for key, record in store.items():
            remaining = record["expires_at"] - now
            is_stale  = remaining < 0
            count     = _result_count(record["entry"])
            # shows each key with its row count, exact ttl left, and stale status
            stored_at  = record.get("stored_at")
            # convert unix timestamp to readable format for easy reading
            stored_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stored_at)) if stored_at else "unknown"
            logger.info(
                "L1 MEMORY |   key=%-55s  rows=%4d  ttl_left=%7.1fs  stale=%-5s  stored_at=%s  status=%s",
                key,
                count,
                max(0, remaining),
                is_stale,
                stored_str,
                "⚠️  STALE — bg refresh will trigger" if is_stale else "✅ FRESH — serving from memory",
            )


# ─────────────────────────────────────────────────────────────────────────────
# Global instance
# ─────────────────────────────────────────────────────────────────────────────
cache_manager = CacheManager()