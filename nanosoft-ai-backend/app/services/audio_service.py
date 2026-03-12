"""
Audio Service — High-Fidelity Transcription for Noisy Mono Audio.
"""
import logging
import tempfile
import os
# Using the modern SDK
from google import genai
from app.config import settings
import asyncio 

logger = logging.getLogger("audio_service")
logger.setLevel(logging.INFO)

# ── Initialize Client ────────────────────────────────────────────────────────
# The new SDK uses a Client object for better session management
client = genai.Client(api_key=settings.GOOGLE_API_KEY)

async def convert_audio_to_text(audio_bytes: bytes) -> str:
    """
    Transcribes mono OGG audio with strict anti-hallucination rules for noise.
    """
    tmp_path = None
    uploaded_file = None

    try:
        # 1. Write bytes to a temp file
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        logger.info(f"🎵 Audio file ready: {tmp_path}")

        # 2. Upload to Gemini Files API
        # We specify audio/ogg to ensure the model handles the Opus codec correctly
        # ✅ NEW — correct syntax
        uploaded_file = client.files.upload(file=tmp_path, config={'mime_type': 'audio/ogg'})
        logger.info(f"✅ Uploaded: {uploaded_file.name}")

        # 3. Use a Strict "Ground Truth" Prompt
        # This is designed specifically for your mono/noise/single-speaker needs
        prompt = """
            TASK: Professional clean-text transcription.
            INPUT: Single-speaker mono audio with background noise and verbal fillers.

            STRICT INSTRUCTIONS:
            1. CLEAN OUTPUT: Remove filler words (um, ah, uh, like, you know) and stutters. 
            2. LOGICAL INTENT: If the user restarts a sentence (e.g., "I want to... I mean, I need to go"), only transcribe the final, corrected thought ("I need to go").
            3. NO HALLUCINATION: If noise makes a phrase unintelligible and you cannot be 100% sure of the words, do NOT guess. Instead, write [Unsure].
            4. FORMATTING: Return only the clean, final text. Do not include speaker labels or timestamps.
            5. NOISE FILTER: Completely ignore background clicks, wind, or static.

            GOAL: Provide the final 'intended' message of the speaker. If the audio is too noisy to be sure, use the [Unsure] tag.
            """

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.models.generate_content,
                    model=settings.GOOGLE_AI_MODEL,
                    contents=[prompt, uploaded_file]
                ),
                timeout=10.0  # fail fast in this seconds
            )
        except asyncio.TimeoutError:
            raise Exception("Audio transcription timed out")

        transcribed_text = response.text.strip()

        if not transcribed_text:
            raise ValueError("Gemini returned no text (check if audio is pure noise).")

        return transcribed_text

    except Exception as e:
        logger.error(f"❌ Transcription failed: {e}")
        raise

    finally:
        # 5. Clean up local temp file
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
            
        # 6. Clean up Gemini Cloud file (Good practice for privacy/quota)
        if uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception as cleanup_err:
                logger.warning(f"⚠️ Cloud cleanup failed: {cleanup_err}")