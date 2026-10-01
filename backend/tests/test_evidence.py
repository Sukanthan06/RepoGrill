from app.evidence import EvidenceSearcher, canonical, verify_claim
from app.models import EvidenceIndex, ExtractedClaim

INDEX = EvidenceIndex(
    paths=["README.md", "requirements.txt", "app/db.py", "app/cache.py", "Dockerfile"],
    dependencies={"flask": ["requirements.txt"], "sqlalchemy": ["requirements.txt"]},
    contents={
        "README.md": "# Demo\nWe might add Redis later.\n",
        "requirements.txt": "flask\nsqlalchemy\n",
        "app/db.py": "import sqlite3\n\nconn = sqlite3.connect('app.db')\n",
        "app/cache.py": "from functools import lru_cache\n\n@lru_cache(maxsize=128)\ndef get(x):\n"
        "    return x\n",
        "Dockerfile": "FROM python:3.11\n",
    },
)
SEARCHER = EvidenceSearcher(INDEX)


def claim(*keywords: str) -> ExtractedClaim:
    return ExtractedClaim(claim="c", keywords=list(keywords), kind="technology")


def test_aliases_resolve_to_canonical_names() -> None:
    assert canonical("PostgreSQL") == "postgres"
    assert canonical("psycopg2") == "postgres"
    assert canonical("something-else") is None


def test_dependency_claim_verified_with_manifest_evidence() -> None:
    verdict = verify_claim(claim("flask"), SEARCHER)
    assert verdict.status == "verified"
    assert verdict.matches[0].path == "requirements.txt"
    assert verdict.matches[0].source == "dependency"


def test_content_claim_verified_with_line_number() -> None:
    verdict = verify_claim(claim("lru_cache"), SEARCHER)
    assert verdict.status == "verified"
    match = verdict.matches[0]
    assert (match.path, match.line) == ("app/cache.py", 1)


def test_planted_postgres_claim_is_contradicted_by_sqlite() -> None:
    verdict = verify_claim(claim("postgres"), SEARCHER)
    assert verdict.status == "contradicted"
    assert "sqlite" in verdict.explanation
    assert verdict.matches[0].path == "app/db.py"


def test_docs_only_mention_is_ambiguous() -> None:
    verdict = verify_claim(claim("redis"), SEARCHER)
    assert verdict.status == "unverified" and verdict.ambiguous
    assert verdict.matches[0].path == "README.md"


def test_missing_primary_with_related_terms_is_ambiguous() -> None:
    verdict = verify_claim(claim("varnish", "cache"), SEARCHER)
    assert verdict.status == "unverified" and verdict.ambiguous


def test_no_evidence_is_unverified() -> None:
    verdict = verify_claim(claim("kafka"), SEARCHER)
    assert verdict.status == "unverified" and not verdict.ambiguous


def test_word_boundaries_prevent_substring_hits() -> None:
    index = EvidenceIndex(paths=["a.py"], contents={"a.py": "postgresql_like = 1\nimport pgx\n"})
    assert verify_claim(claim("pg"), EvidenceSearcher(index)).status == "unverified"


def test_path_match_respects_boundaries() -> None:
    index = EvidenceIndex(paths=["src/expression.py", "docker-compose.yml"])
    searcher = EvidenceSearcher(index)
    assert searcher.find("express") == []
    assert [m.path for m in searcher.find("docker")] == ["docker-compose.yml"]
