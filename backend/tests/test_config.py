import pytest

from app.config import Settings


def test_cors_allows_localhost_in_development() -> None:
    settings = Settings(_env_file=None, frontend_origin="https://app.example.com/")
    assert settings.cors_origins[0] == "https://app.example.com"
    assert "http://localhost:3000" in settings.cors_origins


def test_cors_production_is_restricted_to_frontend_origin() -> None:
    settings = Settings(
        _env_file=None, app_env="production", frontend_origin="https://a.com, https://b.com"
    )
    assert settings.cors_origins == ["https://a.com", "https://b.com"]


def test_groq_key_alias_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "abc")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert Settings(_env_file=None).llm_api_key == "abc"
