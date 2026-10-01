from scripts.discover_models import suggest

MODELS = [
    "allam-2-7b",
    "meta-llama/llama-prompt-guard-2-86m",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "whisper-large-v3",
    "whisper-large-v3-turbo",
]


def test_suggest_picks_strong_fast_and_whisper() -> None:
    result = suggest(MODELS)
    assert result["LLM_MODEL"] == "openai/gpt-oss-120b"
    assert result["LLM_FAST_MODEL"] == "openai/gpt-oss-20b"
    assert result["STT_MODEL"] == "whisper-large-v3-turbo"


def test_suggest_handles_empty_list() -> None:
    assert suggest([]) == {}
