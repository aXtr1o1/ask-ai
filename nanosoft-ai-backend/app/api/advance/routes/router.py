import logging
import asyncio

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from app.api.advance.schemas import AdvanceAskRequest
from app.api.advance.service.service import stream_advance_pipeline
from app.services.chat_websocket_handler import MAX_AUDIO_BYTES
from app.services.audio_service import get_audio_duration_seconds, convert_audio_to_text
from app.services.user_profile_service import consume_audio_seconds_if_available, update_daily_history

logger = logging.getLogger("advance.router")

advance_router = APIRouter()


@advance_router.post(
    "/advance/ask-ai",
    summary     = "Advance Ask-AI Pipeline (SSE)",
    description = (
        "Streams the pipeline as Server-Sent Events (SSE).\n\n"
        "Stages: **Understanding Agent** always runs. "
        "**Analysis Agent** runs only when intent is `db_query`."
    ),
    tags=["advance"],
)
async def advance_ask_ai(request: AdvanceAskRequest) -> StreamingResponse:
    query      = request.query.strip()
    session_id = request.session_id.strip()

    logger.info("[advance/ask-ai] ▶ SSE REQUEST | session=%s | query=%s", session_id, query)

    return StreamingResponse(
        stream_advance_pipeline(query, session_id, request.user_name, request.user_id),
        media_type = "text/event-stream",
        headers    = {
            "Cache-Control":   "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering if behind a proxy
        },
    )


@advance_router.post(
    "/advance/ask-ai/audio",
    summary     = "Advance Ask-AI Pipeline for Audio (SSE)",
    description = (
        "Streams the pipeline as Server-Sent Events (SSE).\n\n"
        "First transcribes audio and then runs the advance pipeline."
    ),
    tags=["advance"],
)
async def advance_ask_ai_audio(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    user_name: str = Form(default=""),
    user_id: str = Form(default=""),
    audio_seconds: float | None = Form(default=None),
) -> StreamingResponse:
    session_id = session_id.strip()
    user_name  = user_name.strip()
    user_id    = user_id.strip()

    logger.info("[advance/ask-ai/audio] ▶ SSE REQUEST | session=%s | filename=%s", session_id, file.filename)

    try:
        # Read the uploaded file bytes
        audio_bytes = await file.read()

        # Enforce audio size check
        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=400, detail="Voice query is too long. Please keep it brief and try again.")

        # Determine sub_user_name for credit validation
        sub_user_name = user_id if (user_id and user_id.strip()) else user_name

        # Audio credit enforcement
        computed_audio_seconds = get_audio_duration_seconds(audio_bytes)
        audio_seconds_effective = (
            computed_audio_seconds
            if computed_audio_seconds is not None and computed_audio_seconds > 0
            else (int(audio_seconds) if audio_seconds else 0)
        )

        logger.info(
            "📊 advance audio_seconds_effective=%s (client=%s, computed=%s)",
            audio_seconds_effective,
            audio_seconds,
            computed_audio_seconds,
        )

        if audio_seconds_effective and audio_seconds_effective > 0:
            consumed = await asyncio.to_thread(
                consume_audio_seconds_if_available,
                name=sub_user_name,
                audio_seconds_delta=audio_seconds_effective,
            )
            if consumed is False:
                raise HTTPException(status_code=402, detail="Audio credits exhausted. Please recharge/upgrade your plan to continue.")

            # Update daily history usage
            try:
                await asyncio.to_thread(
                    update_daily_history,
                    external_user_id=user_name,
                    name=sub_user_name,
                    credits_delta=0,
                    audio_seconds_delta=int(audio_seconds_effective),
                    graph_delta=0,
                    request_delta=0,
                )
                logger.info("✅ usage_history audio saved for advance mode | audio=%s", audio_seconds_effective)
            except Exception as e:
                logger.warning("⚠️ update_daily_history audio failed for advance mode: %s", str(e)[:200])

        # Transcribe audio using convert_audio_to_text
        transcription_result = await convert_audio_to_text(audio_bytes)
        query = transcription_result.get("transcription", "").strip()

        if not query:
            raise HTTPException(status_code=400, detail="Could not understand audio. Please repeat clearly or type your message.")

        logger.info("[advance/ask-ai/audio] Transcribed text: %s", query)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[advance/ask-ai/audio] Error during audio processing: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))

    # Start the SSE streaming advance pipeline
    return StreamingResponse(
        stream_advance_pipeline(query, session_id, user_name, user_id),
        media_type = "text/event-stream",
        headers    = {
            "Cache-Control":   "no-cache",
            "X-Accel-Buffering": "no",
        },
    )