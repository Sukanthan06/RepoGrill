import pytest

from app.file_ranking import rank_files, should_skip


@pytest.mark.parametrize(
    "path,size",
    [
        ("node_modules/react/index.js", 100),
        ("frontend/package-lock.json", 100),
        ("assets/logo.png", 100),
        ("static/app.min.js", 100),
        ("dist/server.js", 100),
        ("vendor/lib/thing.go", 100),
        ("api/user_pb2.py", 100),
        ("src/huge.py", 300 * 1024),
    ],
)
def test_skips_noise(path: str, size: int) -> None:
    assert should_skip(path, size)


def test_keeps_regular_source() -> None:
    assert not should_skip("src/service.py", 4000)


def test_rank_order_readme_manifest_entry_source() -> None:
    entries = [
        ("src/utils/deep/helpers.py", 4000),
        ("src/service.py", 4000),
        ("tests/test_service.py", 4000),
        ("main.py", 2000),
        ("requirements.txt", 200),
        ("README.md", 3000),
        ("node_modules/x/index.js", 10),
        ("docs/guide.md", 2000),
    ]
    ranked = rank_files(entries)
    assert ranked[:4] == ["README.md", "requirements.txt", "main.py", "src/service.py"]
    assert "node_modules/x/index.js" not in ranked
    assert ranked.index("src/service.py") < ranked.index("src/utils/deep/helpers.py")
    assert ranked.index("src/service.py") < ranked.index("tests/test_service.py")


def test_shallow_manifest_beats_nested_entrypoint() -> None:
    ranked = rank_files([("backend/app/main.py", 3000), ("backend/pyproject.toml", 800)])
    assert ranked == ["backend/pyproject.toml", "backend/app/main.py"]


def test_moderate_size_beats_tiny_file_at_same_depth() -> None:
    ranked = rank_files([("src/tiny.py", 50), ("src/core.py", 8000)])
    assert ranked == ["src/core.py", "src/tiny.py"]


def test_docs_and_tooling_rank_below_source() -> None:
    ranked = rank_files(
        [("docs/Makefile", 500), (".devcontainer/setup.sh", 800), ("src/pkg/core.py", 5000)]
    )
    assert ranked[0] == "src/pkg/core.py"
