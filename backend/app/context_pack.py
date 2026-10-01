"""Fit repo files into a fixed prompt budget without losing the big picture."""

import posixpath
import re
from collections import Counter

from app.file_ranking import is_manifest
from app.ingestion import estimate_tokens, truncate_to_tokens
from app.models import FileSnippet

README_SHARE = 0.2
MANIFEST_TOKENS = 200
MIN_FILE_TOKENS = 120

# Lines that describe structure: imports, definitions, routes, exports.
_SKELETON_RE = re.compile(
    r"^\s*(?:"
    r"import\s|from\s+\S+\s+import|export\s|module\.exports|require\(|package\s|use\s"
    r"|(?:async\s+)?def\s|class\s|function\s|(?:pub\s+)?(?:fn|struct|enum|trait|impl)\s"
    r"|func\s|type\s|interface\s|const\s+\w+\s*=\s*(?:async\s*)?\("
    r"|(?:public|private|protected)\s"
    r"|@\w+(?:\.\w+)*\(|app\.\w+\(|router\.\w+\("
    r")"
)


def skeletonize(text: str) -> str:
    """Keep only structural lines (imports, signatures, routes) of a source file."""
    lines = [line.rstrip() for line in text.splitlines() if _SKELETON_RE.match(line)]
    return "\n".join(lines)


def fit_file(snippet: FileSnippet, budget: int) -> str:
    """Return the file text if it fits, otherwise its skeleton cut to the budget."""
    if estimate_tokens(snippet.content) <= budget:
        return snippet.content
    skeleton = skeletonize(snippet.content)
    if skeleton and not posixpath.basename(snippet.path).lower().startswith("readme"):
        text, _ = truncate_to_tokens("# (structure only)\n" + skeleton, budget)
        return text
    text, _ = truncate_to_tokens(snippet.content, budget)
    return text


def _bucket(path: str) -> str:
    """Group a path under its first two directory levels."""
    dirs = path.split("/")[:-1]
    return "/".join(dirs[:2]) + "/" if dirs else "(root)"


def directory_overview(paths: list[str], limit: int = 25) -> str:
    """Summarize the tree as top-level directories with file counts."""
    counts = Counter(_bucket(p) for p in paths)
    lines = [f"{name} ({n} files)" for name, n in counts.most_common(limit)]
    return "\n".join(sorted(lines))


def pack_files(files: list[FileSnippet], budget_tokens: int) -> str:
    """Render files in rank order, sharing the budget fairly between them."""
    blocks: list[str] = []
    remaining = budget_tokens
    for i, snippet in enumerate(files):
        files_left = len(files) - i
        name = posixpath.basename(snippet.path).lower()
        if name.startswith("readme"):
            share = int(budget_tokens * README_SHARE)
        elif is_manifest(snippet.path):
            share = MANIFEST_TOKENS
        else:
            share = remaining // files_left
        share = min(share, remaining)
        if share < MIN_FILE_TOKENS:
            break
        body = fit_file(snippet, share)
        blocks.append(f"### {snippet.path}\n```\n{body}\n```")
        remaining -= estimate_tokens(body) + 10
    return "\n\n".join(blocks)
