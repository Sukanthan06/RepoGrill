"""Decide which repo files are worth reading, and in what order."""

import posixpath

MAX_FILE_BYTES = 200 * 1024

SKIP_DIRS = {
    "node_modules", "vendor", "dist", "build", "out", "target", "bin", "obj",
    ".git", ".next", ".nuxt", ".svelte-kit", ".venv", "venv", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache", "coverage", "htmlcov",
    ".idea", ".vscode", ".gradle", "pods", "generated", "__generated__",
    "migrations", "site-packages", "bower_components", "third_party", ".yarn",
}  # fmt: skip

LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "poetry.lock",
    "pipfile.lock", "uv.lock", "cargo.lock", "gemfile.lock", "composer.lock",
    "go.sum", "pdm.lock", "mix.lock", "pubspec.lock", "packages.lock.json",
}  # fmt: skip

BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp", ".avif", ".tiff",
    ".pdf", ".zip", ".gz", ".tar", ".tgz", ".rar", ".7z", ".jar", ".war", ".class",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".a", ".wasm", ".pyc",
    ".mp3", ".mp4", ".wav", ".ogg", ".webm", ".mov", ".avi", ".flac",
    ".ttf", ".otf", ".woff", ".woff2", ".eot", ".psd", ".sketch", ".fig",
    ".db", ".sqlite", ".sqlite3", ".pkl", ".pt", ".onnx", ".h5", ".npy", ".parquet",
    ".ipynb", ".lock", ".map", ".csv", ".tsv", ".xlsx", ".xls", ".docx", ".pptx",
}  # fmt: skip

GENERATED_SUFFIXES = (
    ".min.js", ".min.css", ".bundle.js", ".chunk.js", ".pb.go", "_pb2.py", "_pb2_grpc.py",
    ".generated.ts", ".generated.js", ".g.dart", ".freezed.dart", ".d.ts",
)  # fmt: skip

MANIFESTS = {
    "package.json", "pyproject.toml", "requirements.txt", "requirements-dev.txt",
    "setup.py", "setup.cfg", "pipfile", "go.mod", "cargo.toml", "gemfile",
    "pom.xml", "build.gradle", "build.gradle.kts", "composer.json", "pubspec.yaml",
    "mix.exs", "dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yaml",
    "makefile", "render.yaml", "vercel.json", "fly.toml", "serverless.yml",
}  # fmt: skip

ENTRY_STEMS = {"main", "app", "index", "server", "cli", "manage", "wsgi", "asgi", "program"}

SOURCE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rs", ".java", ".kt",
    ".kts", ".scala", ".rb", ".php", ".cs", ".fs", ".swift", ".m", ".c", ".h", ".cc",
    ".cpp", ".hpp", ".ex", ".exs", ".erl", ".clj", ".dart", ".lua", ".r", ".jl",
    ".vue", ".svelte", ".astro", ".sql", ".sh", ".graphql", ".proto", ".zig",
}  # fmt: skip

# Directories that rarely explain how the project itself works.
LOW_SIGNAL_DIRS = {
    "docs", "doc", "examples", "example", "samples", "demo", ".devcontainer", ".github",
    "benchmarks", "fixtures", "testdata", "scripts", "tools", "hack", "e2e",
}  # fmt: skip
LOW_SIGNAL_PENALTY = 600

CONFIG_EXTS = {".toml", ".yaml", ".yml", ".json", ".ini", ".cfg", ".conf", ".env.example"}
DOC_EXTS = {".md", ".rst", ".txt"}


def is_manifest(path: str) -> bool:
    name = posixpath.basename(path).lower()
    return name in MANIFESTS or (name.startswith("requirements") and name.endswith(".txt"))


def should_skip(path: str, size: int) -> bool:
    """True for files that add noise rather than signal (deps, binaries, generated)."""
    lowered = path.lower()
    parts = lowered.split("/")
    name = parts[-1]
    if size > MAX_FILE_BYTES:
        return True
    if any(part in SKIP_DIRS for part in parts[:-1]):
        return True
    if name in LOCKFILES:
        return True
    _, ext = posixpath.splitext(name)
    if ext in BINARY_EXTS:
        return True
    return name.endswith(GENERATED_SUFFIXES)


def _is_test(path: str) -> bool:
    lowered = path.lower()
    name = posixpath.basename(lowered)
    return (
        "/test" in f"/{lowered}"
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
        or name.endswith("_test.go")
    )


def _size_bonus(size: int) -> float:
    """Favour moderately sized files: tiny files say little, huge ones blow the budget."""
    if size < 300:
        return -40
    if size <= 15_000:
        return 30
    if size <= 60_000:
        return 10
    return -30


def score_file(path: str, size: int) -> float:
    """Higher means read earlier. README > manifests > entrypoints > shallow source."""
    dirs = path.lower().split("/")[:-1]
    penalty = LOW_SIGNAL_PENALTY if any(d in LOW_SIGNAL_DIRS for d in dirs) else 0
    return _base_score(path, size) - penalty


def _base_score(path: str, size: int) -> float:
    name = posixpath.basename(path).lower()
    stem, ext = posixpath.splitext(name)
    depth = path.count("/")

    if stem == "readme" and ext in DOC_EXTS | {""}:
        return 1000 - depth * 200
    if is_manifest(path):
        return 900 - depth * 60
    if stem in ENTRY_STEMS and ext in SOURCE_EXTS:
        return 700 - depth * 40 + (0 if _is_test(path) else 20)
    if ext in SOURCE_EXTS:
        base = 400 - depth * 35 + _size_bonus(size)
        return base - 150 if _is_test(path) else base
    if ext in CONFIG_EXTS:
        return 150 - depth * 20
    if ext in DOC_EXTS:
        return 100 - depth * 20
    return 0


def rank_files(entries: list[tuple[str, int]]) -> list[str]:
    """Filter out noise and return paths ordered by importance."""
    kept = [(p, s) for p, s in entries if not should_skip(p, s)]
    scored = [(score_file(p, s), p) for p, s in kept]
    scored = [item for item in scored if item[0] > 0]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [path for _, path in scored]
