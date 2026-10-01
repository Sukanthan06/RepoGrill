"""List models from the configured provider and suggest values for .env.

Usage:
    python scripts/discover_models.py            # print suggestions
    python scripts/discover_models.py --write    # also update backend/.env
"""

import argparse
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import BACKEND_DIR, get_settings  # noqa: E402

NON_CHAT_MARKERS = ("whisper", "tts", "orpheus", "guard", "embed", "rerank", "vision-only")
SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)b\b", re.IGNORECASE)


def param_billions(model_id: str) -> float:
    """Best-effort parameter count parsed from the model id (e.g. '...-70b' -> 70)."""
    sizes = [float(m) for m in SIZE_RE.findall(model_id)]
    return max(sizes) if sizes else 0.0


def is_chat_model(model_id: str) -> bool:
    lowered = model_id.lower()
    return not any(marker in lowered for marker in NON_CHAT_MARKERS)


def suggest(model_ids: list[str]) -> dict[str, str]:
    chat = [m for m in model_ids if is_chat_model(m) and param_billions(m) > 0]
    whisper = [m for m in model_ids if "whisper" in m.lower()]
    suggestions: dict[str, str] = {}
    if chat:
        by_size = sorted(chat, key=param_billions)
        suggestions["LLM_MODEL"] = by_size[-1]
        # Smallest capable model: tiny (<14B) models struggle with strict JSON.
        fast_pool = [m for m in by_size if param_billions(m) >= 14] or by_size
        suggestions["LLM_FAST_MODEL"] = fast_pool[0]
    if whisper:
        # Prefer the turbo variant: much faster and plenty accurate for interviews.
        turbo = [m for m in whisper if "turbo" in m.lower()]
        suggestions["STT_MODEL"] = (turbo or sorted(whisper))[0]
    return suggestions


def fetch_models(base_url: str, api_key: str) -> list[str]:
    response = httpx.get(
        f"{base_url.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=20,
    )
    response.raise_for_status()
    return sorted(item["id"] for item in response.json().get("data", []))


def write_env(path: Path, values: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(values)
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in remaining:
            lines[i] = f"{key}={remaining.pop(key)}"
    lines += [f"{key}={value}" for key, value in remaining.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write suggestions to backend/.env")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.llm_api_key:
        print("LLM_API_KEY is not set. Add it to backend/.env first.", file=sys.stderr)
        return 1
    try:
        models = fetch_models(settings.llm_base_url, settings.llm_api_key)
    except httpx.HTTPError as exc:
        print(f"Could not list models: {exc}", file=sys.stderr)
        return 1

    print(f"Models available at {settings.llm_base_url}:")
    for model_id in models:
        print(f"  - {model_id}")
    suggestions = suggest(models)
    print("\nSuggested .env values:")
    for key, value in suggestions.items():
        print(f"{key}={value}")

    if args.write and suggestions:
        env_path = BACKEND_DIR / ".env"
        write_env(env_path, suggestions)
        print(f"\nWrote {len(suggestions)} values to {env_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
