"""Turn a GitHub URL into ranked, truncated context files plus an evidence index."""

import asyncio
import hashlib
import logging

from app.file_ranking import is_manifest, rank_files, should_skip
from app.github_client import GitHubClient
from app.manifests import extract_dependencies
from app.models import EvidenceIndex, FileSnippet, IngestedRepo, RepoMeta
from app.repo_url import RepoRef, parse_repo_url
from app.store import TTLStore

logger = logging.getLogger(__name__)

CONTEXT_FILE_COUNT = 15
EVIDENCE_FILE_COUNT = 40
MAX_MANIFESTS = 10
TOKENS_PER_FILE = 1500
CHARS_PER_TOKEN = 4  # rough heuristic, good enough for budgeting
MAX_EVIDENCE_CHARS = 100_000
FETCH_CONCURRENCY = 8


def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN + 1


def truncate_to_tokens(text: str, max_tokens: int) -> tuple[str, bool]:
    """Cut text to roughly `max_tokens`, preferring a line boundary."""
    limit = max_tokens * CHARS_PER_TOKEN
    if len(text) <= limit:
        return text, False
    cut = text.rfind("\n", 0, limit)
    if cut < limit // 2:
        cut = limit
    return text[:cut].rstrip() + "\n… [truncated]", True


def make_repo_id(full_name: str, sha: str) -> str:
    return hashlib.sha256(f"{full_name.lower()}@{sha}".encode()).hexdigest()[:16]


def select_files(ranked: list[str], all_paths: list[str]) -> tuple[list[str], list[str]]:
    """Return (context paths for the LLM, superset of paths to fetch for evidence)."""
    context = ranked[:CONTEXT_FILE_COUNT]
    evidence = list(ranked[:EVIDENCE_FILE_COUNT])
    manifests = [p for p in ranked if is_manifest(p)]
    manifests += [p for p in all_paths if is_manifest(p) and p not in manifests]
    for path in manifests[:MAX_MANIFESTS]:
        if path not in evidence:
            evidence.append(path)
    return context, evidence


def build_index(paths: list[str], contents: dict[str, str]) -> EvidenceIndex:
    dependencies: dict[str, list[str]] = {}
    for path, text in contents.items():
        for dep in extract_dependencies(path, text):
            dependencies.setdefault(dep, []).append(path)
    return EvidenceIndex(
        paths=sorted(paths),
        dependencies=dependencies,
        contents={p: t[:MAX_EVIDENCE_CHARS] for p, t in contents.items()},
    )


class Ingestor:
    def __init__(self, github: GitHubClient, cache: TTLStore[str, IngestedRepo]) -> None:
        self.github = github
        self.cache = cache

    def get(self, repo_id: str) -> IngestedRepo | None:
        return self.cache.get(repo_id)

    async def ingest(self, repo_url: str) -> IngestedRepo:
        ref = parse_repo_url(repo_url)
        info = await self.github.get_repo(ref)
        sha = await self.github.get_branch_sha(ref, info.default_branch)
        repo_id = make_repo_id(info.full_name, sha)
        cached = self.cache.get(repo_id)
        if cached:
            logger.info("Ingest cache hit for %s@%s", info.full_name, sha[:7])
            return cached

        entries, truncated = await self.github.get_tree(ref, sha)
        all_paths = [e.path for e in entries]
        ranked = rank_files([(e.path, e.size) for e in entries])
        fetchable = [p for p in all_paths if not should_skip(p, 0)]
        context_paths, evidence_paths = select_files(ranked, fetchable)
        contents = await self._fetch_all(ref, sha, evidence_paths)

        context_files = []
        for path in context_paths:
            if path in contents:
                text, cut = truncate_to_tokens(contents[path], TOKENS_PER_FILE)
                context_files.append(FileSnippet(path=path, content=text, truncated=cut))

        owner, name = info.full_name.split("/", 1)
        repo = IngestedRepo(
            repo_id=repo_id,
            meta=RepoMeta(
                owner=owner,
                name=name,
                full_name=info.full_name,
                description=info.description,
                default_branch=info.default_branch,
                sha=sha,
                stars=info.stars,
                language=info.language,
                html_url=info.html_url,
                total_files=len(all_paths),
                tree_truncated=truncated,
            ),
            context_files=context_files,
            index=build_index(all_paths, contents),
            ranked_paths=ranked,
        )
        self.cache.set(repo_id, repo)
        logger.info(
            "Ingested %s@%s: %d files, %d context, %d deps",
            info.full_name, sha[:7], len(all_paths), len(context_files),
            len(repo.index.dependencies),
        )  # fmt: skip
        return repo

    async def _fetch_all(self, ref: RepoRef, sha: str, paths: list[str]) -> dict[str, str]:
        semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)

        async def fetch(path: str) -> tuple[str, str | None]:
            async with semaphore:
                return path, await self.github.get_file_text(ref, sha, path)

        results = await asyncio.gather(*(fetch(p) for p in paths))
        return {path: text for path, text in results if text is not None}
