"""Exponential backoff with jitter for outbound HTTP calls."""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable

import httpx

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRY_AFTER_SECONDS = 20.0


def is_retryable(response: httpx.Response) -> bool:
    return response.status_code in RETRYABLE_STATUS


def backoff_delay(attempt: int, base: float = 0.5, cap: float = 8.0) -> float:
    """Full-jitter backoff: random value in [0, min(cap, base * 2**attempt)]."""
    return random.uniform(0, min(cap, base * (2**attempt)))


def retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        return min(float(value), MAX_RETRY_AFTER_SECONDS)
    except ValueError:
        return None


async def send_with_retry(
    send: Callable[[], Awaitable[httpx.Response]],
    *,
    max_attempts: int = 4,
    label: str = "request",
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> httpx.Response:
    """Call `send` until it returns a non-retryable response or attempts run out.

    Network errors are retried too. The last response (possibly a 429/5xx) is
    returned so the caller can decide how to surface it.
    """
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            response = await send()
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_exc = exc
            logger.warning("%s failed (%s), attempt %d/%d", label, type(exc).__name__,
                           attempt + 1, max_attempts)
        else:
            if not is_retryable(response) or attempt == max_attempts - 1:
                return response
            logger.warning("%s got HTTP %d, attempt %d/%d", label, response.status_code,
                           attempt + 1, max_attempts)
            hinted = retry_after_seconds(response)
            await sleep(hinted if hinted is not None else backoff_delay(attempt))
            continue
        if attempt < max_attempts - 1:
            await sleep(backoff_delay(attempt))
    assert last_exc is not None
    raise last_exc
