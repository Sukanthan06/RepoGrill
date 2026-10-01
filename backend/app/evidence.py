"""Deterministic claim verification against the repo's evidence index.

Order of checks: declared dependencies -> file paths -> content search. A claimed
technology that is absent while a direct alternative is present (e.g. Postgres vs
SQLite) is marked contradicted. Matches that only appear in docs, or where only the
secondary keywords match, are flagged ambiguous for LLM adjudication.
"""

import posixpath
import re
from dataclasses import dataclass, field

from app.file_ranking import is_manifest
from app.models import ClaimStatus, EvidenceIndex, ExtractedClaim

DOC_EXTS = {".md", ".rst", ".txt", ".adoc"}
MAX_EVIDENCE = 3
SNIPPET_CHARS = 160

# Canonical name -> spellings found in manifests, imports, paths and prose.
ALIASES: dict[str, set[str]] = {
    "postgres": {"postgres", "postgresql", "psycopg", "psycopg2", "psycopg2-binary", "asyncpg",
                 "pg", "pg-promise", "postgres.js"},
    "mysql": {"mysql", "mysqlclient", "pymysql", "mysql2", "mariadb"},
    "sqlite": {"sqlite", "sqlite3", "better-sqlite3", "aiosqlite"},
    "mongodb": {"mongodb", "mongo", "pymongo", "mongoose", "motor"},
    "redis": {"redis", "ioredis", "aioredis", "redis-py", "upstash"},
    "memcached": {"memcached", "pymemcache", "memjs"},
    "dynamodb": {"dynamodb"},
    "kafka": {"kafka", "kafkajs", "kafka-python", "confluent-kafka", "aiokafka"},
    "rabbitmq": {"rabbitmq", "amqp", "pika", "amqplib", "aio-pika"},
    "celery": {"celery"},
    "sqs": {"sqs"},
    "graphql": {"graphql", "apollo", "graphene", "strawberry-graphql", "ariadne"},
    "grpc": {"grpc", "grpcio", "@grpc/grpc-js"},
    "docker": {"docker", "dockerfile", "docker-compose"},
    "kubernetes": {"kubernetes", "k8s", "helm"},
    "jwt": {"jwt", "pyjwt", "jsonwebtoken", "python-jose", "jose", "jwt-decode"},
    "websocket": {"websocket", "websockets", "socket.io", "ws"},
    "elasticsearch": {"elasticsearch", "opensearch"},
    "sqlalchemy": {"sqlalchemy"},
    "prisma": {"prisma", "@prisma/client"},
    "typescript": {"typescript", "tsconfig"},
    "react": {"react", "react-dom"},
    "nextjs": {"next", "nextjs", "next.js"},
    "vue": {"vue", "nuxt"},
    "angular": {"angular", "@angular/core"},
    "svelte": {"svelte", "sveltekit", "@sveltejs/kit"},
    "fastapi": {"fastapi"},
    "flask": {"flask"},
    "django": {"django"},
    "express": {"express"},
    "nestjs": {"nestjs", "@nestjs/core"},
    "spring": {"spring", "spring-boot"},
    "pytest": {"pytest"},
    "jest": {"jest"},
    "vitest": {"vitest"},
    "github actions": {".github/workflows"},
}  # fmt: skip

# Technologies that usually replace each other: claiming one when another is present
# is a contradiction rather than a mere absence of evidence.
ALTERNATIVES: list[set[str]] = [
    {"postgres", "mysql", "sqlite", "mongodb", "dynamodb"},
    {"redis", "memcached"},
    {"kafka", "rabbitmq", "sqs"},
    {"react", "vue", "angular", "svelte"},
    {"fastapi", "flask", "django", "express", "nestjs", "spring"},
    {"sqlalchemy", "prisma"},
    {"pytest", "jest", "vitest"},
]


@dataclass
class Match:
    path: str
    line: int | None
    snippet: str
    source: str  # dependency | path | content

    @property
    def in_docs(self) -> bool:
        if self.source == "dependency" or is_manifest(self.path):
            return False
        return posixpath.splitext(self.path)[1].lower() in DOC_EXTS


@dataclass
class Verdict:
    status: ClaimStatus
    explanation: str
    matches: list[Match] = field(default_factory=list)
    ambiguous: bool = False


def canonical(keyword: str) -> str | None:
    lowered = keyword.strip().lower()
    for name, spellings in ALIASES.items():
        if lowered == name or lowered in spellings:
            return name
    return None


def spellings(keyword: str) -> set[str]:
    name = canonical(keyword)
    lowered = keyword.strip().lower()
    return ALIASES[name] | {name, lowered} if name else {lowered}


def _keyword_regex(term: str) -> re.Pattern[str]:
    parts = [re.escape(p) for p in re.split(r"[\s_-]+", term) if p]
    # \w boundaries: "pg" must not match "pgx" and "postgres" must not match "postgres_like".
    return re.compile(r"(?<!\w)" + r"[\s_-]*".join(parts) + r"(?!\w)", re.I)


class EvidenceSearcher:
    def __init__(self, index: EvidenceIndex) -> None:
        self.index = index

    def find(self, keyword: str) -> list[Match]:
        """All evidence for a keyword: dependencies first, then paths, then contents."""
        terms = spellings(keyword)
        matches = self._in_dependencies(terms) + self._in_paths(terms) + self._in_contents(terms)
        return _rank(matches)

    def _in_dependencies(self, terms: set[str]) -> list[Match]:
        return [
            Match(file, None, f"declares dependency '{dep}'", "dependency")
            for dep, files in self.index.dependencies.items()
            if dep in terms or dep.split("/")[-1] in terms
            for file in files
        ]

    def _in_paths(self, terms: set[str]) -> list[Match]:
        # Alphanumeric boundaries so "express" doesn't match "expression.py".
        patterns = [
            re.compile(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])")
            for t in terms
            if len(t) >= 3
        ]
        hits = [p for p in self.index.paths if any(rx.search(p.lower()) for rx in patterns)]
        return [Match(path, None, "", "path") for path in hits[: MAX_EVIDENCE * 3]]

    def _in_contents(self, terms: set[str]) -> list[Match]:
        patterns = [_keyword_regex(t) for t in terms if len(t) >= 2]
        matches = []
        for path, text in self.index.contents.items():
            found = next((m for rx in patterns if (m := rx.search(text))), None)
            if found:
                line = text.count("\n", 0, found.start()) + 1
                snippet = text.splitlines()[line - 1].strip()[:SNIPPET_CHARS]
                matches.append(Match(path, line, snippet, "content"))
        return matches


def _rank(matches: list[Match]) -> list[Match]:
    order = {"dependency": 0, "content": 1, "path": 2}
    unique: dict[tuple[str, str], Match] = {}
    for match in matches:
        unique.setdefault((match.path, match.source), match)
    return sorted(unique.values(), key=lambda m: (m.in_docs, order[m.source], m.path))


def _alternatives_present(keyword: str, searcher: EvidenceSearcher) -> tuple[str, list[Match]]:
    name = canonical(keyword)
    if not name:
        return "", []
    for group in ALTERNATIVES:
        if name not in group:
            continue
        for other in sorted(group - {name}):
            found = [m for m in searcher.find(other) if not m.in_docs]
            if found:
                return other, found
    return "", []


def verify_claim(claim: ExtractedClaim, searcher: EvidenceSearcher) -> Verdict:
    """Label a claim using only the evidence index (no LLM)."""
    keywords = [k for k in claim.keywords if k.strip()]
    if not keywords:
        return Verdict("unverified", "No concrete keywords to check", ambiguous=False)
    primary, secondary = keywords[0], keywords[1:]

    found = searcher.find(primary)
    code_matches = [m for m in found if not m.in_docs]
    if code_matches:
        return Verdict("verified", f"Found '{primary}' in the code", code_matches[:MAX_EVIDENCE])

    alternative, alt_matches = _alternatives_present(primary, searcher)
    if alternative:
        return Verdict(
            "contradicted",
            f"No sign of {primary}; the repo uses {alternative} instead",
            alt_matches[:MAX_EVIDENCE],
        )

    if found:  # only mentioned in documentation
        return Verdict(
            "unverified", f"'{primary}' only appears in docs", found[:MAX_EVIDENCE], ambiguous=True
        )

    partial = [m for k in secondary for m in searcher.find(k) if not m.in_docs]
    if partial:
        return Verdict(
            "unverified",
            f"No '{primary}' found, but related terms appear",
            _rank(partial)[:MAX_EVIDENCE],
            ambiguous=True,
        )
    return Verdict("unverified", f"No evidence of '{primary}' in the repository")
