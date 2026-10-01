"""Parse GitHub repository references from the many shapes users paste."""

import re
from dataclasses import dataclass

from app.errors import BadRequestError

_NAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,99})$")
_SSH_RE = re.compile(r"^(?:ssh://)?git@github\.com[:/](?P<path>.+)$", re.IGNORECASE)
_HTTP_RE = re.compile(
    r"^(?:(?:https?|git)://)?(?:www\.)?github\.com/(?P<path>.+)$", re.IGNORECASE
)


@dataclass(frozen=True)
class RepoRef:
    owner: str
    name: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


def _split_path(path: str) -> tuple[str, str] | None:
    path = path.split("?", 1)[0].split("#", 1)[0].strip("/")
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        return None
    owner, name = parts[0], parts[1]
    if name.lower().endswith(".git"):
        name = name[:-4]
    return owner, name


def parse_repo_url(raw: str) -> RepoRef:
    """Return the owner/name for a GitHub URL, SSH remote or bare `owner/repo`.

    Accepts trailing slashes, `.git` suffixes and deep links such as
    `/tree/<branch>/...` or `/blob/...`, which are ignored.
    """
    text = (raw or "").strip()
    match = _SSH_RE.match(text) or _HTTP_RE.match(text)
    if match:
        path = match.group("path")
    elif "://" not in text and "github.com" not in text.lower() and text.count("/") >= 1:
        path = text
    else:
        raise BadRequestError("That doesn't look like a GitHub repository URL")

    parsed = _split_path(path)
    if not parsed or not all(_NAME_RE.match(p) for p in parsed):
        raise BadRequestError("Expected a URL like https://github.com/owner/repo")
    owner, name = parsed
    if name in {".", ".."}:
        raise BadRequestError("Expected a URL like https://github.com/owner/repo")
    return RepoRef(owner=owner, name=name)
