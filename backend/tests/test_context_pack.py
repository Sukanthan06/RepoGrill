from app.context_pack import directory_overview, pack_files, skeletonize
from app.ingestion import estimate_tokens
from app.models import FileSnippet

PY_SOURCE = """import os
from fastapi import FastAPI

app = FastAPI()

@app.get("/items")
async def list_items():
    data = load()
    return [transform(x) for x in data]

class Repo:
    def save(self, item):
        self.items.append(item)
"""


def test_skeleton_keeps_structure_only() -> None:
    skeleton = skeletonize(PY_SOURCE)
    assert "from fastapi import FastAPI" in skeleton
    assert '@app.get("/items")' in skeleton
    assert "class Repo:" in skeleton
    assert "self.items.append" not in skeleton


def test_pack_respects_budget() -> None:
    files = [FileSnippet(path=f"src/mod{i}.py", content=PY_SOURCE * 40) for i in range(10)]
    packed = pack_files(files, 1500)
    assert estimate_tokens(packed) < 1500 * 1.15
    assert "src/mod0.py" in packed


def test_small_files_are_included_verbatim() -> None:
    files = [FileSnippet(path="main.py", content="print('hi')\n")]
    assert "print('hi')" in pack_files(files, 1000)


def test_directory_overview_counts() -> None:
    overview = directory_overview(["README.md", "src/a/x.py", "src/a/y.py", "src/b.py"])
    assert "src/a/ (2 files)" in overview
    assert "(root) (1 files)" in overview
