import logging
import json
import asyncio
from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import settings
from app.tools.space_booking_tool import GET_SPOTS, BOOK_SPOT, GET_BOOKING_STATUS, fetch_spots_api
from app.prompts.space_booking_prompt import SPACE_BOOKING_SYSTEM_PROMPT
from app.state import memory_store

logger = logging.getLogger("space_booking_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)

SB_THREAD_MAX_MESSAGES = 20


# ── Slim record fields sent to the frontend table ──────────────────────────────
_TABLE_FIELDS = ("SpotCode", "SpotName", "BuildingName", "FloorName")


def _extract_content(msg) -> str:
    """Safely extract plain text from an AI message.
    Gemini can return content as a list of parts instead of a bare string.
    """
    c = msg.content
    if isinstance(c, list):
        return " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in c
        ).strip()
    return c or ""


def _slim_records(p_list: list) -> list:
    """Return only the 4 display fields — strip all raw API noise."""
    return [{f: s.get(f) for f in _TABLE_FIELDS} for s in p_list]


# ── Session cache helpers ──────────────────────────────────────────────────────

def _cache_key(search_term: Optional[str]) -> str:
    return (search_term or "__all__").strip().lower()


def _get_cached_spots(session_id: str, search_term: Optional[str]) -> Optional[dict]:
    cache = memory_store.get(session_id, {}).get("sb_spot_cache", {})
    result = cache.get(_cache_key(search_term))
    if result is not None:
        logger.info("✅ Cache HIT | session=%s | key=%s | spots=%d",
                    session_id, _cache_key(search_term), result.get("TotalCount", 0))
    return result


def _set_cached_spots(session_id: str, search_term: Optional[str], data: dict):
    if session_id not in memory_store:
        memory_store[session_id] = {}
    if "sb_spot_cache" not in memory_store[session_id]:
        memory_store[session_id]["sb_spot_cache"] = {}
    memory_store[session_id]["sb_spot_cache"][_cache_key(search_term)] = data
    logger.info("💾 Cache SET | session=%s | key=%s | spots=%d",
                session_id, _cache_key(search_term), data.get("TotalCount", 0))


def _lookup_spot_from_cache(session_id: Optional[str], spot_code: str) -> Optional[dict]:
    """Find a spot's full details by SpotCode across all cached searches."""
    if not session_id:
        return None
    sb_cache = memory_store.get(session_id, {}).get("sb_spot_cache", {})
    for cached_data in sb_cache.values():
        for spot in cached_data.get("p_list", []):
            if spot.get("SpotCode") == spot_code:
                return spot
    return None


# ── sb_thread helpers ──────────────────────────────────────────────────────────

def _get_sb_thread(session_id: Optional[str]) -> list:
    if not session_id:
        return []
    return list(memory_store.get(session_id, {}).get("sb_thread", []))


def _save_sb_thread(session_id: Optional[str], thread: list):
    if not session_id:
        return
    if session_id not in memory_store:
        memory_store[session_id] = {}
    memory_store[session_id]["sb_thread"] = thread[-SB_THREAD_MAX_MESSAGES:]
    logger.info("💾 sb_thread saved | session=%s | msgs=%d", session_id, len(thread))


def _clear_sb_thread(session_id: Optional[str]):
    """Reset only the conversation thread after a completed booking.
    The spot cache is intentionally kept so the next search in the same
    session does not need to re-hit the API."""
    if session_id and session_id in memory_store:
        memory_store[session_id]["sb_thread"] = []
        logger.info("🗑️ sb_thread reset (cache kept) | session=%s", session_id)


# ── Service ────────────────────────────────────────────────────────────────────

class SpaceBookingService:
    def __init__(self):
        try:
            self.model = ChatGoogleGenerativeAI(
                model=settings.GOOGLE_AI_MODEL,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=0.0
            ).bind_tools([GET_SPOTS, BOOK_SPOT, GET_BOOKING_STATUS])

            self.system_prompt = SPACE_BOOKING_SYSTEM_PROMPT
            logger.info("🚀 SpaceBookingService initialized with tools: GET_SPOTS, BOOK_SPOT, GET_BOOKING_STATUS")
        except Exception as e:
            logger.error(f"❌ SpaceBookingService init failed: {e}", exc_info=True)
            raise

    async def handle_space_booking(
        self,
        messages: list,
        user_name: str,
        sub_user_name: str = None,
        session_id: str = None
    ) -> tuple[str, str, list]:
        try:
            logger.info(f"🚀 Space booking | user={user_name} | session={session_id}")

            # Extract current user query
            current_query = ""
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    current_query = msg.content
                    break
            logger.info("📝 Query: %s", current_query[:120])

            # Load & extend the real per-session conversation thread
            sb_thread = _get_sb_thread(session_id)
            sb_thread.append(HumanMessage(content=current_query))

            # Build prompt: system prompt + real thread only (no scoped memory noise)
            sys_msg = SystemMessage(
                content=self.system_prompt.content + f"\n\nCURRENT USER_NAME: {user_name}. If the user provides a Spot Code, do NOT call GET_SPOTS again; proceed directly to booking or providing details."
            )
            prompt_messages = [sys_msg] + sb_thread

            # First model invoke
            ai_msg = await self.model.ainvoke(prompt_messages)

            tool_data = None

            if ai_msg.tool_calls:
                prompt_messages.append(ai_msg)

                for tc in ai_msg.tool_calls:

                    # ── GET_SPOTS ─────────────────────────────────────────────
                    if tc["name"] == "GET_SPOTS":
                        s_term = tc["args"].get("search_term")

                        cached = _get_cached_spots(session_id, s_term) if session_id else None
                        if cached is not None:
                            logger.info("📦 Cache HIT — skipping API")
                            tool_data = cached
                            tool_result_str = json.dumps(cached)
                        else:
                            # ── Before hitting the API, try filtering the __all__ cache locally ──
                            # Prevents a second API call when the model searches with a spot code
                            # or building name after already fetching all spots in the session.
                            all_cached = _get_cached_spots(session_id, None) if session_id else None
                            if all_cached is not None and s_term and str(s_term).strip():
                                import re as _re
                                clean_search = _re.sub(r'[^a-z0-9]', '', str(s_term).lower())
                                p_list_all = all_cached.get("p_list", [])
                                filtered = [
                                    spot for spot in p_list_all
                                    if clean_search in _re.sub(r'[^a-z0-9]', '', str(spot.get("BuildingName", "")).lower())
                                    or clean_search in _re.sub(r'[^a-z0-9]', '', str(spot.get("SpotCode", "")).lower())
                                    or clean_search in _re.sub(r'[^a-z0-9]', '', str(spot.get("SpotName", "")).lower())
                                ]
                                tool_data = {"TotalCount": len(filtered), "p_list": filtered}
                                tool_result_str = json.dumps(tool_data)
                                if session_id:
                                    _set_cached_spots(session_id, s_term, tool_data)
                                logger.info("📦 Filtered from __all__ cache (no API call) | matches=%d", len(filtered))
                            else:
                                logger.info("🌐 Cache MISS — calling API")
                                tool_result_str = await fetch_spots_api(user_name, s_term)
                                try:
                                    tool_data = json.loads(tool_result_str)
                                except Exception:
                                    tool_data = {"error": "Invalid JSON"}
                                if session_id and isinstance(tool_data, dict) and "p_list" in tool_data:
                                    _set_cached_spots(session_id, s_term, tool_data)

                        # Send only 4 compressed fields to LLM
                        if isinstance(tool_data, dict) and "p_list" in tool_data:
                            compressed = [
                                {f: s.get(f) for f in _TABLE_FIELDS}
                                for s in tool_data.get("p_list", [])
                            ]
                            llm_content = json.dumps({
                                "TotalCount": tool_data.get("TotalCount"),
                                "spots": compressed
                            })
                        else:
                            llm_content = tool_result_str

                        prompt_messages.append(ToolMessage(
                            name=tc["name"], tool_call_id=tc["id"], content=llm_content
                        ))



                    # ── BOOK_SPOT ─────────────────────────────────────────────
                    elif tc["name"] == "BOOK_SPOT":
                        args = tc["args"]
                        args["user_name"] = user_name
                        if sub_user_name:
                            args["sub_user_name"] = sub_user_name

                        # ── Verify spot details from cache (prevents hallucination) ─
                        spot_code_req = args.get("spot_code", "")
                        verified = _lookup_spot_from_cache(session_id, spot_code_req)
                        if verified:
                            args["spot_name"]     = verified.get("SpotName", args.get("spot_name"))
                            args["building_name"] = verified.get("BuildingName", args.get("building_name"))
                            args["floor_name"]    = verified.get("FloorName", args.get("floor_name"))
                            logger.info("✅ Spot verified from cache: %s → %s", spot_code_req, args["spot_name"])
                        tool_result_str = await BOOK_SPOT.ainvoke(args)

                        try:
                            parsed_res = json.loads(tool_result_str)

                            if parsed_res.get("error_type") == "missing_time":
                                spot_code = parsed_res.get("spot_code", "the spot")
                                building  = parsed_res.get("building_name", "the building")

                                prompt_messages.append(ToolMessage(
                                    name=tc["name"], tool_call_id=tc["id"],
                                    content=json.dumps({
                                        "error_type": "missing_time",
                                        "instruction": (
                                            f"Time not provided. Ask the user warmly for their preferred time "
                                            f"for booking {spot_code} at {building}. "
                                            f"Do NOT call BOOK_SPOT again until they reply with a time."
                                        )
                                    })
                                ))
                                ai_msg2 = await self.model.ainvoke(prompt_messages)
                                time_ask = ai_msg2.content or (
                                    f"When would you like to book **{spot_code}** at **{building}**? "
                                    f"(e.g. 10am, 2pm–4pm, morning)"
                                )
                                logger.info("⏰ Missing time — asking: %s", time_ask[:100])
                                sb_thread.append(AIMessage(content=time_ask))
                                _save_sb_thread(session_id, sb_thread)
                                return time_ask, time_ask, messages

                            if parsed_res.get("success"):
                                logger.info("✅ Booking success | id=%s", parsed_res.get("booking_id"))

                        except json.JSONDecodeError:
                            pass

                        prompt_messages.append(ToolMessage(
                            name=tc["name"], tool_call_id=tc["id"], content=tool_result_str
                        ))

                    # ── GET_BOOKING_STATUS ────────────────────────────────────
                    elif tc["name"] == "GET_BOOKING_STATUS":
                        args = tc["args"]
                        args["user_name"] = user_name
                        tool_result_str = await GET_BOOKING_STATUS.ainvoke(args)
                        logger.info("🔍 GET_BOOKING_STATUS result: %s", tool_result_str[:200])

                        prompt_messages.append(ToolMessage(
                            name=tc["name"], tool_call_id=tc["id"], content=tool_result_str
                        ))

                # Final model response
                ai_msg2 = await self.model.ainvoke(prompt_messages)
                content = _extract_content(ai_msg2)

                # ── Handle the case where the model makes ANOTHER tool call instead of replying ──
                # This happens when the LLM skips Phase 2 and tries to call BOOK_SPOT immediately
                # after GET_SPOTS, resulting in empty .content.
                if not content.strip() and ai_msg2.tool_calls:
                    logger.info("⚡ ai_msg2 has tool_calls but no content — handling inline")
                    prompt_messages.append(ai_msg2)

                    for tc2 in ai_msg2.tool_calls:
                        if tc2["name"] == "BOOK_SPOT":
                            args2 = tc2["args"]
                            args2["user_name"] = user_name
                            if sub_user_name:
                                args2["sub_user_name"] = sub_user_name

                            # Verify spot from cache to prevent hallucination
                            spot_code_req2 = args2.get("spot_code", "")
                            verified2 = _lookup_spot_from_cache(session_id, spot_code_req2)
                            if verified2:
                                args2["spot_name"]     = verified2.get("SpotName", args2.get("spot_name"))
                                args2["building_name"] = verified2.get("BuildingName", args2.get("building_name"))
                                args2["floor_name"]    = verified2.get("FloorName", args2.get("floor_name"))
                                logger.info("✅ Spot verified from cache (round-2): %s → %s", spot_code_req2, args2["spot_name"])

                            tool_result2_str = await BOOK_SPOT.ainvoke(args2)
                            try:
                                parsed2 = json.loads(tool_result2_str)
                                if parsed2.get("error_type") == "missing_time":
                                    spot_code2   = parsed2.get("spot_code", args2.get("spot_code", "the spot"))
                                    building2    = parsed2.get("building_name", args2.get("building_name", "the building"))
                                    prompt_messages.append(ToolMessage(
                                        name=tc2["name"], tool_call_id=tc2["id"],
                                        content=json.dumps({
                                            "error_type": "missing_time",
                                            "instruction": (
                                                f"Time not provided. Ask the user warmly for their preferred time "
                                                f"for booking {spot_code2} at {building2}. "
                                                f"Do NOT call BOOK_SPOT again until they reply with a time."
                                            )
                                        })
                                    ))
                                    ai_msg3 = await self.model.ainvoke(prompt_messages)
                                    time_ask = ai_msg3.content or (
                                        f"Almost there! Just let me know your preferred start and end time "
                                        f"for {spot_code2} at {building2} and I will get it confirmed."
                                    )
                                    logger.info("⏰ Round-2 missing time — asking: %s", time_ask[:100])
                                    sb_thread.append(AIMessage(content=time_ask))
                                    _save_sb_thread(session_id, sb_thread)
                                    return time_ask, time_ask, messages

                                if parsed2.get("success"):
                                    logger.info("✅ Round-2 booking success | id=%s", parsed2.get("booking_id"))
                            except json.JSONDecodeError:
                                pass

                            prompt_messages.append(ToolMessage(
                                name=tc2["name"], tool_call_id=tc2["id"], content=tool_result2_str
                            ))

                        elif tc2["name"] == "GET_SPOTS":
                            # Shouldn't re-call GET_SPOTS, but handle gracefully
                            logger.warning("⚠️ Unexpected second GET_SPOTS call — skipping")
                            prompt_messages.append(ToolMessage(
                                name=tc2["name"], tool_call_id=tc2["id"],
                                content=json.dumps({"info": "Spots already retrieved. Use the previous results."})
                            ))

                    # Get final content after handling round-2 tool calls
                    ai_msg3 = await self.model.ainvoke(prompt_messages)
                    content = _extract_content(ai_msg3)

                if not content.strip():
                    # Last-resort fallback — build a sensible message from context
                    spot_hint = ""
                    if tool_data and "p_list" in tool_data and tool_data["p_list"]:
                        spot = tool_data["p_list"][0]
                        spot_hint = (
                            f" for {spot.get('SpotName', '')} ({spot.get('SpotCode', '')}) "
                            f"at {spot.get('BuildingName', '')}"
                        )
                    content = (
                        f"Great news! I have found the space{spot_hint}. "
                        f"Would you like me to go ahead and book it? "
                        f"If so, please share your preferred start and end time."
                    )
                    logger.warning("⚠️ Empty content fallback used — check model output")

                # Manage thread after tool response
                try:
                    last_result = json.loads(prompt_messages[-1].content)
                    if last_result.get("success"):
                        # Booking done — reset for next flow
                        sb_thread.append(AIMessage(content=content))
                        _save_sb_thread(session_id, sb_thread)
                        _clear_sb_thread(session_id)
                    else:
                        sb_thread.append(AIMessage(content=content))
                        _save_sb_thread(session_id, sb_thread)
                except Exception:
                    sb_thread.append(AIMessage(content=content))
                    _save_sb_thread(session_id, sb_thread)

                # ── Respond: table for multiple spots, conversational otherwise ──
                if tool_data and "p_list" in tool_data and len(tool_data["p_list"]) > 1:
                    total = tool_data.get("TotalCount", len(tool_data["p_list"]))
                    p_list = tool_data["p_list"]

                    # For large result sets (>8), override the AI summary with a short message
                    # so the AI doesn't dump the full list into the text — the tiles handle display
                    if total > 8:
                        building_name = p_list[0].get("BuildingName", "this building") if p_list else "this building"
                        summary = (
                            f"You've got {total} spaces available at {building_name}. "
                            f"Browse the options below and let me know which Spot Code you'd like — "
                            f"I'll get it booked for you right away!"
                        )
                    else:
                        summary = content

                    final_response = {
                        "type": "large_dataset",
                        "context_summary": summary,
                        "records": _slim_records(p_list)  # ← 4 fields only
                    }
                    return json.dumps(final_response), summary, messages
                else:
                    return content, content, messages


            # No tool called — pure conversational
            content = _extract_content(ai_msg)
            if not content.strip():
                content = (
                    "I'm here to help you book a space! "
                    "Which building or Spot Code are you looking for?"
                )
            sb_thread.append(AIMessage(content=content))
            _save_sb_thread(session_id, sb_thread)
            return content, content, messages

        except Exception as e:
            logger.error(f"❌ Error in handle_space_booking: {e}", exc_info=True)
            err_msg = "Sorry, something went wrong with your space booking request. Please try again."
            return err_msg, err_msg, messages


space_booking_service = SpaceBookingService()
