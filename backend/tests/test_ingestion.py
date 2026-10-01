from app.ingestion import build_index, make_repo_id, select_files, truncate_to_tokens
from app.store import TTLStore


def test_truncate_keeps_short_text() -> None:
    assert truncate_to_tokens("short", 100) == ("short", False)


def test_truncate_cuts_on_line_boundary() -> None:
    text = "\n".join(f"line {i}" for i in range(500))
    cut, truncated = truncate_to_tokens(text, 50)
    assert truncated
    assert len(cut) < 50 * 4 + 20
    assert cut.endswith("[truncated]")
    assert cut.splitlines()[-2].startswith("line ")


def test_select_files_always_includes_manifests() -> None:
    ranked = [f"src/f{i}.py" for i in range(60)]
    all_paths = ranked + ["services/api/package.json"]
    context, evidence = select_files(ranked, all_paths)
    assert len(context) == 15
    assert "services/api/package.json" in evidence


def test_build_index_maps_dependencies_to_files() -> None:
    index = build_index(
        ["requirements.txt", "app.py"],
        {"requirements.txt": "flask\nredis>=5\n", "app.py": "import flask"},
    )
    assert index.dependencies == {"flask": ["requirements.txt"], "redis": ["requirements.txt"]}
    assert "app.py" in index.contents


def test_repo_id_is_stable_and_case_insensitive() -> None:
    assert make_repo_id("Octo/Demo", "abc") == make_repo_id("octo/demo", "abc")
    assert make_repo_id("octo/demo", "abc") != make_repo_id("octo/demo", "def")


def test_ttl_store_expires_and_slides() -> None:
    now = [0.0]
    store: TTLStore[str, int] = TTLStore(10, clock=lambda: now[0])
    store.set("a", 1)
    now[0] = 8
    assert store.get("a") == 1  # access slides expiry to t=18
    now[0] = 15
    assert store.get("a") == 1
    now[0] = 40
    assert store.cleanup() == 1
    assert store.get("a") is None
