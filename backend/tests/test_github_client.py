import time

import httpx
import pytest
import respx

from app.config import Settings
from app.errors import NotFoundError, RateLimitedError
from app.github_client import GitHubClient, rate_limit_error
from app.repo_url import RepoRef

API = "https://api.github.com"
REF = RepoRef("octo", "demo")


def make_client() -> GitHubClient:
    return GitHubClient(Settings(_env_file=None))


def test_rate_limit_error_reports_reset_time() -> None:
    reset = int(time.time()) + 600
    response = httpx.Response(
        403, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(reset)}
    )
    error = rate_limit_error(response)
    assert error is not None
    assert "resets at" in error.message
    assert error.retry_after is not None and 590 < error.retry_after <= 600


def test_plain_403_is_not_rate_limit() -> None:
    assert rate_limit_error(httpx.Response(403, headers={"x-ratelimit-remaining": "42"})) is None


@respx.mock
async def test_missing_repo_raises_not_found() -> None:
    respx.get(f"{API}/repos/octo/demo").mock(return_value=httpx.Response(404))
    client = make_client()
    with pytest.raises(NotFoundError):
        await client.get_repo(REF)
    await client.aclose()


@respx.mock
async def test_exhausted_quota_raises_rate_limited() -> None:
    reset = str(int(time.time()) + 60)
    respx.get(f"{API}/repos/octo/demo").mock(
        return_value=httpx.Response(
            403, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": reset}
        )
    )
    client = make_client()
    with pytest.raises(RateLimitedError):
        await client.get_repo(REF)
    await client.aclose()


@respx.mock
async def test_tree_returns_only_blobs() -> None:
    respx.get(f"{API}/repos/octo/demo/git/trees/abc?recursive=1").mock(
        return_value=httpx.Response(
            200,
            json={
                "truncated": False,
                "tree": [
                    {"path": "src", "type": "tree"},
                    {"path": "src/main.py", "type": "blob", "size": 120},
                ],
            },
        )
    )
    client = make_client()
    entries, truncated = await client.get_tree(REF, "abc")
    assert [e.path for e in entries] == ["src/main.py"]
    assert truncated is False
    await client.aclose()
