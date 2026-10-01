from app.manifests import extract_dependencies


def test_package_json() -> None:
    text = '{"dependencies": {"express": "^4"}, "devDependencies": {"@types/node": "20"}}'
    assert extract_dependencies("web/package.json", text) == ["@types/node", "express"]


def test_requirements_with_extras_and_comments() -> None:
    text = "fastapi>=0.100\nuvicorn[standard]==0.30  # server\n-r base.txt\n\nSQLAlchemy\n"
    assert extract_dependencies("requirements-dev.txt", text) == [
        "fastapi",
        "sqlalchemy",
        "uvicorn",
    ]


def test_pyproject_pep621_and_poetry() -> None:
    text = """
[project]
dependencies = ["httpx>=0.27", "pydantic_settings"]
[project.optional-dependencies]
dev = ["pytest"]
[tool.poetry.dependencies]
python = "^3.11"
redis = "^5"
"""
    assert extract_dependencies("pyproject.toml", text) == [
        "httpx",
        "pydantic-settings",
        "pytest",
        "redis",
    ]


def test_go_mod_keeps_short_names() -> None:
    text = "module x\n\nrequire (\n\tgithub.com/gin-gonic/gin v1.9.0\n\tgorm.io/gorm v1.25.0\n)\n"
    deps = extract_dependencies("go.mod", text)
    assert "gin" in deps and "github.com/gin-gonic/gin" in deps and "gorm" in deps


def test_docker_images() -> None:
    text = "services:\n  db:\n    image: postgres:16\n  cache:\n    image: redis:7-alpine\n"
    assert extract_dependencies("docker-compose.yml", text) == ["postgres", "redis"]


def test_broken_manifest_returns_empty() -> None:
    assert extract_dependencies("package.json", "{not json") == []
    assert extract_dependencies("README.md", "anything") == []
