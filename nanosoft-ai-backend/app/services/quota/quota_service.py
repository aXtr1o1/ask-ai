"""
services/quota/quota_service.py
────────────────────────────────
Handles direct DB queries when the AI model quota is exceeded.

Why this exists:
    When Gemini API quota is exhausted, the model call fails.
    Instead of showing an error, we offer the user a menu to directly
    query the database without going through the AI.

Flow (triggered from main.py):
    1. Model call fails → is_quota_error() returns True
    2. get_quota_exceeded_message() → show user available services
    3. User replies with service name (e.g. "show assets")
    4. handle_user_table_choice() → parse service + limit → query DB directly
    5. format_response() → return JSON for frontend table renderer

Dynamic:
    No hardcoded service names — all services loaded from client_service_registry.
"""

import logging
import re
import json
from typing import Optional, Tuple, Dict, Any, List

logger = logging.getLogger("services.quota.quota_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)


class QuotaFallbackService:
    """
    Direct DB query fallback when AI model quota is exceeded.
    Fully dynamic — loads services from client_service_registry.
    """

    def __init__(self):
        logger.info("🔄 [QUOTA] QuotaFallbackService initialized | mode=dynamic")

    def is_quota_error(self, error: Exception) -> bool:
        """
        Returns True ONLY for genuine quota / rate-limit errors.
        All other failures (network, DB, auth, etc.) are NOT quota errors
        and should surface normally instead of triggering the fallback menu.
        """
        error_str = str(error).lower()

        quota_signals = (
            "quota",
            "rate limit",
            "rate_limit",
            "resource_exhausted",
            "429",
            "too many requests",
            "exhausted",
            "billing",
            "exceeded your current quota",
        )

        matched = any(signal in error_str for signal in quota_signals)

        if matched:
            logger.warning(
                "[QUOTA] Genuine quota error detected → triggering fallback | error=%s",
                error_str[:120],
            )
        else:
            logger.info(
                "[QUOTA] Non-quota error — NOT triggering fallback | error=%s",
                error_str[:120],
            )

        return matched

    def get_services_for_client(self, client_name: str) -> List[Dict]:
        """
        Load all active services for a client.
        Used to build the quota exceeded menu and to parse user replies.
        """
        try:
            from app.dynamic.service import get_conn, get_services_for_client
            conn     = get_conn()
            services = get_services_for_client(conn, client_name)
            logger.info("[QUOTA] Services loaded | client_name=%s | count=%d", client_name, len(services))
            return services
        except Exception as e:
            logger.error("[QUOTA] Failed to load services | error=%s", e)
            return []

    def get_quota_exceeded_message(self, client_name: str = None) -> str:
        """
        Build the quota exceeded message shown to the user.

        Dynamically lists all available services so user knows what they can query.
        Each service shows its name + example trigger phrase.

        Args:
            client_name: used to load available services from registry

        Returns:
            Formatted message string with service list
        """
        service_lines = ""

        if client_name:
            services = self.get_services_for_client(client_name)
            if services:
                lines = []
                for svc in services:
                    keywords = svc.get("routing_keywords") or []
                    # Use first 2 keywords as examples to keep message short
                    kw_str = ", ".join(keywords[:2]) if keywords else svc["service_key"]
                    lines.append(f"• **{svc['service_name']}** — say: '{kw_str}'")
                service_lines = "\n".join(lines)

        if not service_lines:
            service_lines = "• No services currently available."

        message = (
            "🚦 **High Traffic Detected — Manual Retrieval Mode Active**\n\n"
            "The AI assistant is temporarily unavailable due to heavy demand, "
            "but you can still retrieve your data directly.\n\n"
            "**What would you like to view?**\n"
            f"{service_lines}\n\n"
            "Just tell me what you need — for example:\n"
            "- *'show me assets'*\n"
            "- *'give me 50 complaints'*\n"
            "- *'list all ppm'*"
        )

        logger.info("[QUOTA] Quota exceeded message generated | client_name=%s", client_name)
        return message

    def parse_service_key(self, query: str, client_name: str) -> Optional[str]:
        """
        Detect which service the user is asking about from their reply.

        Matching strategy:
            1. Check routing_keywords from client_service_registry
            2. Fall back to direct service_key match

        Args:
            query:       user's reply e.g. "show me 50 assets"
            client_name: used to load services + their keywords

        Returns:
            service_key string (e.g. "assets") or None if not matched
        """
        query_lower = query.lower()
        services    = self.get_services_for_client(client_name)

        for svc in services:
            # Check each routing keyword
            keywords = svc.get("routing_keywords") or []
            for kw in keywords:
                if kw.lower() in query_lower:
                    logger.info("[QUOTA] Matched service | service_key=%s | via keyword='%s'", svc["service_key"], kw)
                    return svc["service_key"]

            # Also match on service_key directly (e.g. "assets" in query)
            if svc["service_key"].lower() in query_lower:
                logger.info("[QUOTA] Matched service | service_key=%s | via direct match", svc["service_key"])
                return svc["service_key"]

        logger.warning("[QUOTA] Could not detect service | query='%s'", query)
        return None

    def parse_limit(self, query: str) -> Optional[int]:
        """
        Extract a record limit from user query.

        Parsing strategies (in order):
            1. "all" → None (fetch everything)
            2. "limit: N" or "limit N"
            3. "show/get/give/fetch N ..."
            4. "N words" (standalone number followed by word)

        Returns:
            int limit or None (None = fetch all)
        """
        query_lower = query.lower()

        # "all" → no limit
        if " all" in query_lower or query_lower.startswith("all "):
            logger.info("[QUOTA] Detected 'all' — no limit")
            return None

        # "limit: 50" or "limit 50"
        limit_match = re.search(r'limit[\s:]+(\d+)', query_lower)
        if limit_match:
            return int(limit_match.group(1))

        # "show me 50 assets" → 50
        number_match = re.search(r'(?:show|get|give|fetch|list)[\s\w]*?(\d+)', query_lower)
        if number_match:
            return int(number_match.group(1))

        # "50 assets" → 50
        standalone_match = re.search(r'\b(\d+)\s+\w+', query_lower)
        if standalone_match:
            return int(standalone_match.group(1))

        logger.info("[QUOTA] No limit found — fetching all")
        return None

    def query_database(
        self,
        client_name: str,
        user_id:     int,
        service_key: str,
        limit:       Optional[int] = None,
    ) -> Tuple[Dict[str, Any], int]:
        """
        Query client_service_data using sp_universal_query directly.
        No AI involved — pure DB call.

        Args:
            client_name: e.g. "poc"
            user_id:     e.g. 1
            service_key: e.g. "assets"
            limit:       max records or None for all

        Returns:
            (result_dict, total_count)
        """
        logger.info(
            "[QUOTA] Querying DB | client=%s | service=%s | limit=%s",
            client_name, service_key, limit,
        )
        try:
            from app.dynamic.service import get_conn
            conn   = get_conn()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT public.sp_universal_query(%s, %s, %s, %s, %s, %s, %s)",
                (
                    client_name,
                    user_id,
                    service_key,
                    json.dumps({}),  # no filters
                    json.dumps({}),  # no date filters
                    limit,
                    0,               # offset
                ),
            )
            row = cursor.fetchone()
            cursor.close()

            raw = row[0] if row else {}
            if isinstance(raw, str):
                raw = json.loads(raw)

            p_list  = raw.get("p_list", []) or []
            p_count = raw.get("p_count", 0) or 0

            logger.info(
                "✅ [QUOTA] DB query complete | client=%s | service=%s | p_count=%s | returned=%s",
                client_name, service_key, p_count, len(p_list),
            )
            return {"p_list": p_list, "p_count": p_count}, p_count

        except Exception as e:
            logger.error("❌ [QUOTA] DB query failed | service=%s | error=%s", service_key, e, exc_info=True)
            raise

    def format_response(
        self,
        service_key:  str,
        result:       Dict[str, Any],
        total_count:  int,
        limit:        Optional[int] = None,
    ) -> Tuple[str, str]:
        """
        Format DB result into frontend-compatible JSON response.

        Returns:
            (final_response_text, context_summary)
            - final_response_text → JSON string {"context_summary": ..., "records": [...]}
            - context_summary     → short text stored in lc_memory
        """
        p_list = result.get("p_list", [])

        if total_count == 0:
            context_summary = f"No records found for {service_key}."
            return context_summary, context_summary

        if limit and len(p_list) < total_count:
            context_summary = f"Found {total_count} {service_key} records (showing {len(p_list)})."
        else:
            context_summary = f"Found {total_count} {service_key} records."

        response_data = {
            "context_summary": context_summary,
            "records":         p_list,
        }

        final_response = json.dumps(response_data)
        logger.info(
            "✅ [QUOTA] Response formatted | service=%s | records=%d | total=%d",
            service_key, len(p_list), total_count,
        )
        return final_response, context_summary

    def handle_user_table_choice(
        self,
        user_reply:  str,
        user_name:   str,
        user_id:     int,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Handle user's reply after the quota exceeded menu is shown.

        Steps:
            1. Detect which service user wants (parse_service_key)
            2. Extract limit from reply (parse_limit)
            3. Query DB directly (query_database)
            4. Format result for frontend (format_response)

        Args:
            user_reply:  e.g. "show me 50 assets"
            user_name:   client_name e.g. "poc"
            user_id:     integer user id e.g. 1

        Returns:
            (final_response_text, context_summary) or (None, None) if service not detected
        """
        logger.info(
            "[QUOTA] Handling table choice | reply='%s' | client=%s | user_id=%s",
            user_reply, user_name, user_id,
        )

        # Step 1: detect which service user wants
        service_key = self.parse_service_key(user_reply, client_name=user_name)
        if not service_key:
            logger.warning("[QUOTA] Could not detect service from reply='%s'", user_reply)
            return None, None

        # Step 2: extract limit
        limit = self.parse_limit(user_reply)
        logger.info("[QUOTA] Parsed | service_key=%s | limit=%s", service_key, limit)

        # Step 3: query DB
        try:
            result, total_count = self.query_database(
                client_name = user_name,
                user_id     = user_id,
                service_key = service_key,
                limit       = limit,
            )
        except Exception as e:
            logger.error("[QUOTA] DB query failed | service=%s | error=%s", service_key, e)
            return None, None

        # Step 4: format and return
        return self.format_response(service_key, result, total_count, limit)


# Singleton — imported by main.py
quota_fallback_service = QuotaFallbackService()