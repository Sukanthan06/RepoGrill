"""Extract dependency names from common package manifests."""

import json
import logging
import posixpath
import re
import tomllib
from collections.abc import Callable, Iterable

logger = logging.getLogger(__name__)

_REQ_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_GO_REQUIRE_RE = re.compile(r"^\s*(?:require\s+)?([a-z0-9.\-]+\.[a-z]+/[^\s]+)\s+v", re.MULTILINE)
_GEM_RE = re.compile(r"""^\s*gem\s+['"]([^'"]+)['"]""", re.MULTILINE)
_MAVEN_RE = re.compile(r"<artifactId>\s*([^<\s]+)\s*</artifactId>")
_GRADLE_RE = re.compile(
    r"(?:implementation|api|compile|runtimeOnly|testImplementation)"
    r"""\s*\(?\s*['"]([^:'"]+):([^:'"]+)"""
)
_PUBSPEC_RE = re.compile(r"^\s{2}([a-z_][a-z0-9_]*):", re.MULTILINE)
_DOCKER_FROM_RE = re.compile(r"^\s*FROM\s+([^\s:@]+)", re.IGNORECASE | re.MULTILINE)
_COMPOSE_IMAGE_RE = re.compile(r"^\s*image:\s*['\"]?([^\s:'\"@]+)", re.MULTILINE)


def _normalize(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _requirement_names(lines: Iterable[str]) -> list[str]:
    names = []
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith(("-", "git+", "http://", "https://")):
            continue
        match = _REQ_NAME_RE.match(line)
        if match:
            names.append(match.group(1))
    return names


def parse_requirements(text: str) -> list[str]:
    return _requirement_names(text.splitlines())


def parse_package_json(text: str) -> list[str]:
    data = json.loads(text)
    names: list[str] = []
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        section = data.get(key)
        if isinstance(section, dict):
            names.extend(section)
    return names


def parse_pyproject(text: str) -> list[str]:
    data = tomllib.loads(text)
    project = data.get("project", {})
    names = _requirement_names(project.get("dependencies", []))
    for group in project.get("optional-dependencies", {}).values():
        names += _requirement_names(group)
    for group in data.get("dependency-groups", {}).values():
        names += _requirement_names(g for g in group if isinstance(g, str))
    poetry = data.get("tool", {}).get("poetry", {})
    names += [n for n in poetry.get("dependencies", {}) if n.lower() != "python"]
    names += list(poetry.get("dev-dependencies", {}))
    for group in poetry.get("group", {}).values():
        names += list(group.get("dependencies", {}))
    return names


def parse_cargo(text: str) -> list[str]:
    data = tomllib.loads(text)
    names: list[str] = []
    for key in ("dependencies", "dev-dependencies", "build-dependencies"):
        names += list(data.get(key, {}))
    return names


def parse_go_mod(text: str) -> list[str]:
    modules = _GO_REQUIRE_RE.findall(text)
    # Keep both the full module path and its last segment (e.g. "gin" for gin-gonic/gin).
    return modules + [m.rstrip("/").split("/")[-1] for m in modules]


def parse_gradle(text: str) -> list[str]:
    return [artifact for _, artifact in _GRADLE_RE.findall(text)]


def parse_composer(text: str) -> list[str]:
    data = json.loads(text)
    names: list[str] = []
    for key in ("require", "require-dev"):
        names += [n for n in data.get(key, {}) if "/" in n]
    return names + [n.split("/")[-1] for n in names]


def parse_pubspec(text: str) -> list[str]:
    block = re.search(r"^dependencies:\n((?:\s{2}.*\n?)+)", text, re.MULTILINE)
    return _PUBSPEC_RE.findall(block.group(1)) if block else []


def parse_docker(text: str) -> list[str]:
    images = _DOCKER_FROM_RE.findall(text) + _COMPOSE_IMAGE_RE.findall(text)
    return [i.split("/")[-1] for i in images if i.lower() != "scratch"]


Parser = Callable[[str], list[str]]

PARSERS: dict[str, Parser] = {
    "package.json": parse_package_json,
    "pyproject.toml": parse_pyproject,
    "cargo.toml": parse_cargo,
    "go.mod": parse_go_mod,
    "gemfile": lambda t: _GEM_RE.findall(t),
    "pom.xml": lambda t: _MAVEN_RE.findall(t),
    "build.gradle": parse_gradle,
    "build.gradle.kts": parse_gradle,
    "composer.json": parse_composer,
    "pubspec.yaml": parse_pubspec,
    "dockerfile": parse_docker,
    "docker-compose.yml": parse_docker,
    "docker-compose.yaml": parse_docker,
    "compose.yaml": parse_docker,
}


def parser_for(path: str) -> Parser | None:
    name = posixpath.basename(path).lower()
    if name.startswith("requirements") and name.endswith(".txt"):
        return parse_requirements
    return PARSERS.get(name)


def extract_dependencies(path: str, text: str) -> list[str]:
    """Return normalized dependency names declared in a manifest, or [] if unknown."""
    parser = parser_for(path)
    if parser is None:
        return []
    try:
        names = parser(text)
    except (ValueError, tomllib.TOMLDecodeError, AttributeError, TypeError) as exc:
        logger.info("Could not parse %s: %s", path, exc)
        return []
    return sorted({_normalize(n) for n in names if n and n.strip()})
