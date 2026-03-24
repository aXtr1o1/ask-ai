"""
User profile usage tracking (PostgreSQL).

UPDATE-only behavior:
- we ONLY update existing `user_profile` rows
- if the user row doesn't exist, we log a warning (no insert)
"""

import logging
from app.api.database.postgres_client import get_pool

logger = logging.getLogger("user_profile_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(ch)


def get_credits_remaining(name: str) -> int | None:
    """
    Return credits_remaining for an existing user, else None.
    """
    if not name:
        raise ValueError("name is required")

    conn = get_pool()
    conn.rollback()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT credits_remaining FROM user_profile WHERE name = %s",
            (name,),
        )
        row = cur.fetchone()
        if not row:
            logger.warning(
                "⚠️ user_profile missing for name=%s (credits check skipped)",
                name,
            )
            return None

        try:
            return int(row[0] or 0)
        except Exception:
            return 0


def get_graph_count_and_limit(name: str) -> tuple[int, int] | None:
    """
    Return (graph_count, graph_limit) for an existing user, else None.
    """
    if not name:
        raise ValueError("name is required")

    conn = get_pool()
    conn.rollback()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT graph_count, graph_limit FROM user_profile WHERE name = %s",
            (name,),
        )
        row = cur.fetchone()
        if not row:
            logger.warning(
                "⚠️ user_profile missing for name=%s (graph check skipped)",
                name,
            )
            return None

        try:
            graph_count = int(row[0] or 0)
            graph_limit = int(row[1] or 0)
            return graph_count, graph_limit
        except Exception:
            return 0, 0


def update_usage_if_exists(
    *,
    name: str,
    tokens_used_delta: int = 0,
    request_delta: int = 1,
    graph_delta: int = 0,
    credits_per_request: int = 1,
    audio_seconds_delta: int = 0,
) -> None:
    """
    Atomic UPDATE of counters for an existing user_profile row.

    If no row exists for `name`, we log and return.
    """
    if not name:
        raise ValueError("name is required")

    tokens_used_delta = int(tokens_used_delta or 0)
    request_delta = int(request_delta or 0)
    graph_delta = int(graph_delta or 0)
    credits_per_request = int(credits_per_request or 0)
    audio_seconds_delta = int(audio_seconds_delta or 0)

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
                "name": name,
                "tokens_used_delta": tokens_used_delta,
                "request_delta": request_delta,
                "graph_delta": graph_delta,
                "audio_seconds_delta": audio_seconds_delta,
                "credits_delta": credits_per_request * request_delta,
            },
        )

        if cur.rowcount == 0:
            logger.warning(
                "⚠️ user_profile missing for name=%s (no update applied)",
                name,
            )
            conn.rollback()
            return

    conn.commit()


def consume_audio_seconds_if_available(
    *,
    name: str,
    audio_seconds_delta: int,
) -> bool | None:
    """
    Atomically consume audio credits:
      - If user exists and (audio_seconds + delta) <= audio_limit → update and return True
      - If user exists but not enough credits → return False
      - If user missing (or audio columns not available) → log warning and return None
    """
    if not name:
        raise ValueError("name is required")

    audio_seconds_delta = int(audio_seconds_delta or 0)
    if audio_seconds_delta <= 0:
        logger.warning("⚠️ audio_seconds_delta <= 0 for name=%s; skipping consume", name)
        return None

    conn = get_pool()
    conn.rollback()

    with conn.cursor() as cur:
        try:
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
            logger.warning(
                "⚠️ audio credits consume failed (missing columns?): name=%s err=%s",
                name,
                str(e)[:200],
            )
            conn.rollback()
            return None

        if cur.rowcount and cur.rowcount > 0:
            conn.commit()
            return True

        # rowcount==0 could be: out of audio credits OR user missing.
        cur.execute(
            """
            SELECT audio_limit, audio_seconds
            FROM user_profile
            WHERE name = %s
            """,
            (name,),
        )
        row = cur.fetchone()
        if not row:
            logger.warning(
                "⚠️ user_profile missing for name=%s (audio check skipped)",
                name,
            )
            conn.rollback()
            return None

        audio_limit, audio_seconds_used = row[0], row[1]
        try:
            audio_limit = int(audio_limit or 0)
            audio_seconds_used = int(audio_seconds_used or 0)
        except Exception:
            logger.warning(
                "⚠️ invalid audio_limit/audio_seconds values for name=%s (audio check skipped)",
                name,
            )
            conn.rollback()
            return None

        if audio_seconds_used + audio_seconds_delta > audio_limit:
            logger.info(
                "⛔ Audio credits exhausted | name=%s used=%s delta=%s limit=%s",
                name,
                audio_seconds_used,
                audio_seconds_delta,
                audio_limit,
            )
            conn.rollback()
            return False

        # Fallback: something else prevented update; allow.
        logger.warning(
            "⚠️ audio credits consume did not apply but no exhaustion detected for name=%s",
            name,
        )
        conn.rollback()
        return None
"""

"""

# CHANGE function signature to accept both
def get_user_usage_stats(
    external_user_id: str,
    name: str
) -> dict:

    if not external_user_id or not name:
        raise ValueError("external_user_id and name are required")

    conn = get_pool()
    conn.rollback()

    with conn.cursor() as cur:

        # ── Query 1: user_profile ────────────────────────────
        cur.execute(
            """
            SELECT
                credits_limit,
                credits_used,
                credits_remaining,
                audio_seconds,
                audio_limit,
                graph_count,
                graph_limit,
                request_count,
                request_limit,
                tokens_used,
                token_limit
            FROM user_profile
            WHERE external_user_id = %s AND name = %s
            LIMIT 1
            """,
            (external_user_id, name)
        )
        row = cur.fetchone()

        if not row:
            logger.warning(
                "⚠️ user_profile missing for external_user_id=%s name=%s",
                external_user_id, name,
            )
            return {}

        (
            credits_limit,
            credits_used,
            credits_remaining,
            audio_seconds,
            audio_limit,
            graph_count,
            graph_limit,
            request_count,
            request_limit,
            tokens_used,
            token_limit,
        ) = row

        # ── Query 2: usage_history ───────────────────────────
        cur.execute(
            """
            SELECT
                date,
                credits_used,
                audio_seconds,
                graph_count,
                request_count,
                tokens_used
            FROM usage_history
            WHERE external_user_id = %s AND name = %s
            ORDER BY date DESC
            LIMIT 7
            """,
            (external_user_id, name)
        )
        history_rows = cur.fetchall()

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
            "✅ get_user_usage_stats | external_user_id=%s name=%s | history_days=%s",
            external_user_id, name, len(history)
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
    external_user_id: str,   
    name: str,
    credits_delta: int = 0,
    audio_seconds_delta: int = 0,
    graph_delta: int = 0,
    request_delta: int = 1,
    tokens_delta: int = 0,
) -> None:

    if not external_user_id or not name:
        logger.warning("⚠️ update_daily_history — missing external_user_id or name")
        return

    credits_delta       = int(credits_delta       or 0)
    audio_seconds_delta = int(audio_seconds_delta or 0)
    graph_delta         = int(graph_delta         or 0)
    request_delta       = int(request_delta       or 0)
    tokens_delta        = int(tokens_delta        or 0)

    conn = get_pool()
    conn.rollback()

    with conn.cursor() as cur:
        # ── Guard: skip if user_profile row doesn't exist ──
        cur.execute(
            "SELECT 1 FROM user_profile WHERE external_user_id = %s AND name = %s",
            (external_user_id, name),
        )
        if not cur.fetchone():
            logger.warning(
                "⚠️ update_daily_history skipped — user_profile missing for external_user_id=%s name=%s",
                external_user_id, name,
            )
            conn.rollback()
            return

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
                external_user_id,
                name,
                max(credits_delta, 0),
                max(audio_seconds_delta, 0),
                max(graph_delta, 0),
                max(request_delta, 0),
                max(tokens_delta, 0),
            )
        )
        if cur.rowcount == 0:
            logger.warning(
                "⚠️ update_daily_history did not affect rows | external_user_id=%s name=%s",
                external_user_id, name,
            )
            conn.rollback()
            return

    conn.commit()
    logger.info(
        "✅ update_daily_history | external_user_id=%s name=%s | credits=%s audio=%s graph=%s reqs=%s",
        external_user_id, name,
        credits_delta, audio_seconds_delta, graph_delta, request_delta
    )