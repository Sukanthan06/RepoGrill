from typing import Annotated

from fastapi import APIRouter, Depends, Form, UploadFile

from app.errors import BadRequestError
from app.models import TranscriptionResponse
from app.services import Services, get_services
from app.stt import transcribe_audio

router = APIRouter(prefix="/api", tags=["speech"])


@router.post("/transcribe")
async def transcribe(
    audio: UploadFile,
    services: Annotated[Services, Depends(get_services)],
    duration_seconds: Annotated[float | None, Form()] = None,
) -> TranscriptionResponse:
    limit = services.settings.max_audio_bytes
    data = await audio.read(limit + 1)
    if len(data) > limit:
        raise BadRequestError("Audio is too large; keep answers under two minutes")
    text = await transcribe_audio(
        services.llm, services.settings, data, audio.content_type, duration_seconds
    )
    return TranscriptionResponse(text=text)
