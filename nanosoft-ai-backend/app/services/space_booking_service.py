import logging
import json
import asyncio
import re
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
    """Find a spot's full details by SpotCode or SpotName across all cached searches (case-insensitive)."""
    if not session_id or not spot_code:
        return None
    
    target_code = str(spot_code).strip().lower()
    sb_cache = memory_store.get(session_id, {}).get("sb_spot_cache", {})
    for cached_data in sb_cache.values():
        for spot in cached_data.get("p_list", []):
            cached_code = str(spot.get("SpotCode", spot.get("spotCode", spot.get("spotcode", "")))).strip().lower()
            cached_name = str(spot.get("SpotName", spot.get("spotName", spot.get("spotname", "")))).strip().lower()
            if cached_code == target_code or cached_name == target_code:
                return spot
    return None


async def _verify_spot_async(session_id: Optional[str], spot_code: str, user_name: str) -> Optional[dict]:
    """Verify spot from cache first. If not found, hit the DB (API) to get full data."""
    if not spot_code:
        return None
    
    # 1. Check cache
    verified = _lookup_spot_from_cache(session_id, spot_code)
    if verified:
        return verified
        
    # 2. Not in cache -> hit the DB
    logger.info("🔍 Spot %s not in cache, hitting DB for verification...", spot_code)
    try:
        api_result_str = await fetch_spots_api(user_name, spot_code)
        api_result = json.loads(api_result_str)
        target_code = str(spot_code).strip().lower()
        for spot in api_result.get("p_list", []):
            cached_code = str(spot.get("SpotCode", spot.get("spotCode", spot.get("spotcode", "")))).strip().lower()
            cached_name = str(spot.get("SpotName", spot.get("spotName", spot.get("spotname", "")))).strip().lower()
            if cached_code == target_code or cached_name == target_code:
                return spot
    except Exception as e:
        logger.error("❌ Failed DB verification for spot %s: %s", spot_code, e)
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
    """Reset the conversation thread after a completed booking.
    The __all__ spot cache is kept to avoid re-hitting the API.
    Per-search-term caches are cleared so fresh searches return correct filtered results
    instead of stale single-spot selections from the previous booking."""
    if session_id and session_id in memory_store:
        memory_store[session_id]["sb_thread"] = []
        # Clear per-term caches but preserve the __all__ full dataset cache
        sb_cache = memory_store[session_id].get("sb_spot_cache", {})
        all_data = sb_cache.get("__all__")
        memory_store[session_id]["sb_spot_cache"] = {"__all__": all_data} if all_data else {}
        logger.info("🗑️ sb_thread reset + per-term cache cleared (all-cache kept) | session=%s", session_id)


# ── Service ────────────────────────────────────────────────────────────────────

class SpaceBookingService:
    def __init__(self):
        try:
            self.model = ChatGoogleGenerativeAI(
                model=settings.GOOGLE_SPACE_BOOKING_MODEL,
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

            # ── Dynamic Spot Cache Injection for Direct/Metadata Queries ──
            if "SpotCode: " in current_query and session_id:
                import re
                s_code_match = re.search(r"SpotCode:\s*([^,|]+)", current_query)
                if s_code_match:
                    s_code = s_code_match.group(1).strip()
                    s_name_match = re.search(r"SpotName:\s*([^,|]+)", current_query)
                    s_name = s_name_match.group(1).strip() if s_name_match else "the spot"
                    s_bldg_match = re.search(r"BuildingName:\s*([^,|]+)", current_query)
                    s_bldg = s_bldg_match.group(1).strip() if s_bldg_match else "the building"
                    s_floor_match = re.search(r"FloorName:\s*([^,|]+)", current_query)
                    s_floor = s_floor_match.group(1).strip() if s_floor_match else ""
                    
                    spot_dict = {
                        "SpotCode": s_code,
                        "SpotName": s_name,
                        "BuildingName": s_bldg,
                        "FloorName": s_floor
                    }
                    
                    # Inject into both __all__ cache and term-specific cache to bypass API verification
                    cache_all = _get_cached_spots(session_id, None)
                    if not cache_all:
                        cache_all = {"TotalCount": 0, "p_list": []}
                    
                    exists = False
                    for existing_spot in cache_all.get("p_list", []):
                        if str(existing_spot.get("SpotCode")).strip().lower() == s_code.lower():
                            exists = True
                            break
                    if not exists:
                        cache_all["p_list"].append(spot_dict)
                        cache_all["TotalCount"] = len(cache_all["p_list"])
                        _set_cached_spots(session_id, None, cache_all)
                    
                    _set_cached_spots(session_id, s_code, {"TotalCount": 1, "p_list": [spot_dict]})
                    logger.info("✅ Dynamically cached clicked spot metadata: SpotCode=%s, SpotName=%s", s_code, s_name)

            # Load & extend the real per-session conversation thread
            sb_thread = _get_sb_thread(session_id)

            # ── Fast-path for direct tile clicks ──
            if current_query.startswith("SpotCode: ") and "[CALENDAR_PAYLOAD]" not in current_query:
                import re
                s_code_match = re.search(r"SpotCode:\s*([^,]+)", current_query)
                if s_code_match:
                    s_code = s_code_match.group(1).strip()
                    s_name_match = re.search(r"SpotName:\s*([^,]+)", current_query)
                    s_name = s_name_match.group(1).strip() if s_name_match else "the spot"
                    s_bldg_match = re.search(r"BuildingName:\s*([^,]+)", current_query)
                    s_bldg = s_bldg_match.group(1).strip() if s_bldg_match else "the building"
                    s_floor_match = re.search(r"FloorName:\s*(.*)", current_query)
                    s_floor = s_floor_match.group(1).strip() if s_floor_match else ""
                    
                    floor_part = f", {s_floor}" if s_floor else ""
                    content = (
                        f"Great choice! You've selected {s_name} (Spot Code: {s_code}) "
                        f"at {s_bldg}{floor_part}. "
                        f"To complete your booking, please use the calendar to select "
                        f"your preferred start and end time."
                    )
                    logger.info("⚡ Fast-path (Direct Click): bypassing LLM for spot=%s", s_code)
                    sb_thread.append(HumanMessage(content=current_query))
                    sb_thread.append(AIMessage(content=content))
                    _save_sb_thread(session_id, sb_thread)
                    return content, content, messages



            # Inject strict instruction to prevent the LLM from hallucinating bullet points from memory
            injected_query = (
                f"{current_query}\n\n"
                f"[SYSTEM: EVERY SINGLE search or location query from the user MUST hit the cache by calling GET_SPOTS immediately. "
                f"Even if they are just refining a previous search, you MUST call GET_SPOTS again. "
                f"NEVER answer from memory or history when asked to book or search. You MUST use GET_SPOTS. "
                f"NEVER say 'I couldn't find any spots' or 'I don't see any spots' WITHOUT actually calling GET_SPOTS first! "
                f"NEVER output bullet points or lists of spaces in your text response! The UI will render the list for you. "
                f"Only GET_BOOKING_STATUS is allowed to use bullet points. "
                f"If you do not call a tool, you MUST output a conversational response explaining what you need from the user.]"
            )
            sb_thread.append(HumanMessage(content=current_query))

            # ── Just-in-Time (JIT) Dynamic Prompt Hydration ──
            # Fetch active buildings dynamically from cache or API to load into LLM system prompt context
            cached_all = _get_cached_spots(session_id, None) if session_id else None
            if cached_all is None:
                logger.info("🌐 JIT Context Hydration: Fetching spots list to extract active buildings")
                try:
                    all_spots_str = await fetch_spots_api(user_name, None)
                    all_spots_data = json.loads(all_spots_str)
                    if session_id and isinstance(all_spots_data, dict) and "p_list" in all_spots_data:
                        _set_cached_spots(session_id, None, all_spots_data)
                    cached_all = all_spots_data
                except Exception as e:
                    logger.error(f"❌ Failed JIT fetching: {e}")
                    cached_all = {}

            unique_buildings = []
            if cached_all and isinstance(cached_all, dict) and "p_list" in cached_all:
                unique_buildings = sorted(list(set(
                    str(s.get("BuildingName")) for s in cached_all.get("p_list", []) if s.get("BuildingName")
                )))

            from datetime import datetime, timezone, timedelta
            # Calculate current India time (UTC+5:30)
            current_ist_time = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
            current_date_str = current_ist_time.strftime("%Y-%m-%d")
            current_time_str = current_ist_time.strftime("%Y-%m-%d %I:%M %p (India Time)")

            # Build prompt dynamically with injected live directory and strict guardrails
            hydrated_content = (
                self.system_prompt.content + 
                f"\n\nCURRENT DATE: {current_date_str}."
                f"\nCURRENT INDIA TIME: {current_time_str}."
                f"\nCRITICAL: You are operating in India Time. If the user asks for a time that has ALREADY PASSED according to the CURRENT INDIA TIME, you MUST NOT call BOOK_SPOT. Tell them they cannot book in the past."
                f"\nCURRENT USER_NAME: {user_name}."
                "\nCRITICAL: If the user's message contains a specific Spot Code but does NOT contain the calendar booking payload ([CALENDAR_PAYLOAD]), you MUST call GET_SPOTS to verify it exists and retrieve its building and floor details. NEVER call BOOK_SPOT with unknown or hallucinated spot details. Once verified, ask them to 'use the calendar' to select a time."
                "\nCRITICAL: If the user searches for any kind of space, keyword, floor name, or tries to refine the list (e.g., 'floor 6', 'floor6', 'Building 1'), you MUST call GET_SPOTS immediately. You MUST pass the user's query exactly as entered (including single squished words like 'floor6') as the search_term. Do NOT pass an empty string, None, or modify the query before calling GET_SPOTS."
                "\nCRITICAL: If the user's message is a conversational affirmation, confirmation, or agreement in response to your suggestion, do NOT call GET_SPOTS. Instead, ask them to specify which building or floor they would like to search or try."
                "\nCRITICAL: If the user's message is a general intent to book, you MUST call GET_SPOTS immediately to show them the available options. Do NOT respond with conversational clarification questions. Just call the tool."
                "\nCRITICAL: When asking the user for their booking times, you MUST include the exact phrase 'use the calendar' in your response. Do NOT ask the user to type, share, write, or tell you their start and end time manually."
                "\nCRITICAL: Never call BOOK_SPOT unless the COMPLETE date (including the year) and the time have been provided by the user (either in their latest message, or established in the recent conversation history) or via a structured calendar message. If the user provides a month and day but NOT the year, you MUST NOT call BOOK_SPOT. Instead, ask the user to confirm the year for their booking."
                f"\nCRITICAL: If the user requests a booking for a date or time that is in the past (before {current_date_str}), you MUST NOT call BOOK_SPOT. Instead, reply immediately: 'You cannot create a booking for a past date. Please select a present or future date.'"
                "\nCRITICAL: If the calendar booking payload ([CALENDAR_PAYLOAD]) is present in the user message (e.g. '[CALENDAR_PAYLOAD] start_time: ...'), this means the user used the calendar UI. You MUST call BOOK_SPOT immediately using the start_time and end_time from the payload (even if they are in 24-hour format). You MUST NOT ask for AM/PM confirmation, and you MUST NOT call GET_SPOTS. Only ask for AM/PM confirmation if the user typed dates/times via conversational text without any '[CALENDAR_PAYLOAD]' present."
            )
            if unique_buildings:
                hydrated_content += f"\n\nLIVE ACTIVE BUILDINGS DIRECTORY TODAY (DYNAMIC): {', '.join(unique_buildings)}"

            sys_msg = SystemMessage(content=hydrated_content)
            # Create a temporary HumanMessage with the injected JIT directives only for this invoke,
            # so the DB thread history doesn't save the system directives.
            temp_human = HumanMessage(content=injected_query)
            prompt_messages = [sys_msg] + sb_thread[:-1] + [temp_human]

            # First model invoke
            ai_msg = await self.model.ainvoke(prompt_messages)

            tool_data = None
            last_tool_called = None
            booking_status_data = None

            if ai_msg.tool_calls:
                prompt_messages.append(ai_msg)
                sb_thread.append(ai_msg)

                for tc in ai_msg.tool_calls:
                    last_tool_called = tc["name"]

                    # ── GET_SPOTS ─────────────────────────────────────────────
                    if tc["name"] == "GET_SPOTS":
                        s_term = tc["args"].get("search_term")

                        if "[CALENDAR_PAYLOAD]" in current_query:
                            logger.warning("⚠️ Programmatically blocked GET_SPOTS call during [CALENDAR_PAYLOAD] processing")
                            tool_data = {"TotalCount": 0, "p_list": []}
                            tool_result_str = json.dumps({
                                "success": False,
                                "error": "GET_SPOTS is disabled when a booking calendar payload is present. You MUST call BOOK_SPOT immediately."
                            })
                        else:
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
                                    from app.tools.space_booking_tool import fuzzy_filter_spots
                                    p_list_all = all_cached.get("p_list", [])
                                    filtered = fuzzy_filter_spots(s_term, p_list_all)
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

                        # Send only 4 compressed fields to LLM (Stateless In-Context Retrieval / Ephemeral RAG)
                        if isinstance(tool_data, dict) and "p_list" in tool_data:
                            compressed = [
                                {f: s.get(f) for f in _TABLE_FIELDS}
                                for s in tool_data.get("p_list", [])
                            ]
                            llm_payload = {
                                "TotalCount": tool_data.get("TotalCount"),
                                "spots": compressed
                            }
                            # If search term doesn't match any spots, dynamically inject the unique buildings directory
                            if tool_data.get("TotalCount") == 0:
                                all_spots_cache = _get_cached_spots(session_id, None) if session_id else None
                                if all_spots_cache and "p_list" in all_spots_cache:
                                    llm_payload["available_buildings"] = sorted(list(set(
                                        str(s.get("BuildingName")) for s in all_spots_cache.get("p_list", []) if s.get("BuildingName")
                                    )))
                            llm_content = json.dumps(llm_payload)
                        else:
                            llm_content = tool_result_str

                        tool_msg = ToolMessage(
                            name=tc["name"], tool_call_id=tc["id"], content=llm_content
                        )
                        prompt_messages.append(tool_msg)
                        sb_thread.append(tool_msg)



                    # ── BOOK_SPOT ─────────────────────────────────────────────
                    elif tc["name"] == "BOOK_SPOT":
                        args = tc["args"]
                        args["user_name"] = user_name
                        if sub_user_name:
                            args["sub_user_name"] = sub_user_name

                        # ── Verify spot details from cache or DB (prevents hallucination) ─
                        spot_code_req = args.get("spot_code", "")
                        verified = await _verify_spot_async(session_id, spot_code_req, user_name)
                        if verified:
                            args["spot_code"]     = verified.get("SpotCode", verified.get("spotCode", verified.get("spotcode", args.get("spot_code"))))
                            args["spot_name"]     = verified.get("SpotName", verified.get("spotName", verified.get("spotname", args.get("spot_name"))))
                            args["building_name"] = verified.get("BuildingName", verified.get("buildingName", verified.get("buildingname", args.get("building_name"))))
                            args["floor_name"]    = verified.get("FloorName", verified.get("floorName", verified.get("floorname", args.get("floor_name"))))
                            logger.info("✅ Spot verified: %s → %s (real spot_code: %s)", spot_code_req, args["spot_name"], args["spot_code"])
                            tool_result_str = await BOOK_SPOT.ainvoke(args)
                        else:
                            logger.warning("❌ Spot hallucinated or invalid: %s", spot_code_req)
                            tool_result_str = json.dumps({
                                "success": False,
                                "error": "Invalid SpotCode. You MUST search and verify the spot using GET_SPOTS first before booking."
                            })

                        try:
                            parsed_res = json.loads(tool_result_str)

                            if parsed_res.get("error_type") == "missing_time":
                                spot_code = parsed_res.get("spot_code", "the spot")
                                building  = parsed_res.get("building_name", "the building")

                                tool_msg = ToolMessage(
                                    name=tc["name"], tool_call_id=tc["id"],
                                    content=json.dumps({
                                        "error_type": "missing_time",
                                        "instruction": (
                                            f"Time not provided. Ask the user warmly for their preferred time "
                                            f"for booking {spot_code} at {building}. "
                                            f"CRITICAL: You MUST include the exact phrase 'use the calendar' in your response."
                                        )
                                    })
                                )
                                prompt_messages.append(tool_msg)
                                sb_thread.append(tool_msg)
                                ai_msg2 = await self.model.ainvoke(prompt_messages)
                                time_ask = ai_msg2.content or (
                                    f"When would you like to book **{spot_code}** at **{building}**? "
                                    f"Please use the calendar to select your preferred start and end time."
                                )
                                logger.info("⏰ Missing time — asking: %s", time_ask[:100])
                                sb_thread.append(AIMessage(content=time_ask))
                                _save_sb_thread(session_id, sb_thread)
                                return time_ask, time_ask, messages

                            if parsed_res.get("success"):
                                logger.info("✅ Booking success | id=%s", parsed_res.get("booking_id"))

                        except json.JSONDecodeError:
                            pass

                        tool_msg = ToolMessage(
                            name=tc["name"], tool_call_id=tc["id"], content=tool_result_str
                        )
                        prompt_messages.append(tool_msg)
                        sb_thread.append(tool_msg)

                    # ── GET_BOOKING_STATUS ────────────────────────────────────
                    elif tc["name"] == "GET_BOOKING_STATUS":
                        args = tc["args"]
                        args["user_name"] = user_name
                        tool_result_str = await GET_BOOKING_STATUS.ainvoke(args)
                        logger.info("🔍 GET_BOOKING_STATUS result: %s", tool_result_str[:200])
                        try:
                            booking_status_data = json.loads(tool_result_str)
                        except Exception as e:
                            logger.error("Failed to parse GET_BOOKING_STATUS result: %s", e)

                        tool_msg = ToolMessage(
                            name=tc["name"], tool_call_id=tc["id"], content=tool_result_str
                        )
                        prompt_messages.append(tool_msg)
                        sb_thread.append(tool_msg)

                # Final model response
                ai_msg2 = await self.model.ainvoke(prompt_messages)
                content = _extract_content(ai_msg2)

                # ── Fast-path: single-spot GET_SPOTS result + empty ai_msg2 ──────────────────
                # When the user says "book this GPRF-KFC" (spot code without SpotCode: prefix),
                # the LLM correctly finds the spot via GET_SPOTS but then returns empty content.
                # Instead of hitting the generic fallback, synthesize the Stage 3 calendar
                # confirmation directly from the cached spot data — no extra LLM call needed.
                if (
                    not content.strip()
                    and not ai_msg2.tool_calls
                    and last_tool_called == "GET_SPOTS"
                    and tool_data
                    and isinstance(tool_data.get("p_list"), list)
                    and len(tool_data["p_list"]) == 1
                ):
                    spot = tool_data["p_list"][0]
                    s_code  = spot.get("SpotCode", "")
                    s_name  = spot.get("SpotName", "the spot")
                    s_bldg  = spot.get("BuildingName", "the building")
                    s_floor = spot.get("FloorName", "")
                    floor_part = f", {s_floor}" if s_floor else ""
                    content = (
                        f"Great choice! I have found {s_name} (Spot Code: {s_code}) "
                        f"at {s_bldg}{floor_part}. "
                        f"To complete your booking, please use the calendar to select "
                        f"your preferred start and end date and time."
                    )
                    logger.info(
                        "⚡ Fast-path Stage-3: single-spot GET_SPOTS → calendar prompt | spot=%s", s_code
                    )
                    sb_thread.append(AIMessage(content=content))
                    _save_sb_thread(session_id, sb_thread)
                    return content, content, messages

                # ── Handle the case where the model makes ANOTHER tool call instead of replying ──
                # This happens when the LLM skips Phase 2 and tries to call BOOK_SPOT immediately
                # after GET_SPOTS, resulting in empty .content.
                if not content.strip() and ai_msg2.tool_calls:
                    logger.info("⚡ ai_msg2 has tool_calls but no content — handling inline")
                    prompt_messages.append(ai_msg2)
                    sb_thread.append(ai_msg2)

                    for tc2 in ai_msg2.tool_calls:
                        if tc2["name"] == "BOOK_SPOT":
                            args2 = tc2["args"]
                            args2["user_name"] = user_name
                            if sub_user_name:
                                args2["sub_user_name"] = sub_user_name

                            # Verify spot from cache or DB to prevent hallucination
                            spot_code_req2 = args2.get("spot_code", "")
                            verified2 = await _verify_spot_async(session_id, spot_code_req2, user_name)
                            if verified2:
                                args2["spot_code"]     = verified2.get("SpotCode", verified2.get("spotCode", verified2.get("spotcode", args2.get("spot_code"))))
                                args2["spot_name"]     = verified2.get("SpotName", verified2.get("spotName", verified2.get("spotname", args2.get("spot_name"))))
                                args2["building_name"] = verified2.get("BuildingName", verified2.get("buildingName", verified2.get("buildingname", args2.get("building_name"))))
                                args2["floor_name"]    = verified2.get("FloorName", verified2.get("floorName", verified2.get("floorname", args2.get("floor_name"))))
                                logger.info("✅ Spot verified (round-2): %s → %s (real spot_code: %s)", spot_code_req2, args2["spot_name"], args2["spot_code"])
                                tool_result2_str = await BOOK_SPOT.ainvoke(args2)
                            else:
                                logger.warning("❌ Spot hallucinated or invalid (round-2): %s", spot_code_req2)
                                tool_result2_str = json.dumps({
                                    "success": False,
                                    "error": "Invalid SpotCode. You MUST search and verify the spot using GET_SPOTS first before booking."
                                })
                            try:
                                parsed2 = json.loads(tool_result2_str)
                                if parsed2.get("error_type") == "missing_time":
                                    spot_code2   = parsed2.get("spot_code", args2.get("spot_code", "the spot"))
                                    building2    = parsed2.get("building_name", args2.get("building_name", "the building"))
                                    tool_msg2 = ToolMessage(
                                        name=tc2["name"], tool_call_id=tc2["id"],
                                        content=json.dumps({
                                            "error_type": "missing_time",
                                            "instruction": (
                                                f"Time not provided. Ask the user warmly for their preferred time "
                                                f"for booking {spot_code2} at {building2}. "
                                                f"CRITICAL: You MUST include the exact phrase 'use the calendar' in your response."
                                            )
                                        })
                                    )
                                    prompt_messages.append(tool_msg2)
                                    sb_thread.append(tool_msg2)
                                    ai_msg3 = await self.model.ainvoke(prompt_messages)
                                    time_ask = ai_msg3.content or (
                                        f"Almost there! Please use the calendar to select your preferred start and end time "
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

                            tool_msg2 = ToolMessage(
                                name=tc2["name"], tool_call_id=tc2["id"], content=tool_result2_str
                            )
                            prompt_messages.append(tool_msg2)
                            sb_thread.append(tool_msg2)

                        elif tc2["name"] == "GET_SPOTS":
                            # Shouldn't re-call GET_SPOTS, but handle gracefully
                            logger.warning("⚠️ Unexpected second GET_SPOTS call — skipping")
                            tool_msg2 = ToolMessage(
                                name=tc2["name"], tool_call_id=tc2["id"],
                                content=json.dumps({"info": "Spots already retrieved. Use the previous results."})
                            )
                            prompt_messages.append(tool_msg2)
                            sb_thread.append(tool_msg2)

                    # Get final content after handling round-2 tool calls
                    ai_msg3 = await self.model.ainvoke(prompt_messages)
                    content = _extract_content(ai_msg3)



                # Manage thread after tool response
                try:
                    last_result = json.loads(prompt_messages[-1].content)
                    if last_result.get("success"):
                        # If LLM didn't generate a conversational confirmation, provide one
                        if not content.strip():
                            b_id = last_result.get('booking_id', '')
                            content = f"Your spot has been successfully booked! (Booking ID: {b_id})" if b_id else "Your spot has been successfully booked!"
                            
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
                if tool_data and "p_list" in tool_data and len(tool_data["p_list"]) >= 1:
                    total = tool_data.get("TotalCount", len(tool_data["p_list"]))
                    p_list = tool_data["p_list"]

                    # For large result sets (>8), override the AI summary with a short message
                    # so the AI doesn't dump the full list into the text — the tiles handle display
                    if total > 8:
                        unique_bldgs = sorted(list(set(s.get("BuildingName") for s in p_list if s.get("BuildingName"))))
                        if len(unique_bldgs) == 1:
                            building_label = f"at {unique_bldgs[0]}"
                        else:
                            building_label = "across our locations"
                        summary = (
                            f"You've got {total} spaces available {building_label}. "
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
                    # Final fallback if LLM is completely silent
                    if not content.strip():
                        content = "I'm sorry, I couldn't find any spots matching that description. Could you try a different name or area?"
                    return content, content, messages


            # No tool called — pure conversational
            content = _extract_content(ai_msg)
            
            if not content.strip():
                content = "I'm sorry, I couldn't find any spots matching that description. Could you try a different name or area?"

            sb_thread.append(AIMessage(content=content))
            _save_sb_thread(session_id, sb_thread)
            return content, content, messages

        except Exception as e:
            logger.error(f"❌ Error in handle_space_booking: {e}", exc_info=True)
            err_msg = "Sorry, something went wrong with your space booking request. Please try again."
            return err_msg, err_msg, messages


space_booking_service = SpaceBookingService()
