"""Run a full text-only RepoGrill interview in the terminal.

Usage:
    python scripts/cli_interview.py https://github.com/owner/repo [--length 5|8|12]
                                    [--difficulty easy|medium|hard]

Type your answer and press Enter. Type /end to stop early.
"""

import argparse
import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable
from functools import partial
from pathlib import Path
from typing import TypeVar, cast

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.errors import AppError, RateLimitedError  # noqa: E402
from app.models import Difficulty, InterviewLength, TurnOut  # noqa: E402
from app.services import Services  # noqa: E402

T = TypeVar("T")
BOLD, DIM, CYAN, RESET = "\033[1m", "\033[2m", "\033[36m", "\033[0m"
MAX_RATE_LIMIT_WAITS = 3


def say(turn: TurnOut) -> None:
    label = f"[{turn.question_number}/{turn.total_questions} · {turn.topic}]"
    print(f"\n{DIM}{label}{RESET}\n{CYAN}{BOLD}Interviewer:{RESET} {turn.text}")


async def with_rate_limit_wait(call: Callable[[], Awaitable[T]]) -> T:
    """Retry a call after provider rate limits, telling the user what's happening."""
    for attempt in range(MAX_RATE_LIMIT_WAITS + 1):
        try:
            return await call()
        except RateLimitedError as exc:
            if attempt == MAX_RATE_LIMIT_WAITS:
                raise
            wait = min(exc.retry_after or 15, 60)
            print(f"{DIM}Rate limited, retrying in {wait:.0f}s…{RESET}")
            await asyncio.sleep(wait)
    raise AssertionError("unreachable")


async def read_answer() -> str:
    while True:
        text = (await asyncio.to_thread(input, f"{BOLD}You:{RESET} ")).strip()
        if text:
            return text


async def run(repo_url: str, length: int, difficulty: str) -> None:
    services = Services.create(get_settings())
    try:
        print(f"{DIM}Reading {repo_url}…{RESET}")
        repo = await services.ingestor.ingest(repo_url)
        print(f"{DIM}Analyzed {len(repo.context_files)} files; building dossier…{RESET}")
        await with_rate_limit_wait(partial(services.dossiers.get_or_create, repo))
        session, turn = await with_rate_limit_wait(
            partial(
                services.interviews.start,
                repo.repo_id,
                cast(InterviewLength, length),
                cast(Difficulty, difficulty),
            )
        )
        say(turn)
        while not session.done:
            answer = await read_answer()
            if answer.lower() == "/end":
                say(services.interviews.end_early(session.session_id))
                break
            turn = await with_rate_limit_wait(
                partial(services.interviews.answer, session.session_id, answer)
            )
            say(turn)
        print(f"\n{DIM}Interview finished: {len(session.transcript)} turns recorded.{RESET}")
    finally:
        await services.aclose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Text-only RepoGrill interview")
    parser.add_argument("repo_url")
    parser.add_argument("--length", type=int, choices=(5, 8, 12), default=5)
    parser.add_argument("--difficulty", choices=("easy", "medium", "hard"), default="medium")
    parser.add_argument("--verbose", action="store_true", help="show HTTP and engine logs")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)
    try:
        asyncio.run(run(args.repo_url, args.length, args.difficulty))
    except AppError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nInterrupted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
