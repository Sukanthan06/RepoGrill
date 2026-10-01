"""Application settings loaded from environment variables and .env files."""

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
# Later files win: a backend/.env overrides a repo-root .env.
ENV_FILES = (BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = Field(default="", validation_alias=AliasChoices("LLM_API_KEY", "GROQ_API_KEY"))
    llm_model: str = ""
    llm_fast_model: str = ""
    stt_model: str = ""
    llm_timeout_seconds: float = 60.0
    llm_max_attempts: int = 4

    github_token: str = ""
    github_api_url: str = "https://api.github.com"

    frontend_origin: str = ""
    session_ttl_seconds: int = 2 * 60 * 60
    log_level: str = "INFO"

    max_audio_bytes: int = 10 * 1024 * 1024
    max_audio_seconds: int = 120

    @property
    def cors_origins(self) -> list[str]:
        origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
        origins += [o.strip().rstrip("/") for o in self.frontend_origin.split(",") if o.strip()]
        return origins

    @property
    def fast_model(self) -> str:
        """The cheap model, falling back to the strong one when unset."""
        return self.llm_fast_model or self.llm_model


@lru_cache
def get_settings() -> Settings:
    return Settings()
