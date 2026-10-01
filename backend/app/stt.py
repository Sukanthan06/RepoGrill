"""Validate uploaded answer audio and transcribe it with the configured Whisper model."""

from app.config import Settings
from app.errors import BadRequestError
from app.llm_client import LLMClient

ALLOWED_TYPES = {
    "audio/webm", "audio/ogg", "audio/mpeg", "audio/mp4", "audio/wav", "audio/x-wav",
    "audio/m4a", "audio/x-m4a", "video/webm",
}  # fmt: skip
EXTENSIONS = {"audio/webm": "webm", "video/webm": "webm", "audio/ogg": "ogg", "audio/mpeg": "mp3",
              "audio/mp4": "m4a", "audio/m4a": "m4a", "audio/x-m4a": "m4a", "audio/wav": "wav",
              "audio/x-wav": "wav"}  # fmt: skip


def base_content_type(content_type: str | None) -> str:
    """Strip codec parameters: 'audio/webm;codecs=opus' -> 'audio/webm'."""
    return (content_type or "").split(";", 1)[0].strip().lower()


def validate_audio(
    data: bytes, content_type: str | None, duration_seconds: float | None, settings: Settings
) -> str:
    """Return the normalized content type or raise a BadRequestError."""
    kind = base_content_type(content_type)
    if kind not in ALLOWED_TYPES:
        raise BadRequestError(f"Unsupported audio type '{kind or 'unknown'}'")
    if not data:
        raise BadRequestError("Audio upload is empty")
    if len(data) > settings.max_audio_bytes:
        raise BadRequestError("Audio is too large; keep answers under two minutes")
    if duration_seconds is not None and duration_seconds > settings.max_audio_seconds + 2:
        raise BadRequestError("Audio is longer than the two-minute limit")
    return kind


async def transcribe_audio(
    llm: LLMClient,
    settings: Settings,
    data: bytes,
    content_type: str | None,
    duration_seconds: float | None = None,
) -> str:
    kind = validate_audio(data, content_type, duration_seconds, settings)
    return await llm.transcribe(data, f"answer.{EXTENSIONS[kind]}", kind)
