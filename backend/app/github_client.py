"""Thin async wrapper over the GitHub REST API and raw content host."""

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings
from app.errors import NotFoundError, RateLimitedError, UpstreamError
from app.repo_url import RepoRef
from app.retry import send_with_retry

logger = logging.getLogger(__name__)

RAW_HOST = "https://raw.githubusercontent.com"


@dataclass(frozen=True)
class RepoInfo:
    full_name: str
    description: str
    default_branch: str
    stars: int
    language: str | None
    html_url: str


@dataclass(frozen=True)
class TreeEntry:
    path: str
    size: int


def rate_limit_error(response: httpx.Response) -> RateLimitedError | None:
    """Return a RateLimitedError if GitHub says the quota is exhausted."""
    remaining = response.headers.get("x-ratelimit-remaining")
    if response.status_code not in (403, 429):
        return None
    if response.status_code == 403 and remaining != "0":
        return None
    reset = response.headers.get("x-ratelimit-reset")
    if reset and reset.isdigit():
        reset_at = datetime.fromtimestamp(int(reset), tz=UTC)
        wait = max(0.0, int(reset) - time.time())
        return RateLimitedError(
            f"GitHub API rate limit reached. It resets at {reset_at:%H:%M} UTC "
            f"(in about {int(wait // 60) + 1} min). Adding a GITHUB_TOKEN raises the limit.",
            retry_after=wait,
        )
    return RateLimitedError("GitHub API rate limit reached; try again shortly", retry_after=60)


class GitHubClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "RepoGrill",
        }
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"
        self._http = http or httpx.AsyncClient(timeout=20, headers=headers, follow_redirects=True)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get(self, url: str, label: str) -> httpx.Response:
        async def send() -> httpx.Response:
            return await self._http.get(url)

        try:
            response = await send_with_retry(send, max_attempts=3, label=label)
        except httpx.HTTPError as exc:
            raise UpstreamError(f"Could not reach GitHub ({type(exc).__name__})") from exc
        limited = rate_limit_error(response)
        if limited:
            raise limited
        return response

    async def _get_json(self, path: str, label: str) -> Any:
        url = f"{self.settings.github_api_url.rstrip('/')}{path}"
        response = await self._get(url, label)
        if response.status_code == 404:
            raise NotFoundError(
                "Repository not found. It may be private, renamed, or the URL has a typo."
            )
        if response.status_code >= 400:
            raise UpstreamError(f"GitHub returned HTTP {response.status_code} for {label}")
        return response.json()

    async def get_repo(self, ref: RepoRef) -> RepoInfo:
        data = await self._get_json(f"/repos/{ref.owner}/{ref.name}", "repo metadata")
        if data.get("private"):
            raise NotFoundError("This repository is private; RepoGrill only reads public repos.")
        return RepoInfo(
            full_name=data["full_name"],
            description=data.get("description") or "",
            default_branch=data["default_branch"],
            stars=int(data.get("stargazers_count", 0)),
            language=data.get("language"),
            html_url=data["html_url"],
        )

    async def get_branch_sha(self, ref: RepoRef, branch: str) -> str:
        data = await self._get_json(
            f"/repos/{ref.owner}/{ref.name}/branches/{quote(branch, safe='')}", "branch"
        )
        return str(data["commit"]["sha"])

    async def get_tree(self, ref: RepoRef, sha: str) -> tuple[list[TreeEntry], bool]:
        """Return all blobs in the tree and whether GitHub truncated the listing."""
        data = await self._get_json(
            f"/repos/{ref.owner}/{ref.name}/git/trees/{sha}?recursive=1", "tree"
        )
        entries = [
            TreeEntry(path=item["path"], size=int(item.get("size", 0)))
            for item in data.get("tree", [])
            if item.get("type") == "blob"
        ]
        return entries, bool(data.get("truncated"))

    async def get_file_text(self, ref: RepoRef, sha: str, path: str) -> str | None:
        """Fetch a file from the raw host (does not count against the API quota)."""
        url = f"{RAW_HOST}/{ref.owner}/{ref.name}/{sha}/{quote(path)}"
        try:
            response = await self._get(url, "raw file")
        except (UpstreamError, RateLimitedError) as exc:
            logger.warning("Skipping %s: %s", path, exc.message)
            return None
        if response.status_code != 200:
            return None
        try:
            return response.content.decode("utf-8")
        except UnicodeDecodeError:
            return None
