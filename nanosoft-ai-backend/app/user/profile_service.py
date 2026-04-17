"""
user/profile_service.py
────────────────────────
User profile usage tracking — credits, tokens, audio, graphs, requests.

UPDATE-ONLY behavior:
    This file NEVER inserts new rows into user_profile.
    Rows must exist before these functions are called.
    If a row doesn't exist, we log a warning and skip silently.

Why update-only:
    User profiles are created by a separate admin/onboarding process.
    The chatbot only tracks usage — it doesn't create users.

Functions:
    get_credits_remaining()            → check if user has credits left (gate check)
    get_graph_count_and_limit()        → check if user has graph credits left
    update_usage_if_exists()           → decrement credits + increment all counters
    consume_audio_seconds_if_available → atomic audio credit check + consume
    get_user_usage_stats()             → full stats including 7-day history
    update_daily_history()             → append today's usage to usage_history table
"""

import logging
from app.api.database.postgres_client import get_pool

logger = logging.getLogger("user.profile_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(ch)


def get_credits_remaining(name: str) -> int | None:
    """
    Return credits_remaining for an existing user.

    Used as a gate check before processing any query.
    If credits_remaining == 0, query is blocked with an upgrade message.

    Returns:
        int credits_remaining, or None if user row not found
    """
    if not name:
        raise ValueError("name is required")

    logger.info("[PROFILE] Checking credits | name=%s", name)

    conn = get_pool()
    conn.rollback()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT credits_remaining FROM user_profile WHERE name = %s",
            (name,),
        )
        row = cur.fetchone()
        if not row:
            logger.warning("[PROFILE] user_profile missing for name=%s — credits check skipped", name)
            return None

        credits = int(row[0] or 0)
        logger.info("[PROFILE] Credits remaining | name=%s | credits=%d", name, credits)
        return credits


def get_graph_count_and_limit(name: str) -> tuple[int, int] | None:
    """
    Return (graph_count, graph_limit) for an existing user.

    Used as a gate check before graph queries.
    If graph_count >= graph_limit, graph query is blocked.

    Returns:
        (graph_count, graph_limit) tuple, or None if user row not found
    """
    if not name:
        raise ValueError("name is required")

    logger.info("[PROFILE] Checking graph credits | name=%s", name)

    conn = get_pool()
    conn.rollback()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT graph_count, graph_limit FROM user_profile WHERE name = %s",
            (name,),
        )
        row = cur.fetchone()
        if not row:
            logger.warning("[PROFILE] user_profile missing for name=%s — graph check skipped", name)
            return None

        graph_count = int(row[0] or 0)
        graph_limit = int(row[1] or 0)
        logger.info("[PROFILE] Graph usage | name=%s | count=%d | limit=%d", name, graph_count, graph_limit)
        return graph_count, graph_limit


def update_usage_if_exists(
    *,
    name:                str,
    tokens_used_delta:   int = 0,
    request_delta:       int = 1,
    graph_delta:         int = 0,
    credits_per_request: int = 1,
    audio_seconds_delta: int = 0,
) -> None:
    """
    Atomically increment all usage counters for an existing user.

    What gets updated:
        request_count     += request_delta
        graph_count       += graph_delta
        audio_seconds     += audio_seconds_delta
        tokens_used       += tokens_used_delta
        credits_used      += credits_per_request * request_delta
        credits_remaining  = MAX(credits_limit - credits_used, 0)  ← always recalculated

    Called after every successful query response.
    Skips silently if user row doesn't exist.
    """
    if not name:
        raise ValueError("name is required")

    # Normalize all deltas to int to prevent type errors
    tokens_used_delta   = int(tokens_used_delta   or 0)
    request_delta       = int(request_delta       or 0)
    graph_delta         = int(graph_delta         or 0)
    credits_per_request = int(credits_per_request or 0)
    audio_seconds_delta = int(audio_seconds_delta or 0)

    logger.info(
        "[PROFILE] Updating usage | name=%s | requests=%d | tokens=%d | graphs=%d | audio=%ds | credits=%d",
        name, request_delta, tokens_used_delta, graph_delta, audio_seconds_delta,
        credits_per_request * request_delta,
    )

    conn = get_pool()
    conn.rollback()

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE user_profile
            SET
                request_count     = request_count + %(request_delta)s,
                graph_count       = graph_count + %(graph_delta)s,
                audio_seconds     = audio_seconds + %(audio_seconds_delta)s,
                tokens_used       = tokens_used + %(tokens_used_delta)s,
                credits_used      = credits_used + %(credits_delta)s,
                credits_remaining = GREATEST(credits_limit - (credits_used + %(credits_delta)s), 0),
                last_request_at   = NOW(),
                updated_at        = NOW()
            WHERE name = %(name)s
            """,
            {
                "name":               name,
                "tokens_used_delta":  tokens_used_delta,
                "request_delta":      request_delta,
                "graph_delta":        graph_delta,
                "audio_seconds_delta":audio_seconds_delta,
                "credits_delta":      credits_per_request * request_delta,
            },
        )

        if cur.rowcount == 0:
            logger.warning("[PROFILE] user_profile missing for name=%s — no update applied", name)
            conn.rollback()
            return

    conn.commit()
    logger.info("✅ [PROFILE] Usage updated | name=%s", name)


def consume_audio_seconds_if_available(
    *,
    name:                str,
    audio_seconds_delta: int,
) -> bool | None:
    """
    Atomically consume audio credits if user has enough remaining.

    Why atomic:
        We check AND update in one SQL statement to prevent race conditions.
        Two concurrent requests cannot both succeed if only one credit remains.

    Returns:
        True   → credits consumed successfully
        False  → insufficient audio credits
        None   → user not found or columns missing (skip silently)
    """
    if not name:
        raise ValueError("name is required")

    audio_seconds_delta = int(audio_seconds_delta or 0)
    if audio_seconds_delta <= 0:
        logger.warning("[PROFILE] audio_seconds_delta <= 0 for name=%s — skipping", name)
        return None

    logger.info("[PROFILE] Consuming audio credits | name=%s | delta=%ds", name, audio_seconds_delta)

    conn = get_pool()
    conn.rollback()

    with conn.cursor() as cur:
        try:
            # Atomic check + update: only succeeds if audio_seconds + delta <= audio_limit
            cur.execute(
                """
                UPDATE user_profile
                SET
                    audio_seconds = audio_seconds + %(delta)s,
                    updated_at = NOW()
                WHERE name = %(name)s
                  AND audio_seconds + %(delta)s <= audio_limit
                """,
                {"name": name, "delta": audio_seconds_delta},
            )
        except Exception as e:
            logger.warning("[PROFILE] Audio consume failed (missing columns?) | name=%s | error=%s", name, str(e)[:200])
            conn.rollback()
            return None

        if cur.rowcount and cur.rowcount > 0:
            conn.commit()
            logger.info("✅ [PROFILE] Audio credits consumed | name=%s | delta=%ds", name, audio_seconds_delta)
            return True

        # rowcount == 0 → either out of credits or user missing
        # Check which one it is
        cur.execute(
            "SELECT audio_limit, audio_seconds FROM user_profile WHERE name = %s",
            (name,),
        )
        row = cur.fetchone()

        if not row:
            logger.warning("[PROFILE] user_profile missing for name=%s — audio check skipped", name)
            conn.rollback()
            return None

        audio_limit        = int(row[0] or 0)
        audio_seconds_used = int(row[1] or 0)

        if audio_seconds_used + audio_seconds_delta > audio_limit:
            logger.info(
                "⛔ [PROFILE] Audio credits exhausted | name=%s | used=%ds | delta=%ds | limit=%ds",
                name, audio_seconds_used, audio_seconds_delta, audio_limit,
            )
            conn.rollback()
            return False

        # Something else prevented update — allow as fallback
        logger.warning("[PROFILE] Audio consume did not apply but no exhaustion detected | name=%s", name)
        conn.rollback()
        return None


def get_user_usage_stats(external_user_id: str, name: str) -> dict:
    """
    Return full usage statistics for a user including 7-day history.

    Used by GET /api/usage/{external_user_id}/{user_name} endpoint.

    Returns dict with:
        - All counters from user_profile (credits, tokens, audio, graphs, requests)
        - 7-day history from usage_history table (for trend charts)
        - tokens_remaining calculated as max(token_limit - tokens_used, 0)
    """
    if not external_user_id or not name:
        raise ValueError("external_user_id and name are required")

    logger.info("[PROFILE] Fetching usage stats | external_user_id=%s | name=%s", external_user_id, name)

    conn = get_pool()
    conn.rollback()

    with conn.cursor() as cur:
        # Query 1: current totals from user_profile
        cur.execute(
            """
            SELECT
                credits_limit, credits_used, credits_remaining,
                audio_seconds, audio_limit,
                graph_count, graph_limit,
                request_count, request_limit,
                tokens_used, token_limit
            FROM user_profile
            WHERE external_user_id = %s AND name = %s
            LIMIT 1
            """,
            (external_user_id, name)
        )
        row = cur.fetchone()

        if not row:
            logger.warning("[PROFILE] user_profile missing | external_user_id=%s | name=%s", external_user_id, name)
            return {}

        (
            credits_limit, credits_used, credits_remaining,
            audio_seconds, audio_limit,
            graph_count, graph_limit,
            request_count, request_limit,
            tokens_used, token_limit,
        ) = row

        # Query 2: last 7 days from usage_history (for trend charts)
        cur.execute(
            """
            SELECT date, credits_used, audio_seconds, graph_count, request_count, tokens_used
            FROM usage_history
            WHERE external_user_id = %s AND name = %s
            ORDER BY date DESC
            LIMIT 7
            """,
            (external_user_id, name)
        )
        history_rows = cur.fetchall()

        # Reverse so history is chronological (oldest first)
        history = [
            {
                "date":          str(r[0]),
                "credits_used":  int(r[1] or 0),
                "audio_seconds": int(r[2] or 0),
                "graph_count":   int(r[3] or 0),
                "request_count": int(r[4] or 0),
                "tokens_used":   int(r[5] or 0),
            }
            for r in reversed(history_rows)
        ]

        logger.info(
            "✅ [PROFILE] Usage stats fetched | external_user_id=%s | name=%s | history_days=%d",
            external_user_id, name, len(history),
        )

        return {
            "credits_limit":     int(credits_limit     or 0),
            "credits_used":      int(credits_used      or 0),
            "credits_remaining": int(credits_remaining or 0),
            "audio_seconds":     int(audio_seconds     or 0),
            "audio_limit":       int(audio_limit       or 0),
            "graph_count":       int(graph_count       or 0),
            "graph_limit":       int(graph_limit       or 0),
            "request_count":     int(request_count     or 0),
            "request_limit":     int(request_limit     or 0),
            "tokens_used":       int(tokens_used       or 0),
            "token_limit":       int(token_limit       or 0),
            "tokens_remaining":  max(int(token_limit or 0) - int(tokens_used or 0), 0),
            "history":           history,
        }


def update_daily_history(
    *,
    external_user_id:    str,
    name:                str,
    credits_delta:       int = 0,
    audio_seconds_delta: int = 0,
    graph_delta:         int = 0,
    request_delta:       int = 1,
    tokens_delta:        int = 0,
) -> None:
    """
    Upsert today's usage row in usage_history table.

    Called after every query response to maintain daily usage trends.
    Uses ON CONFLICT to increment today's row if it exists.

    Guards:
        - Skips if user_profile row doesn't exist
        - Skips if all deltas are 0
    """
    if not external_user_id or not name:
        logger.warning("[PROFILE] update_daily_history — missing external_user_id or name")
        return

    # Normalize to int
    credits_delta       = int(credits_delta       or 0)
    audio_seconds_delta = int(audio_seconds_delta or 0)
    graph_delta         = int(graph_delta         or 0)
    request_delta       = int(request_delta       or 0)
    tokens_delta        = int(tokens_delta        or 0)

    conn = get_pool()
    conn.rollback()

    with conn.cursor() as cur:
        # Guard: only update if user_profile exists
        cur.execute(
            "SELECT 1 FROM user_profile WHERE external_user_id = %s AND name = %s",
            (external_user_id, name),
        )
        if not cur.fetchone():
            logger.warning(
                "[PROFILE] update_daily_history skipped — user_profile missing | external_user_id=%s | name=%s",
                external_user_id, name,
            )
            conn.rollback()
            return

        # Upsert today's row — increment if exists, insert if not
        cur.execute(
            """
            INSERT INTO usage_history
                (external_user_id, name, date, credits_used,
                 audio_seconds, graph_count, request_count, tokens_used, updated_at)
            VALUES
                (%s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (external_user_id, name, date) DO UPDATE SET
                credits_used  = usage_history.credits_used  + EXCLUDED.credits_used,
                audio_seconds = usage_history.audio_seconds + EXCLUDED.audio_seconds,
                graph_count   = usage_history.graph_count   + EXCLUDED.graph_count,
                request_count = usage_history.request_count + EXCLUDED.request_count,
                tokens_used   = usage_history.tokens_used   + EXCLUDED.tokens_used,
                updated_at    = NOW()
            """,
            (
                external_user_id, name,
                max(credits_delta, 0),
                max(audio_seconds_delta, 0),
                max(graph_delta, 0),
                max(request_delta, 0),
                max(tokens_delta, 0),
            )
        )

        if cur.rowcount == 0:
            logger.warning("[PROFILE] update_daily_history — no rows affected | external_user_id=%s", external_user_id)
            conn.rollback()
            return

    conn.commit()
    logger.info(
        "✅ [PROFILE] Daily history updated | external_user_id=%s | name=%s | credits=%d | audio=%ds | graphs=%d | requests=%d",
        external_user_id, name, credits_delta, audio_seconds_delta, graph_delta, request_delta,
    )