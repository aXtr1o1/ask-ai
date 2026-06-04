import logging
import json
import asyncio
from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import settings
from app.tools.space_booking_tool import GET_SPOTS, BOOK_SPOT, fetch_spots_api
from app.prompts.space_booking_prompt import SPACE_BOOKING_SYSTEM_PROMPT
from app.state import memory_store

logger = logging.getLogger("space_booking_service")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(ch)

# ── How many turns of space booking history to keep in memory ──────────────────
SB_THREAD_MAX_MESSAGES = 20


def _cache_key(search_term: Optional[str]) -> str:
    """Normalise a search term into a consistent cache key."""
    return (search_term or "__all__").strip().lower()


def _get_cached_spots(session_id: str, search_term: Optional[str]) -> Optional[dict]:
    """Return cached spot data for this session+search_term, or None."""
    cache = memory_store.get(session_id, {}).get("sb_spot_cache", {})
    key = _cache_key(search_term)
    result = cache.get(key)
    if result is not None:
        logger.info("✅ Cache HIT | session=%s | key=%s | spots=%d",
                    session_id, key, result.get("TotalCount", 0))
    return result


def _set_cached_spots(session_id: str, search_term: Optional[str], data: dict):
    """Store spot data in the session cache."""
    if session_id not in memory_store:
        memory_store[session_id] = {}
    if "sb_spot_cache" not in memory_store[session_id]:
        memory_store[session_id]["sb_spot_cache"] = {}
    key = _cache_key(search_term)
    memory_store[session_id]["sb_spot_cache"][key] = data
    logger.info("💾 Cache SET | session=%s | key=%s | spots=%d",
                session_id, key, data.get("TotalCount", 0))


def _get_sb_thread(session_id: Optional[str]) -> list:
    """Retrieve the per-session space booking conversation thread."""
    if not session_id:
        return []
    return list(memory_store.get(session_id, {}).get("sb_thread", []))


def _save_sb_thread(session_id: Optional[str], thread: list):
    """Persist the updated thread back to session memory (trimmed)."""
    if not session_id:
        return
    if session_id not in memory_store:
        memory_store[session_id] = {}
    memory_store[session_id]["sb_thread"] = thread[-SB_THREAD_MAX_MESSAGES:]
    logger.info("💾 sb_thread saved | session=%s | msgs=%d", session_id, len(thread))


def _clear_sb_thread(session_id: Optional[str]):
    """Clear the thread after a completed booking so the next flow starts fresh."""
    if session_id and session_id in memory_store:
        memory_store[session_id]["sb_thread"] = []
        memory_store[session_id]["sb_spot_cache"] = {}
        logger.info("🗑️ sb_thread + sb_spot_cache cleared | session=%s", session_id)


class SpaceBookingService:
    def __init__(self):
        try:
            self.model = ChatGoogleGenerativeAI(
                model=settings.GOOGLE_AI_MODEL,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=0.0
            ).bind_tools([GET_SPOTS, BOOK_SPOT])

            self.system_prompt = SPACE_BOOKING_SYSTEM_PROMPT
            logger.info("🚀 SpaceBookingService initialized with tools")
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
            logger.info(f"🚀 Handling space booking for {user_name} | session={session_id}")

            # ── 1. Extract current user query from the incoming messages ──────────
            current_query = ""
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    current_query = msg.content
                    break

            logger.info("📝 Current query: %s", current_query[:120])

            # ── 2. Load per-session sb_thread (real HumanMessage/AIMessage chain) ─
            sb_thread = _get_sb_thread(session_id)
            sb_thread.append(HumanMessage(content=current_query))

            # ── 3. Build prompt: space booking system prompt + real thread ─────────
            sys_msg = SystemMessage(
                content=self.system_prompt.content + f"\n\nCURRENT USER_NAME: {user_name}"
            )
            prompt_messages = [sys_msg] + sb_thread

            # ── 4. First model invoke ─────────────────────────────────────────────
            ai_msg = await self.model.ainvoke(prompt_messages)

            tool_data = None

            # ── 5. Tool handling ───────────────────────────────────────────────────
            if ai_msg.tool_calls:
                prompt_messages.append(ai_msg)

                for tc in ai_msg.tool_calls:

                    # ── GET_SPOTS ─────────────────────────────────────────────────
                    if tc["name"] == "GET_SPOTS":
                        s_term = tc["args"].get("search_term")

                        cached = _get_cached_spots(session_id, s_term) if session_id else None
                        if cached is not None:
                            logger.info("📦 Using cached spots — skipping API call")
                            tool_data = cached
                            tool_result_str = json.dumps(cached)
                        else:
                            logger.info("🌐 Cache MISS — calling GET_SPOTS API")
                            tool_result_str = await fetch_spots_api(user_name, s_term)
                            try:
                                tool_data = json.loads(tool_result_str)
                            except Exception:
                                tool_data = {"error": "Invalid JSON response"}

                            if session_id and isinstance(tool_data, dict) and "p_list" in tool_data:
                                _set_cached_spots(session_id, s_term, tool_data)

                        # Compress to 4 fields for LLM — saves tokens
                        if isinstance(tool_data, dict) and "p_list" in tool_data:
                            compressed = [
                                {
                                    "SpotCode": s.get("SpotCode"),
                                    "SpotName": s.get("SpotName"),
                                    "BuildingName": s.get("BuildingName"),
                                    "FloorName": s.get("FloorName"),
                                }
                                for s in tool_data.get("p_list", [])
                            ]
                            llm_content = json.dumps({
                                "TotalCount": tool_data.get("TotalCount"),
                                "spots": compressed
                            })
                        else:
                            llm_content = tool_result_str

                        prompt_messages.append(ToolMessage(
                            name=tc["name"],
                            tool_call_id=tc["id"],
                            content=llm_content
                        ))

                    # ── BOOK_SPOT ─────────────────────────────────────────────────
                    elif tc["name"] == "BOOK_SPOT":
                        args = tc["args"]
                        args["user_name"] = user_name
                        if sub_user_name:
                            args["sub_user_name"] = sub_user_name

                        tool_result_str = await BOOK_SPOT.ainvoke(args)

                        try:
                            parsed_res = json.loads(tool_result_str)

                            # ── Missing time — ask the user for it ────────────────
                            if parsed_res.get("error_type") == "missing_time":
                                spot_code = parsed_res.get("spot_code", "the spot")
                                building  = parsed_res.get("building_name", "the building")

                                prompt_messages.append(ToolMessage(
                                    name=tc["name"],
                                    tool_call_id=tc["id"],
                                    content=json.dumps({
                                        "error_type": "missing_time",
                                        "instruction": (
                                            f"Timing was not provided. Ask the user for their preferred time "
                                            f"for booking {spot_code} at {building}. "
                                            f"Do NOT call BOOK_SPOT again until the user's next message contains an actual time."
                                        )
                                    })
                                ))

                                ai_msg2 = await self.model.ainvoke(prompt_messages)
                                time_ask = ai_msg2.content or (
                                    f"What is your preferred time for booking **{spot_code}** at **{building}**? "
                                    f"(e.g., 10am, 2pm–4pm, morning)"
                                )
                                logger.info("⏰ Missing time — asking user: %s", time_ask[:100])

                                # Save thread with the time-ask so next turn has full context
                                sb_thread.append(AIMessage(content=time_ask))
                                _save_sb_thread(session_id, sb_thread)
                                return time_ask, time_ask, messages

                            # ── Booking succeeded — clear thread for next flow ─────
                            if parsed_res.get("success"):
                                logger.info("✅ Booking success | booking_id=%s", parsed_res.get("booking_id"))

                        except json.JSONDecodeError:
                            pass

                        prompt_messages.append(ToolMessage(
                            name=tc["name"],
                            tool_call_id=tc["id"],
                            content=tool_result_str
                        ))

                # ── Second invocation — generate final response ───────────────────
                ai_msg2 = await self.model.ainvoke(prompt_messages)
                content = ai_msg2.content or ""

                if not content.strip():
                    content = (
                        "I'm sorry, something went wrong generating a response. "
                        "Please try again or rephrase your request."
                    )

                # After successful booking, reset the thread
                try:
                    last_tool_result = json.loads(prompt_messages[-1].content)
                    if last_tool_result.get("success"):
                        _clear_sb_thread(session_id)
                    else:
                        sb_thread.append(AIMessage(content=content))
                        _save_sb_thread(session_id, sb_thread)
                except Exception:
                    sb_thread.append(AIMessage(content=content))
                    _save_sb_thread(session_id, sb_thread)

                # Return table response if multiple spots found
                if tool_data and "p_list" in tool_data and len(tool_data["p_list"]) > 1:
                    final_response = {
                        "type": "large_dataset",
                        "context_summary": content,
                        "records": tool_data["p_list"]
                    }
                    return json.dumps(final_response), content, messages
                else:
                    return content, content, messages

            # ── No tool called — pure conversational response ──────────────────────
            content = ai_msg.content or ""
            if not content.strip():
                content = (
                    "I'm here to help you book a space! "
                    "Could you tell me which building or Spot Code you're looking for?"
                )

            sb_thread.append(AIMessage(content=content))
            _save_sb_thread(session_id, sb_thread)
            return content, content, messages

        except Exception as e:
            logger.error(f"❌ Error in handle_space_booking: {e}", exc_info=True)
            err_msg = "Sorry, something went wrong while processing your space booking request."
            return err_msg, err_msg, messages


space_booking_service = SpaceBookingService()
