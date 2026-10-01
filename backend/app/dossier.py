"""Generate and cache the project dossier that drives the interview."""

import asyncio
import logging
import posixpath
import re

from app.context_pack import directory_overview, pack_files
from app.ingestion import estimate_tokens
from app.llm_client import LLMClient
from app.models import Dossier, IngestedRepo
from app.prompt_loader import render
from app.store import TTLStore

logger = logging.getLogger(__name__)

MAX_DEPENDENCIES_LISTED = 60
MAX_NOTABLE_FILES = 60
DOSSIER_MAX_OUTPUT_TOKENS = 6000
_LEADING_SLASHES_RE = re.compile(r"^(?:\./|/)+")


class PathResolver:
    """Map model-cited paths onto real repository paths, dropping hallucinations."""

    def __init__(self, paths: list[str]) -> None:
        self._paths = set(paths)
        self._by_name: dict[str, list[str]] = {}
        for path in paths:
            self._by_name.setdefault(posixpath.basename(path).lower(), []).append(path)

    def resolve(self, cited: str) -> str | None:
        cleaned = _LEADING_SLASHES_RE.sub("", cited.strip().strip("`"))
        if cleaned in self._paths:
            return cleaned
        suffix_matches = [p for p in self._paths if p.endswith("/" + cleaned)]
        if len(suffix_matches) == 1:
            return suffix_matches[0]
        by_name = self._by_name.get(posixpath.basename(cleaned).lower(), [])
        return by_name[0] if len(by_name) == 1 else None

    def resolve_all(self, cited: list[str]) -> list[str]:
        resolved = (self.resolve(c) for c in cited)
        return list(dict.fromkeys(p for p in resolved if p))


def ground_dossier(dossier: Dossier, paths: list[str]) -> Dossier:
    """Replace every cited file list with paths that really exist."""
    resolver = PathResolver(paths)
    for item in dossier.tech_stack:
        item.evidence_files = resolver.resolve_all(item.evidence_files)
    for component in dossier.architecture.components:
        component.files = resolver.resolve_all(component.files)
    for decision in dossier.key_design_decisions:
        decision.files = resolver.resolve_all(decision.files)
    for spot in dossier.likely_weak_spots:
        spot.files = resolver.resolve_all(spot.files)
    for question in dossier.candidate_questions:
        question.related_files = resolver.resolve_all(question.related_files)
    return dossier


def build_messages(repo: IngestedRepo, budget_tokens: int) -> list[dict[str, str]]:
    meta = repo.meta
    deps = sorted(repo.index.dependencies)
    dep_text = ", ".join(deps[:MAX_DEPENDENCIES_LISTED]) or "(none detected)"
    if len(deps) > MAX_DEPENDENCIES_LISTED:
        dep_text += f", … (+{len(deps) - MAX_DEPENDENCIES_LISTED} more)"
    header = render(
        "dossier_user",
        full_name=meta.full_name,
        description=meta.description or "(none)",
        language=meta.language or "unknown",
        total_files=meta.total_files,
        overview=directory_overview(repo.index.paths),
        notable_files="\n".join(repo.ranked_paths[:MAX_NOTABLE_FILES]) or "(none)",
        dependencies=dep_text,
        files="",
    )
    system = render("dossier_system")
    file_budget = budget_tokens - estimate_tokens(system) - estimate_tokens(header)
    files = pack_files(repo.context_files, max(file_budget, 500))
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": header + files},
    ]


class DossierService:
    def __init__(self, llm: LLMClient, cache: TTLStore[str, Dossier], budget_tokens: int) -> None:
        self.llm = llm
        self.cache = cache
        self.budget_tokens = budget_tokens
        self._inflight: dict[str, asyncio.Task[Dossier]] = {}

    async def get_or_create(self, repo: IngestedRepo) -> Dossier:
        """Return the cached dossier for repo+SHA, generating it at most once."""
        cached = self.cache.get(repo.repo_id)
        if cached:
            return cached
        task = self._inflight.get(repo.repo_id)
        if task is None:
            task = asyncio.create_task(self._generate(repo))
            self._inflight[repo.repo_id] = task
            task.add_done_callback(lambda _: self._inflight.pop(repo.repo_id, None))
        return await asyncio.shield(task)

    async def _generate(self, repo: IngestedRepo) -> Dossier:
        messages = build_messages(repo, self.budget_tokens)
        logger.info(
            "Generating dossier for %s (~%d prompt tokens)",
            repo.meta.full_name,
            sum(estimate_tokens(m["content"]) for m in messages),
        )
        dossier = await self.llm.chat_json(
            messages, Dossier, max_tokens=DOSSIER_MAX_OUTPUT_TOKENS, temperature=0.3
        )
        dossier = ground_dossier(dossier, repo.index.paths)
        self.cache.set(repo.repo_id, dossier)
        return dossier
