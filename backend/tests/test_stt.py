import pytest

from app.config import Settings
from app.errors import BadRequestError
from app.stt import base_content_type, validate_audio

SETTINGS = Settings(_env_file=None, max_audio_bytes=1000, max_audio_seconds=120)


def test_strips_codec_parameters() -> None:
    assert base_content_type("audio/webm;codecs=opus") == "audio/webm"


def test_accepts_webm_opus() -> None:
    assert validate_audio(b"x" * 10, "audio/webm;codecs=opus", 30, SETTINGS) == "audio/webm"


@pytest.mark.parametrize(
    "data,content_type,duration",
    [
        (b"x", "image/png", None),
        (b"", "audio/webm", None),
        (b"x" * 1001, "audio/webm", None),
        (b"x", "audio/webm", 200),
    ],
)
def test_rejects_bad_uploads(data: bytes, content_type: str, duration: float | None) -> None:
    with pytest.raises(BadRequestError):
        validate_audio(data, content_type, duration, SETTINGS)
