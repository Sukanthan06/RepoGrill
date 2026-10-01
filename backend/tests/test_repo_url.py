import pytest

from app.errors import BadRequestError
from app.repo_url import parse_repo_url


@pytest.mark.parametrize(
    "raw",
    [
        "https://github.com/octo/hello-world",
        "https://github.com/octo/hello-world/",
        "https://github.com/octo/hello-world.git",
        "http://www.github.com/octo/hello-world",
        "github.com/octo/hello-world",
        "https://github.com/octo/hello-world/tree/main/src",
        "https://github.com/octo/hello-world/blob/dev/README.md#L10",
        "https://github.com/octo/hello-world?tab=readme",
        "git@github.com:octo/hello-world.git",
        "ssh://git@github.com/octo/hello-world.git",
        "  octo/hello-world  ",
    ],
)
def test_parses_common_formats(raw: str) -> None:
    ref = parse_repo_url(raw)
    assert (ref.owner, ref.name) == ("octo", "hello-world")


def test_keeps_dots_in_repo_names() -> None:
    assert parse_repo_url("https://github.com/vercel/next.js").full_name == "vercel/next.js"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "not a url",
        "https://gitlab.com/octo/hello-world",
        "https://github.com/octo",
        "https://github.com/",
        "https://github.com/octo/bad name",
    ],
)
def test_rejects_invalid(raw: str) -> None:
    with pytest.raises(BadRequestError):
        parse_repo_url(raw)
