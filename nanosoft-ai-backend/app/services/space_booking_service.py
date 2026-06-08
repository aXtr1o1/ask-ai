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
                content=self.system_prompt.content + (
                    f"\n\nCURRENT USER_NAME: {user_name}. "
                    "YOUR PERSONA: You are a warm, enthusiastic space booking agent — not a data retrieval system. "
                    "Always speak like you are personally helping the user book their ideal space, using friendly and encouraging language. "
                    "Never say 'I found X results' or 'I retrieved X spaces' — instead say 'Great! X spaces are available for your meeting!' or similar. "
                    "IMPORTANT REMINDERS: "
                    "(1) When user wants to see available BUILDINGS, call GET_SPOTS with list_buildings_only=True. Respond with ONE short warm booking-agent sentence only — do NOT list building names in your text. "
                    "(2) When user wants to browse all spaces, call GET_SPOTS with NO search_term. You will see TotalCount and a sample of 15 spots — the user sees ALL tiles. Say one enthusiastic sentence about the count and invite them to browse. "
                    "(3) When user mentions a building, floor, spot code, or type, call GET_SPOTS with that as search_term. "
                    "(4) When spots are shown as tiles, do NOT list them in your text — one short warm booking-agent sentence only. "
                    "(5) When you have presented a spot and the user confirms they want to book it, "
                    "THEN and ONLY THEN say 'use the calendar'. "
                    "Do NOT show the calendar when first presenting a spot — always ask for confirmation first. "
                    "(6) Never use bullet points, asterisks, numbered lists, or any markdown — plain natural sentences only. "
                    "(7) CRITICAL TILE-CLICK RULE: When the user's message starts with 'I\\'d like to book this spot' and contains 'SpotCode:', this is an AUTO-GENERATED message from the user clicking a space tile. "
                    "The user has ALREADY selected their spot. DO NOT call GET_SPOTS. DO NOT ask for confirmation. "
                    "Immediately respond in Stage 3 mode: acknowledge the spot warmly and say 'use the calendar' to pick date and time. "
                    "Example trigger: 'I\\'d like to book this spot — SpotCode: WRMF-NES, SpotName: WASH ROOMS, Building: Reef Mall, Floor: GF Level'. "
                    "Your response: 'Perfect! To complete your booking for WASH ROOMS at Reef Mall, please use the calendar to select your preferred start and end date and time.'"
                )
            )
            prompt_messages = [sys_msg] + sb_thread

            # (Confirmation pre-check removed as requested. The model will handle it via rule 7)

            # First model invoke
            ai_msg = await self.model.ainvoke(prompt_messages)

            tool_data = None

            if ai_msg.tool_calls:
                prompt_messages.append(ai_msg)

                for tc in ai_msg.tool_calls:

                    # ── GET_SPOTS ─────────────────────────────────────────────
                    if tc["name"] == "GET_SPOTS":
                        s_term = tc["args"].get("search_term")
                        want_buildings = bool(tc["args"].get("list_buildings_only", False))

                        # ── Buildings-only fast path ──────────────────────────
                        if want_buildings:
                            # Try to build buildings list from __all__ cache first
                            all_cached = _get_cached_spots(session_id, None) if session_id else None
                            if all_cached is not None:
                                p_list_all = all_cached.get("p_list", [])
                                seen = set()
                                unique_buildings = []
                                for spot in p_list_all:
                                    b = spot.get("BuildingName", "").strip()
                                    if b and b not in seen:
                                        seen.add(b)
                                        unique_buildings.append({"BuildingName": b})
                                logger.info("🏢 Buildings from __all__ cache | count=%d", len(unique_buildings))
                            else:
                                # Need to fetch all spots first
                                logger.info("🌐 Buildings-only: fetching all spots from API")
                                raw_str = await fetch_spots_api(user_name, None, list_buildings_only=True)
                                raw_data = json.loads(raw_str)
                                unique_buildings = raw_data.get("p_list", [])
                            tool_data = {"type": "buildings_list", "p_list": unique_buildings}
                            n_buildings = len(unique_buildings)
                            tool_result_str = json.dumps({
                                "total_buildings": n_buildings,
                                "context_hint": (
                                    f"There are {n_buildings} buildings available. "
                                    f"Respond with ONE short natural sentence that tells the user the count and that the full list is shown below. "
                                    f"Example: 'We have {n_buildings} buildings available — take a look at the list below and let me know which one interests you.'"
                                ),
                                "buildings": [b["BuildingName"] for b in unique_buildings]
                            })
                            prompt_messages.append(ToolMessage(
                                name=tc["name"], tool_call_id=tc["id"], content=tool_result_str
                            ))
                            continue  # skip the normal spot cache/API path below

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
                                total_filtered = len(filtered)
                                # Store ALL results in cache — tiles show everything, LLM gets sample
                                tool_data = {"TotalCount": total_filtered, "p_list": filtered}
                                tool_result_str = json.dumps(tool_data)
                                if session_id:
                                    _set_cached_spots(session_id, s_term, tool_data)
                                logger.info("📦 Filtered from __all__ cache (no API call) | matches=%d | all stored", total_filtered)
                            else:
                                logger.info("🌐 Cache MISS — calling API")
                                tool_result_str = await fetch_spots_api(user_name, s_term)
                                try:
                                    tool_data = json.loads(tool_result_str)
                                except Exception:
                                    tool_data = {"error": "Invalid JSON"}
                                if session_id and isinstance(tool_data, dict) and "p_list" in tool_data:
                                    _set_cached_spots(session_id, s_term, tool_data)


                        # Send ONLY summary + top 15 sample spots to LLM — never dump all records.
                        # The full p_list goes to the frontend as tiles (records), not to the LLM.
                        if isinstance(tool_data, dict) and "p_list" in tool_data:
                            sample = tool_data["p_list"][:15]
                            compressed = [
                                {f: s.get(f) for f in _TABLE_FIELDS}
                                for s in sample
                            ]
                            total = tool_data.get("TotalCount") or len(tool_data["p_list"])
                            showing = len(compressed)

                            # Build a context_hint so the model generates accurate, booking-agent-toned text
                            if not s_term:
                                # Browse all: all tiles shown to user
                                context_hint = (
                                    f"There are {total} spaces available across all buildings — all shown as tiles. "
                                    f"You are a space booking agent. Respond with ONE short, warm, booking-agent sentence that mentions the total count and tells the user they can click any tile to select a space, or say a building/floor/code to narrow it down. "
                                    f"Example: 'Great news — we have {total} spaces ready for your booking! Click any tile below to select a space, or tell me a building, floor, or spot code to find the perfect match.'"
                                )
                            elif total == 1:
                                # Exactly 1 match — present the spot and ask for confirmation first.
                                # Do NOT ask for calendar yet — wait for the user to say yes/confirm.
                                spot = compressed[0] if compressed else {}
                                spot_code = spot.get('SpotCode', '')
                                spot_name = spot.get('SpotName', '')
                                building = spot.get('BuildingName', '')
                                floor = spot.get('FloorName', '')
                                # Build a description that avoids SpotName==BuildingName repetition
                                if spot_name and spot_name != building:
                                    spot_desc = f"{spot_name} ({spot_code}) on {floor} at {building}"
                                elif spot_code:
                                    spot_desc = f"{spot_code} on {floor} at {building}"
                                else:
                                    spot_desc = f"{building}, {floor}"
                                context_hint = (
                                    f"Exactly 1 space available: SpotCode={spot_code}, "
                                    f"SpotName={spot_name}, "
                                    f"BuildingName={building}, "
                                    f"FloorName={floor}. "
                                    f"You are a booking agent. Present this space to the user, ask if they would like to book it, and tell them they can click the tile or say 'yes' to confirm. "
                                    f"DO NOT mention the calendar yet — only ask for confirmation. "
                                    f"Example: 'I found {spot_desc} — click the tile or say yes and I will get your booking sorted!'"
                                )
                            else:
                                # Multiple results: booking-agent tone
                                context_hint = (
                                    f"{total} spaces are available and all are shown as tiles. "
                                    f"You are a booking agent. Respond with ONE short, warm, enthusiastic sentence that mentions the count, tells the user to click any tile to select a space, or narrow down by floor/spot code. "
                                    f"Example: 'Great! {total} spaces are available — click any tile to select one, or tell me a floor or spot code to narrow it down.'"
                                )

                            llm_content = json.dumps({
                                "TotalCount": total,
                                "showing": showing,
                                "context_hint": context_hint,
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
                    # Model returned empty — re-invoke with an explicit nudge to respond
                    logger.warning("⚠️ Empty content — re-invoking model for natural response")
                    prompt_messages.append(HumanMessage(
                        content="Please respond naturally based on the results above."
                    ))
                    ai_msg_retry = await self.model.ainvoke(prompt_messages)
                    content = _extract_content(ai_msg_retry)

                # Manage thread after tool response
                # Stage 3 detection: model asked user to "use the calendar" AND
                # there is only 1 spot result (specific spot confirmed) → skip tiles.
                # IMPORTANT: if multiple spots were returned, always show tiles even if
                # model incorrectly said "use the calendar" (Stage 2 confusion).
                p_list_len = len(tool_data.get("p_list", [])) if isinstance(tool_data, dict) else 0
                is_stage3 = (
                    "use the calendar" in content.lower()
                    and p_list_len <= 1
                    and tool_data.get("type") != "buildings_list"
                )

                # Buildings-list mode: return as clean text list (no tiles)
                if tool_data and tool_data.get("type") == "buildings_list":
                    buildings = tool_data.get("p_list", [])
                    building_names = [b.get("BuildingName", "") for b in buildings if b.get("BuildingName")]
                    # Model already has the building list from the ToolMessage and generates
                    # a natural intro. Use that but ensure it's just ONE short sentence.
                    # Strip any trailing comma/list the model may have appended.
                    intro_line = content.split("\n")[0].strip().rstrip(":")
                    if not intro_line:
                        intro_line = f"Here are the {len(building_names)} available buildings."
                    building_text = "\n".join(building_names)
                    full_response = f"{intro_line}\n\n{building_text}"
                    return full_response, full_response, messages

                # Spot tiles mode: show spot tiles for search/browse results
                # ALWAYS show a tile for single result (even in Stage 3) so user can
                # confirm which space they're booking before the calendar opens.
                # For multiple results, suppress tiles only if Stage 3 triggered.
                elif (not is_stage3 or p_list_len == 1) and tool_data and "p_list" in tool_data and len(tool_data["p_list"]) >= 1:
                    p_list = tool_data["p_list"]
                    # Let the model speak — use its natural response as the summary
                    # We only provide the tile records; the model decides the message
                    final_response = {
                        "type": "large_dataset",
                        "context_summary": content,
                        "records": _slim_records(p_list)  # ← 4 fields only
                    }
                    return json.dumps(final_response), content, messages
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
