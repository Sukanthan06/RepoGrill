"""Load prompt templates from app/prompts and fill `$placeholders`."""

from functools import lru_cache
from pathlib import Path
from string import Template

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@lru_cache
def load_prompt(name: str) -> Template:
    return Template((PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip())


def render(name: str, **values: object) -> str:
    """Render a template; unknown placeholders raise so typos fail loudly."""
    return load_prompt(name).substitute({k: str(v) for k, v in values.items()})
