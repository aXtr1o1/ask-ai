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
import uuid
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

# ─────────────────────────────────────────────────────────────────────────────
# ADDED: Queue Manager Config
# ─────────────────────────────────────────────────────────────────────────────
QUEUE_WAIT_TIMEOUT_SECONDS = 2     # max time a user waits in queue before getting stale data
QUEUE_POLL_INTERVAL        = 0.5    # how often (seconds) a waiting user checks if fresh data is ready
QUEUE_LOCK_EXPIRY          = 2     # Redis lock TTL (seconds) — dies exactly when user timeout hits, slot freed instantly
# ─────────────────────────────────────────────────────────────────────────────
# END ADDED: Queue Manager Config
# ─────────────────────────────────────────────────────────────────────────────


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


# ─────────────────────────────────────────────────────────────────────────────
# L1 — IN-MEMORY CACHE  (SESSION-SCOPED)
# ─────────────────────────────────────────────────────────────────────────────
class L1Cache:
    """
    Thread-safe in-process dict cache — SESSION-SCOPED.
    
    Each session has its own L1 namespace.
    Structure: {session_id: {key: {entry, expires_at, stored_at}}}
    
    This ensures that:
    - Browser A and Browser B for the same user have SEPARATE L1 caches
    - L1 is fast, private, session-local
    - L2 (Redis) remains shared across all sessions (as it should be)
    """

    def __init__(self):
        # NEW: session_id → {key → record}
        self._store: dict[str, dict[str, dict]] = {}

    # ── public ────────────────────────────────────────────────────────────────

    def get(self, session_id: str, key: str) -> tuple[Optional[Any], bool]:
        """
        Returns (entry, is_stale) for the given session.
        
        If session_id not in store → full miss (not present at all).
        """
        session_cache = self._store.get(session_id)
        if session_cache is None:
            return None, False  # Session has no L1 cache yet
        
        record = session_cache.get(key)
        if record is None:
            return None, False  # Key not in this session's cache
        
        is_stale = time.time() > record["expires_at"]
        if is_stale:
            logger.debug(
                "L1 | STALE session=%s key=%s (expired %.0fs ago)", 
                session_id, key, time.time() - record["expires_at"]
            )
        return record["entry"], is_stale

    def set(self, session_id: str, key: str, entry: Any, ttl: int = L1_TTL_SECONDS):
        """Store entry in this session's L1 cache."""
        now = time.time()
        
        # Initialize session cache if first time
        if session_id not in self._store:
            self._store[session_id] = {}
        
        self._store[session_id][key] = {
            "entry": entry,
            "expires_at": now + ttl,
            "stored_at": now,
        }
        logger.debug(
            "L1 | SET session=%s key=%s ttl=%ds rows=%d stored_at=%s", 
            session_id, key, ttl, _result_count(entry), now
        )

    def delete(self, session_id: str, key: str):
        """Remove key from this session's cache."""
        session_cache = self._store.get(session_id)
        if session_cache:
            session_cache.pop(key, None)

    # ── diagnostics ───────────────────────────────────────────────────────────

    def log_state(self, session_id: str = None):
        """
        Log L1 state.
        If session_id provided → log only that session.
        If None → log all sessions.
        """
        now = time.time()
        
        if session_id:
            # Log single session
            session_cache = self._store.get(session_id)
            if not session_cache:
                logger.info("L1 | STATE session=%s (empty)", session_id)
                return
            
            logger.info("L1 | STATE session=%s total_keys=%d", session_id, len(session_cache))
            for key, record in session_cache.items():
                remaining = max(0, record["expires_at"] - now)
                stale = time.time() > record["expires_at"]
                count = _result_count(record["entry"])
                stored_at = record.get("stored_at")
                stored_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stored_at)) if stored_at else "unknown"
                logger.info(
                    "L1 |   key=%-55s rows=%4d ttl_left=%5.0fs stale=%-5s stored_at=%s",
                    key, count, remaining, stale, stored_str,
                )
        else:
            # Log all sessions
            if not self._store:
                logger.info("L1 | STATE (empty - no sessions)")
                return
            
            logger.info("L1 | STATE total_sessions=%d", len(self._store))
            for sess_id, session_cache in self._store.items():
                logger.info("L1 |   session=%s keys=%d", sess_id, len(session_cache))
                for key, record in session_cache.items():
                    remaining = max(0, record["expires_at"] - now)
                    stale = time.time() > record["expires_at"]
                    count = _result_count(record["entry"])
                    stored_at = record.get("stored_at")
                    stored_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stored_at)) if stored_at else "unknown"
                    logger.info(
                        "L1 |     key=%-55s rows=%4d ttl_left=%5.0fs stale=%-5s stored_at=%s",
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
#  QUEUE MANAGER — FIFO Fresh-Data Priority with Timeout Fallback
# ─────────────────────────────────────────────────────────────────────────────
class QueueManager:
    """
    FIFO Queue layer that sits on top of L1/L2 stale handling.

    Purpose:
        When stale data is detected, instead of immediately returning stale data,
        users are placed in a FIFO queue to receive fresh data from the DB.
        Only if the user waits beyond QUEUE_WAIT_TIMEOUT_SECONDS do they get
        stale data — with a traffic_fallback signal so the LLM can inform them politely.

    Redis keys used (2 new keys per cache key):
        queue:{key}      → FIFO list of request_ids (RPUSH to join, LPOP when done)
        queue:{key}:lock → which request_id is currently fetching from DB

    The existing L2 data key ({key}) is reused as the fresh result store.
    When the lock holder finishes, it calls l2.set() — stale_flag reappears —
    all other waiting users detect this and exit the queue with fresh data.

    Return value:
        (data, is_traffic_fallback)
        is_traffic_fallback = True  → caller should signal LLM to be polite about stale data
        is_traffic_fallback = False → fresh data returned successfully
    """

    def __init__(self, redis_client):
        self.redis = redis_client

    def _queue_key(self, key: str) -> str:
        return f"queue:{key}"

    def _lock_key(self, key: str) -> str:
        return f"queue:{key}:lock"

    def wait_for_fresh_or_timeout(
    self,
    key: str,
    stale_data: Any,
    fetch_fn: Callable,
    l2: "L2Cache",
    l1: "L1Cache",
    session_id: str,  # 🆕 NEW: session_id parameter
) -> tuple[Any, bool]:
        
        """
        Main entry point for the queue layer.

        Steps:
            1. Generate a unique request_id and join the queue (RPUSH).
            2. Poll every QUEUE_POLL_INTERVAL seconds:
               a. Check if L2 stale_flag has reappeared → fresh data already stored by another user → grab it.
               b. Check if I am at the front of the queue AND lock is free → I fetch from DB.
            3. If QUEUE_WAIT_TIMEOUT_SECONDS exceeded → exit queue → return (stale_data, True).
            4. On DB fetch success → store in L2 + L1 → release lock → remove from queue → return (fresh_data, False).

        Returns:
            (data, is_traffic_fallback)
        """
        request_id  = str(uuid.uuid4())
        queue_key   = self._queue_key(key)
        lock_key    = self._lock_key(key)
        start_time  = time.time()

        # ── Join the FIFO queue ───────────────────────────────────────────────
        self.redis.rpush(queue_key, request_id)
        queue_len = self.redis.llen(queue_key)

        # 🆕 NEW: Get all queue members to show user who's waiting
        all_waiting = self.redis.lrange(queue_key, 0, -1)
        current_lock = self.redis.get(lock_key)

        logger.info(
            "QUEUE | JOINED  key=%s  request_id=%s  position=%d/%d",
            key, request_id[:8], queue_len, queue_len,  # Shows "position 3/3"
        )

        # 🆕 NEW: Show complete queue state when user joins
        logger.info("=" * 80)
        logger.info("📋 QUEUE STATE - Current Waiting List")
        logger.info("=" * 80)
        logger.info(f"Queue Key: {queue_key}")
        logger.info(f"Total Waiting: {queue_len} users")
        logger.info(f"Your Position: {queue_len} (just joined)")
        logger.info("")
        logger.info("Current Queue:")

        for i, req_id in enumerate(all_waiting, 1):
            is_you = "👈 YOU" if req_id == request_id else ""
            is_fetching = "🔴 FETCHING FROM DB" if req_id == current_lock else "⏳ WAITING"
            logger.info(f"  {i}. {req_id[:8]}... {is_fetching} {is_you}")

        logger.info("=" * 80)

        try:
            while True:
                elapsed = time.time() - start_time

                # ── Timeout check ─────────────────────────────────────────────
                # 10s is the TOTAL deadline per user — includes waiting in queue + DB fetch time
                # if 10s exceeded → user exits queue immediately → gets stale data with polite message
                if elapsed >= QUEUE_WAIT_TIMEOUT_SECONDS:
                    self._leave_queue(queue_key, request_id)   # clean exit — remove from queue
                    logger.warning(
                        "QUEUE | TIMEOUT  key=%s  request_id=%s  waited=%.1fs  → exited queue → returning stale data (traffic fallback)",
                        key, request_id, elapsed,
                    )
                    return stale_data, True   # is_traffic_fallback = True

                # ── Check if another user already refreshed L2 ────────────────
                # stale_flag reappearing means fresh data is now in L2
                stale_flag_ttl = self.redis.ttl(f"{key}{_STALE_SUFFIX}")
                if stale_flag_ttl >= 0:
                    raw = self.redis.get(key)
                    if raw:
                        fresh_entry = json.loads(raw)
                        count = _result_count(fresh_entry)
                        logger.info(
                            "QUEUE | FRESH DETECTED session=%s key=%s rows=%d",
                            session_id, key, count,
                        )
                        # Promote to THIS SESSION's L1
                        if count <= L1_SIZE_THRESHOLD:
                            l1.set(session_id, key, fresh_entry)  # 🆕 Pass session_id
                            logger.info("QUEUE | L1 PROMOTE session=%s key=%s", session_id, key)
                        self._leave_queue(queue_key, request_id)
                        return fresh_entry, False

                # ── Check if I'm first and lock is free ──────────────────────────
                front = self.redis.lindex(queue_key, 0)
                lock = self.redis.get(lock_key)

                if front == request_id and lock is None:
                    acquired = self.redis.set(lock_key, request_id, ex=QUEUE_LOCK_EXPIRY, nx=True)
                    if acquired:
                        logger.info("QUEUE | LOCK ACQUIRED session=%s key=%s", session_id, key)
                        try:
                            result = fetch_fn()
                            indexed = _wrap(result)
                            count = _result_count(indexed)

                            # Update L2 (shared)
                            l2.set(key, indexed)
                            logger.info("QUEUE | L2 UPDATED session=%s key=%s rows=%d", session_id, key, count)

                            # Update THIS SESSION's L1
                            if count <= L1_SIZE_THRESHOLD:
                                l1.set(session_id, key, indexed)  # 🆕 Pass session_id
                                logger.info("QUEUE | L1 UPDATED session=%s key=%s", session_id, key)
                            else:
                                l1.delete(session_id, key)  # 🆕 Pass session_id
                                logger.info("QUEUE | L1 EVICTED session=%s key=%s (too large)", session_id, key)

                            return indexed, False

                        except Exception as e:
                            logger.error("QUEUE | DB FETCH FAILED session=%s: %s", session_id, e)
                            return stale_data, True

                        finally:
                            self.redis.delete(lock_key)
                            self._leave_queue(queue_key, request_id)
               # ── Not my turn yet — log wait position and sleep ─────────────
               
                position = self._get_position(queue_key, request_id)
                current_queue_len = self.redis.llen(queue_key)

                # 🆕 NEW: Show updated queue state every 2 seconds (every 4th poll)
                # This avoids log spam while keeping user informed
                poll_count = int(elapsed / QUEUE_POLL_INTERVAL)
                if poll_count % 4 == 0:  # Every 2 seconds (0.5s * 4)
                    all_waiting = self.redis.lrange(queue_key, 0, -1)
                    current_lock = self.redis.get(lock_key)
                    
                    logger.info("")
                    logger.info("📊 QUEUE UPDATE - Still Waiting...")
                    logger.info(f"Your Position: {position}/{current_queue_len}")
                    logger.info(f"Time Elapsed: {elapsed:.1f}s / {QUEUE_WAIT_TIMEOUT_SECONDS}s")
                    logger.info(f"Current Queue ({current_queue_len} users):")
                    
                    for i, req_id in enumerate(all_waiting, 1):
                        is_you = "👈 YOU" if req_id == request_id else ""
                        is_fetching = "🔴 FETCHING" if req_id == current_lock else "⏳ WAITING"
                        logger.info(f"  {i}. {req_id[:8]}... {is_fetching} {is_you}")
                    logger.info("")

                # Keep the compact log for every poll
                logger.info(
                    "QUEUE | WAITING  position=%s/%s  elapsed=%.1fs / %ds  remaining_timeout=%.1fs",
                    position, current_queue_len, elapsed, QUEUE_WAIT_TIMEOUT_SECONDS,
                    QUEUE_WAIT_TIMEOUT_SECONDS - elapsed,
                )
                time.sleep(QUEUE_POLL_INTERVAL)

        except Exception as e:
            logger.error(
                "QUEUE | UNEXPECTED ERROR  key=%s  request_id=%s  error=%s  → falling back to stale",
                key, request_id, e, exc_info=True,
            )
            self._leave_queue(queue_key, request_id)
            return stale_data, True

    def _leave_queue(self, queue_key: str, request_id: str):
        """Remove this request_id from the queue (LREM removes all occurrences)."""
        self.redis.lrem(queue_key, 0, request_id)
        logger.info("QUEUE | LEFT QUEUE  queue_key=%s  request_id=%s", queue_key, request_id)

    def _get_position(self, queue_key: str, request_id: str) -> str:
        """Return 1-based position in queue for logging. Returns '?' if not found."""
        try:
            members = self.redis.lrange(queue_key, 0, -1)
            if request_id in members:
                return str(members.index(request_id) + 1)
        except Exception:
            pass
        return "?"
    
    # 🆕 NEW: Helper method to get queue summary
    def get_queue_summary(self, key: str) -> dict:
        """
        Return a dictionary with current queue state for logging/monitoring.
        
        Returns:
            {
                "queue_length": 3,
                "waiting_requests": ["req-abc", "req-def", "req-ghi"],
                "current_lock_holder": "req-abc" or None,
                "lock_ttl_remaining": 12 (seconds) or -2 (expired)
            }
        """
        queue_key = self._queue_key(key)
        lock_key = self._lock_key(key)
        
        return {
            "queue_length": self.redis.llen(queue_key),
            "waiting_requests": self.redis.lrange(queue_key, 0, -1),
            "current_lock_holder": self.redis.get(lock_key),
            "lock_ttl_remaining": self.redis.ttl(lock_key),
        }


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

    ADDED: Queue layer on stale hits.
        Instead of immediately returning stale data, users join a FIFO queue
        and wait up to QUEUE_WAIT_TIMEOUT_SECONDS for fresh data.
        Only on timeout do they receive stale data — flagged as is_traffic_fallback=True
        so the LLM can communicate politely about the traffic situation.
    """
    def __init__(self):
        self.l1 = L1Cache()
        self.l2 = L2Cache()
        self.queue = QueueManager(self.l2.client)

    def get_or_fetch(
        self,
        tool_name: str,
        user_id: str,
        session_id: str,  # 🆕 NEW: session_id parameter
        args: dict,
        fetch_fn: Callable,
    ) -> Any:
        """
        Synchronous cache-or-fetch with session-scoped L1.
        
        Pipeline:
        1. Check L1 for THIS SESSION (not global)
        2. Check L2 (Redis, shared across all sessions)
        3. Hit DB if both miss
        """
        key = _make_key(tool_name, user_id, args)

        logger.info(
            "CACHE | LOOKUP tool=%-8s user=%s session=%s key=%s",
            tool_name, user_id, session_id, key,
        )

        # ── Step 1: L1 Check (SESSION-SCOPED) ────────────────────────────────
        l1_entry, l1_stale = self.l1.get(session_id, key)  # 🆕 Pass session_id

        if l1_entry is not None:
            count = _result_count(l1_entry)
            if not l1_stale:
                logger.info(
                    "CACHE | L1 HIT (FRESH) tool=%-8s user=%s session=%s rows=%d → returning immediately",
                    tool_name, user_id, session_id, count,
                )
                self._log_pipeline("L1_FRESH")
                return l1_entry

            # L1 stale → enter queue
            logger.info(
                "CACHE | L1 HIT (STALE) tool=%-8s user=%s session=%s rows=%d → entering queue",
                tool_name, user_id, session_id, count,
            )
            self._log_pipeline("L1_STALE")
            self.log_queue_state()
            
            fresh_data, is_traffic_fallback = self.queue.wait_for_fresh_or_timeout(
                key=key,
                stale_data=l1_entry,
                fetch_fn=fetch_fn,
                l2=self.l2,
                l1=self.l1,
                session_id=session_id,  # 🆕 Pass session_id to queue
            )
            
            if is_traffic_fallback:
                logger.warning(
                    "CACHE | L1 STALE FALLBACK tool=%-8s user=%s session=%s",
                    tool_name, user_id, session_id,
                )
            else:
                logger.info(
                    "CACHE | L1 STALE RESOLVED tool=%-8s user=%s session=%s",
                    tool_name, user_id, session_id,
                )
            return {"data": fresh_data, "is_traffic_fallback": is_traffic_fallback}

        logger.info("CACHE | L1 MISS tool=%-8s user=%s session=%s", tool_name, user_id, session_id)

        # ── Step 2: L2 Check (SHARED ACROSS SESSIONS) ────────────────────────
        l2_entry, l2_stale = self.l2.get(key)  # L2 key is user-scoped, not session-scoped

        if l2_entry is not None:
            count = _result_count(l2_entry)
            if not l2_stale:
                logger.info(
                    "CACHE | L2 HIT (FRESH) tool=%-8s user=%s session=%s rows=%d",
                    tool_name, user_id, session_id, count,
                )
                # Promote to THIS SESSION's L1
                if count <= L1_SIZE_THRESHOLD:
                    self.l1.set(session_id, key, l2_entry)  # 🆕 Pass session_id
                    logger.info(
                        "CACHE | L1 PROMOTE tool=%-8s user=%s session=%s rows=%d",
                        tool_name, user_id, session_id, count,
                    )
                self._log_pipeline("L2_FRESH")
                return l2_entry

            # L2 stale → enter queue
            logger.info(
                "CACHE | L2 HIT (STALE) tool=%-8s user=%s session=%s rows=%d → entering queue",
                tool_name, user_id, session_id, count,
            )
            self._log_pipeline("L2_STALE")
            self.log_queue_state()
            
            fresh_data, is_traffic_fallback = self.queue.wait_for_fresh_or_timeout(
                key=key,
                stale_data=l2_entry,
                fetch_fn=fetch_fn,
                l2=self.l2,
                l1=self.l1,
                session_id=session_id,  # 🆕 Pass session_id to queue
            )
            
            if is_traffic_fallback:
                logger.warning(
                    "CACHE | L2 STALE FALLBACK tool=%-8s user=%s session=%s",
                    tool_name, user_id, session_id,
                )
            else:
                logger.info(
                    "CACHE | L2 STALE RESOLVED tool=%-8s user=%s session=%s",
                    tool_name, user_id, session_id,
                )
            return {"data": fresh_data, "is_traffic_fallback": is_traffic_fallback}

        logger.info("CACHE | L2 MISS tool=%-8s user=%s session=%s", tool_name, user_id, session_id)

        # ── Step 3: DB Hit ────────────────────────────────────────────────────
        logger.info("CACHE | DB HIT tool=%-8s user=%s session=%s", tool_name, user_id, session_id)
        result = fetch_fn()
        indexed = _wrap(result)
        count = _result_count(indexed)

        # Store in L2 (shared across sessions)
        self.l2.set(key, indexed)
        logger.info("CACHE | L2 STORED tool=%-8s user=%s session=%s", tool_name, user_id, session_id)

        # Store in THIS SESSION's L1
        if count <= L1_SIZE_THRESHOLD:
            self.l1.set(session_id, key, indexed)  # 🆕 Pass session_id
            logger.info(
                "CACHE | L1 STORED tool=%-8s user=%s session=%s rows=%d",
                tool_name, user_id, session_id, count,
            )

        self._log_pipeline("DB_HIT")
        self._log_both_states(session_id)  # 🆕 Pass session_id for logging

        return indexed

    def _log_both_states(self, session_id: str):
        """Log L1 (for this session) and L2 (global)."""
        self.l1.log_state(session_id)
        self.l2.log_state()

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
            "L1_STALE":  ["⚠️  L1 → STALE HIT",   "⏭  L2 → SKIPPED",    "🔄 DB → QUEUE WAIT"],
            "L2_FRESH":  ["❌ L1 → MISS",          "✅ L2 → FRESH HIT",   "⏭  DB → SKIPPED"  ],
            "L2_STALE":  ["❌ L1 → MISS",          "⚠️  L2 → STALE HIT",  "🔄 DB → QUEUE WAIT"],
            "DB_HIT":    ["❌ L1 → MISS",          "❌ L2 → MISS",        "🔴 DB → HIT & CACHED"],
        }
        steps = STAGES.get(stage, [])
        logger.info("CACHE | PIPELINE  %s  |  %s  |  %s", *steps)
        

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
                "⚠️  STALE — queue triggered" if is_stale else "✅ FRESH — serving from memory",
            )

    # 🆕 NEW: Log all active queues system-wide
    def log_queue_state(self, pattern: str = "queue:*"):
        """
        Log all active queues - useful for debugging and monitoring.
        Shows which queues exist, how many users waiting, who has locks.
        """
        try:
            # Find all queue keys (exclude lock keys)
            all_keys = self.l2.client.keys(pattern)
            queue_keys = [k for k in all_keys if not k.endswith(':lock')]
            
            if not queue_keys:
                logger.info("🎫 QUEUE STATE | No active queues")
                return
            
            logger.info("=" * 80)
            logger.info(f"🎫 ACTIVE QUEUES | Total: {len(queue_keys)}")
            logger.info("=" * 80)
            
            for queue_key in queue_keys:
                # Get queue details
                members = self.l2.client.lrange(queue_key, 0, -1)
                queue_len = len(members)
                lock_key = f"{queue_key}:lock"
                lock_holder = self.l2.client.get(lock_key)
                lock_ttl = self.l2.client.ttl(lock_key)
                
                logger.info(f"\n📋 Queue: {queue_key}")
                logger.info(f"   Length: {queue_len} users waiting")
                
                if lock_holder:
                    logger.info(f"   🔒 Lock: HELD by {lock_holder[:8]}... (TTL: {lock_ttl}s)")
                else:
                    logger.info(f"   🔓 Lock: FREE (no one fetching)")
                
                logger.info(f"   Waiting list:")
                for i, req_id in enumerate(members, 1):
                    status = "🔴 FETCHING" if req_id == lock_holder else "⏳ WAITING"
                    logger.info(f"      {i}. {req_id[:8]}... {status}")
            
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"🎫 QUEUE STATE LOG ERROR: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Global instance
# ─────────────────────────────────────────────────────────────────────────────
cache_manager = CacheManager()
