"""Single entry point for all LLM and speech-to-text calls (OpenAI-compatible API)."""

import json
import logging
import re
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.errors import ConfigError, LLMOutputError, RateLimitedError, UpstreamError
from app.retry import retry_after_seconds, send_with_retry

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
Message = dict[str, str]

REPAIR_INSTRUCTION = (
    "Your previous reply was not valid JSON for the required schema. "
    "Error: {error}\n"
    "Reply again with ONLY a single JSON object that matches the schema. "
    "No prose, no markdown fences."
)
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def extract_json(text: str) -> Any:
    """Parse a JSON object from model output, tolerating fences and stray prose."""
    cleaned = _FENCE_RE.sub("", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


def parse_model(text: str, schema: type[T]) -> T:
    """Parse and validate model output; raises ValueError with a readable reason."""
    try:
        data = extract_json(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"schema mismatch: {exc.errors(include_url=False)[:5]}") from exc


class LLMClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._http = http or httpx.AsyncClient(timeout=settings.llm_timeout_seconds)

    async def aclose(self) -> None:
        await self._http.aclose()

    def _headers(self) -> dict[str, str]:
        if not self.settings.llm_api_key:
            raise ConfigError("LLM_API_KEY is not set")
        return {"Authorization": f"Bearer {self.settings.llm_api_key}"}

    def _url(self, path: str) -> str:
        return f"{self.settings.llm_base_url.rstrip('/')}/{path.lstrip('/')}"

    @staticmethod
    def _require_model(model: str, env_name: str) -> str:
        if not model:
            raise ConfigError(f"{env_name} is not set; run scripts/discover_models.py")
        return model

    async def _post(self, path: str, label: str, **kwargs: Any) -> httpx.Response:
        headers = self._headers()

        async def send() -> httpx.Response:
            return await self._http.post(self._url(path), headers=headers, **kwargs)

        try:
            response = await send_with_retry(
                send, max_attempts=self.settings.llm_max_attempts, label=label
            )
        except httpx.HTTPError as exc:
            raise UpstreamError(f"LLM provider unreachable: {type(exc).__name__}") from exc
        if response.status_code == 429:
            raise RateLimitedError(
                "LLM provider rate limit reached", retry_after=retry_after_seconds(response)
            )
        return response

    async def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.4,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> str:
        """Return the assistant text for a chat completion."""
        payload: dict[str, Any] = {
            "model": self._require_model(model or self.settings.llm_model, "LLM_MODEL"),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        response = await self._post("chat/completions", "chat", json=payload)
        if response.status_code == 400 and json_mode:
            # Some providers reject output that fails their own JSON check;
            # fall back to plain mode and let our parser/repair loop handle it.
            logger.info("JSON mode rejected by provider, retrying without response_format")
            payload.pop("response_format")
            response = await self._post("chat/completions", "chat", json=payload)
        if response.status_code >= 400:
            raise UpstreamError(f"LLM provider returned HTTP {response.status_code}")
        try:
            return response.json()["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, ValueError) as exc:
            raise UpstreamError("Unexpected LLM response shape") from exc

    async def chat_json(
        self,
        messages: list[Message],
        schema: type[T],
        *,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> T:
        """Chat and validate the reply against `schema`, repairing once on failure."""
        text = await self.chat(
            messages, model=model, temperature=temperature, max_tokens=max_tokens, json_mode=True
        )
        try:
            return parse_model(text, schema)
        except ValueError as first_error:
            logger.warning("LLM JSON invalid for %s, attempting repair", schema.__name__)
            repair = messages + [
                {"role": "assistant", "content": text[:4000]},
                {"role": "user", "content": REPAIR_INSTRUCTION.format(error=first_error)},
            ]
            text = await self.chat(
                repair, model=model, temperature=0.0, max_tokens=max_tokens, json_mode=True
            )
            try:
                return parse_model(text, schema)
            except ValueError as second_error:
                raise LLMOutputError(
                    f"Model returned invalid {schema.__name__} twice: {second_error}"
                ) from second_error

    async def transcribe(self, audio: bytes, filename: str, content_type: str) -> str:
        """Transcribe audio with the configured Whisper model."""
        model = self._require_model(self.settings.stt_model, "STT_MODEL")
        response = await self._post(
            "audio/transcriptions",
            "transcribe",
            data={"model": model, "response_format": "json", "language": "en"},
            files={"file": (filename, audio, content_type)},
        )
        if response.status_code >= 400:
            raise UpstreamError(f"Transcription failed with HTTP {response.status_code}")
        try:
            return str(response.json().get("text", "")).strip()
        except ValueError as exc:
            raise UpstreamError("Unexpected transcription response") from exc
