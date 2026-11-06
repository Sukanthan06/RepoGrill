import httpx
import pytest
import respx
from pydantic import BaseModel

from app.config import Settings
from app.errors import LLMOutputError, RateLimitedError
from app.llm_client import LLMClient, extract_json, parse_model

BASE = "https://llm.test/v1"


class Verdict(BaseModel):
    action: str
    score: int


def make_settings() -> Settings:
    return Settings(
        _env_file=(),
        llm_base_url=BASE,
        llm_api_key="test-key",
        llm_model="strong-model",
        llm_fast_model="fast-model",
        llm_max_attempts=4,
    )


def completion(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def instant(_: float) -> None:
        return None

    monkeypatch.setattr("app.retry.asyncio.sleep", instant)


def test_extract_json_strips_fences_and_prose() -> None:
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! {"a": 2} hope this helps') == {"a": 2}


def test_parse_model_reports_schema_errors() -> None:
    with pytest.raises(ValueError, match="schema mismatch"):
        parse_model('{"action": "x"}', Verdict)


@respx.mock
async def test_chat_json_valid_first_try() -> None:
    route = respx.post(f"{BASE}/chat/completions").mock(
        return_value=completion('{"action": "next", "score": 3}')
    )
    client = LLMClient(make_settings())
    result = await client.chat_json([{"role": "user", "content": "hi"}], Verdict)
    assert result == Verdict(action="next", score=3)
    assert route.call_count == 1
    await client.aclose()


@respx.mock
async def test_chat_json_repairs_once() -> None:
    route = respx.post(f"{BASE}/chat/completions").mock(
        side_effect=[completion("not json at all"), completion('{"action": "end", "score": 5}')]
    )
    client = LLMClient(make_settings())
    result = await client.chat_json([{"role": "user", "content": "hi"}], Verdict)
    assert result.action == "end"
    assert route.call_count == 2
    await client.aclose()


@respx.mock
async def test_chat_json_fails_gracefully_after_repair() -> None:
    respx.post(f"{BASE}/chat/completions").mock(return_value=completion('{"oops": true}'))
    client = LLMClient(make_settings())
    with pytest.raises(LLMOutputError):
        await client.chat_json([{"role": "user", "content": "hi"}], Verdict)
    await client.aclose()


@respx.mock
async def test_retries_429_then_succeeds() -> None:
    route = respx.post(f"{BASE}/chat/completions").mock(
        side_effect=[httpx.Response(429), httpx.Response(503), completion("hello")]
    )
    client = LLMClient(make_settings())
    assert await client.chat([{"role": "user", "content": "hi"}]) == "hello"
    assert route.call_count == 3
    await client.aclose()


@respx.mock
async def test_persistent_429_raises_rate_limited() -> None:
    route = respx.post(f"{BASE}/chat/completions").mock(
        return_value=httpx.Response(429, headers={"retry-after": "7"})
    )
    client = LLMClient(make_settings())
    with pytest.raises(RateLimitedError) as info:
        await client.chat([{"role": "user", "content": "hi"}])
    assert route.call_count == 4
    assert info.value.retry_after == 7.0
    await client.aclose()


@respx.mock
async def test_reasoning_effort_sent_only_when_configured() -> None:
    route = respx.post(f"{BASE}/chat/completions").mock(return_value=completion("ok"))
    settings = make_settings()
    client = LLMClient(settings)
    await client.chat([{"role": "user", "content": "hi"}])
    assert b"reasoning_effort" not in route.calls[-1].request.content
    settings.llm_reasoning_effort = "low"
    await client.chat([{"role": "user", "content": "hi"}])
    assert b'"reasoning_effort":"low"' in route.calls[-1].request.content
    await client.aclose()
