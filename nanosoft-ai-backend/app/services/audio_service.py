"""
Audio Service — Transcription + Confirmation in One Model Call
───────────────────────────────────────────────────────────────
Zero-shot approach — rules only, no examples.
Simple 3-outcome classification:
  1. General knowledge → proceed directly
  2. Data query        → always confirm with user first
  3. Not FM query      → ask user to repeat
"""
import logging
import tempfile
import os
import json
import asyncio
import math
import subprocess
from google import genai
from app.config import settings

logger = logging.getLogger("audio_service")
logger.setLevel(logging.INFO)

# ── Initialize Gemini Client ─────────────────────────────────────────────────
client = genai.Client(api_key=settings.GOOGLE_API_KEY)

# ── FM Domain Reference ──────────────────────────────────────────────────────
FM_DOMAIN_REFERENCE = """
This assistant handles 3 domains: ASSETS, PPM, BDM.
Filter fields: division, discipline, locality, building, floor, spot_name,
status, condition, priority, asset_type, make, model, trade_group,
service_area, owner, serial_no, asset_tag_no, frequency, stage,
contract, tech, equipment, work_order, complaint_type, complaint_mode,
complaint_nature, wo_type, service_type, complainer, analysis_tech,
execution_tech, complaint_no.
"""

# ── System Instructions — Pure Zero-Shot, Rules Only ─────────────────────────
SYSTEM_INSTRUCTIONS = f"""
You are an expert Facility Management audio transcription system.

DOMAIN KNOWLEDGE:
{FM_DOMAIN_REFERENCE}

YOUR JOB — complete all steps in one pass:

STEP 1 — TRANSCRIBE:
- Remove filler words and stutters.
- Keep only the final corrected thought if user restarts.
- Ignore background noise.
- If a filter field value is physically unclear due to noise or mumbling
  → replace that word with [Unsure] and add to uncertain_terms.
- Never mark [Unsure] just because a value seems unusual.

STEP 2 — CLASSIFY into exactly one of 3 outcomes:

OUTCOME 1 — GENERAL KNOWLEDGE OR GREETING:
The user is asking a conceptual or definitional FM question,
OR greeting, introducing themselves, or making small talk.
This includes greetings like "Hi", "Hello", "Good morning",
introductions like "My name is X", and casual phrases like
"Thank you", "Bye", "How are you".
Names in introductions are NOT filter values and require NO confirmation.
Any sentence that starts with "My name is" or "I am" is always OUTCOME 1.
No data will be fetched. No filter fields involved.
→ needs_clarification = false
→ clarification_question = ""

OUTCOME 2 — DATA QUERY:
The user wants to fetch real data from the system.
This includes any query that wants to list, show, count, or filter
assets, complaints, or PPM tasks — with or without filter values.
→ needs_clarification = true
→ clarification_question must be a single friendly sentence that
  repeats back what you understood, ending with "Is that correct?"
  If any word was [Unsure], mention it was unclear in the question.

OUTCOME 3 — NOT FM QUERY:
The audio does not relate to facility management at all.
Includes casual conversation, accidental recordings, vague statements.
→ needs_clarification = true
→ clarification_question = "I didn't quite catch that. Could you please repeat your question?"

STEP 3 — OUTPUT:
Return ONLY this exact JSON. No extra text, no markdown.
{{
    "transcription": "clean transcribed text, or empty string for OUTCOME 3",
    "uncertain_terms": ["word1"],
    "needs_clarification": true or false,
    "clarification_question": "confirmation sentence or question, empty string for OUTCOME 1"
}}
"""


async def convert_audio_to_text(audio_bytes: bytes) -> dict:
    """
    Transcribes audio AND classifies the query in ONE model call.

    Returns:
    {
        "transcription":          str  — clean text (empty if OUTCOME 3)
        "uncertain_terms":        list — physically unclear words
        "needs_clarification":    bool — True for data queries and non-FM queries
        "clarification_question": str  — confirmation or repeat request
    }

    main.py flow:
        if needs_clarification=True (data query):
            send clarification_question to user → wait for reply
            if yes  → run with original transcription
            if no   → use their corrected reply as new query
        if needs_clarification=False (general knowledge):
            run process_query directly
    """
    tmp_path      = None
    uploaded_file = None

    try:
        # ── 1. Write bytes to temp file ──────────────────────────────────────
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        logger.info(f"🎵 Audio file ready: {tmp_path}")

        # ── 2. Upload to Gemini Files API ────────────────────────────────────
        uploaded_file = client.files.upload(
            file=tmp_path,
            config={"mime_type": "audio/ogg"}
        )
        logger.info(f"✅ Uploaded: {uploaded_file.name}")

        # ── 3. Call Gemini ───────────────────────────────────────────────────
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.models.generate_content,
                    model=settings.GOOGLE_AI_MODEL,
                    contents=["Transcribe and classify this audio.", uploaded_file],
                    config={
                        "system_instruction": SYSTEM_INSTRUCTIONS,
                        "response_mime_type": "application/json"
                    }
                ),
                timeout=15.0
            )
        except asyncio.TimeoutError:
            raise Exception("Audio transcription timed out")

        # ── 4. Parse result ──────────────────────────────────────────────────
        result = json.loads(response.text)
        logger.info(f"📝 Transcription result: {result}")

        # ── 5. Safety checks ─────────────────────────────────────────────────
        transcription          = result.get("transcription", "").strip()
        uncertain_terms        = result.get("uncertain_terms", [])
        needs_clarification    = bool(result.get("needs_clarification", False))
        clarification_question = result.get("clarification_question", "").strip()

        # needs_clarification=True but no question → use default
        if needs_clarification and not clarification_question:
            clarification_question = "I didn't quite catch that. Could you please repeat your question?"

        # Empty transcription but needs_clarification=False → fix it
        if not transcription and not needs_clarification:
            needs_clarification    = True
            clarification_question = "I didn't quite catch that. Could you please repeat your question?"

        if needs_clarification:
            logger.info(f"🔍 Confirmation/Clarification: '{clarification_question}'")
        else:
            logger.info(f"✅ General knowledge — PROCEED directly")

        return {
            "transcription":          transcription,
            "uncertain_terms":        uncertain_terms,
            "needs_clarification":    needs_clarification,
            "clarification_question": clarification_question
        }

    except Exception as e:
        logger.error(f"❌ Transcription error: {e}")
        # Safe fallback — never crash the WebSocket
        return {
            "transcription":          "",
            "uncertain_terms":        [],
            "needs_clarification":    True,
            "clarification_question": "I'm sorry, I couldn't process that audio. Could you please repeat your request?"
        }

    finally:
        # ── Cleanup temp file ────────────────────────────────────────────────
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

        # ── Cleanup Gemini cloud file ────────────────────────────────────────
        if uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception as cleanup_err:
                logger.warning(f"⚠️ Cloud cleanup failed: {cleanup_err}")


# Changes done by sanjeevan


def get_audio_duration_seconds(audio_bytes: bytes) -> int | None:
    """
    Compute audio duration (seconds) by running `ffprobe` on the received bytes.
    Returns an integer number of seconds, or None if duration can't be determined.
    """
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            tmp_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            logger.warning("⚠️ ffprobe failed: %s", (proc.stderr or "").strip()[:200])
            return None

        dur_str = (proc.stdout or "").strip()
        if not dur_str:
            return None

        dur = float(dur_str)
        if not math.isfinite(dur) or dur <= 0:
            return None

        # Use ceil so we don't under-consume audio credits.
        return int(math.ceil(dur))
    except Exception as e:
        logger.warning("⚠️ Failed to compute audio duration: %s", str(e)[:200])
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass