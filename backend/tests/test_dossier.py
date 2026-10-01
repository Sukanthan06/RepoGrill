from app.dossier import PathResolver, build_messages, ground_dossier
from app.ingestion import estimate_tokens
from app.models import (
    CandidateQuestion,
    Dossier,
    EvidenceIndex,
    FileSnippet,
    IngestedRepo,
    RepoMeta,
    TechItem,
)

PATHS = ["README.md", "backend/app/main.py", "backend/app/db.py", "frontend/src/main.tsx"]


def make_repo(file_size: int = 20_000) -> IngestedRepo:
    meta = RepoMeta(
        owner="o", name="r", full_name="o/r", default_branch="main", sha="abc",
        html_url="https://github.com/o/r", total_files=len(PATHS),
    )  # fmt: skip
    files = [
        FileSnippet(path=p, content="def handler():\n    pass\n" * (file_size // 25)) for p in PATHS
    ]
    index = EvidenceIndex(paths=PATHS, dependencies={"fastapi": ["pyproject.toml"]})
    return IngestedRepo(repo_id="id", meta=meta, context_files=files, index=index)


def test_resolver_handles_prefixes_suffixes_and_basenames() -> None:
    resolver = PathResolver(PATHS)
    assert resolver.resolve("./backend/app/main.py") == "backend/app/main.py"
    assert resolver.resolve("app/db.py") == "backend/app/db.py"
    assert resolver.resolve("`main.tsx`") == "frontend/src/main.tsx"
    assert resolver.resolve("src/made_up.py") is None


def test_ground_dossier_drops_hallucinated_paths() -> None:
    question = CandidateQuestion(
        topic="db", difficulty=2, question="q", related_files=["db.py", "nope.py"]
    )
    dossier = Dossier(
        summary="s",
        tech_stack=[TechItem(name="FastAPI", evidence_files=["/backend/app/main.py", "x.py"])],
        candidate_questions=[question] * 6,
    )
    grounded = ground_dossier(dossier, PATHS)
    assert grounded.tech_stack[0].evidence_files == ["backend/app/main.py"]
    assert grounded.candidate_questions[0].related_files == ["backend/app/db.py"]


def test_build_messages_stays_within_budget() -> None:
    messages = build_messages(make_repo(), budget_tokens=3000)
    total = sum(estimate_tokens(m["content"]) for m in messages)
    assert total <= 3000 * 1.15
    assert "o/r" in messages[1]["content"]
    assert "fastapi" in messages[1]["content"]
