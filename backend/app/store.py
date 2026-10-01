"""Small in-memory key/value stores with sliding TTL expiry."""

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from typing import Generic, TypeVar

logger = logging.getLogger(__name__)

K = TypeVar("K")
V = TypeVar("V")


class TTLStore(Generic[K, V]):
    """Dict-like store whose entries expire `ttl` seconds after last access."""

    def __init__(self, ttl_seconds: float, clock: Callable[[], float] = time.monotonic) -> None:
        self.ttl = ttl_seconds
        self._clock = clock
        self._items: dict[K, tuple[float, V]] = {}

    def __len__(self) -> int:
        return len(self._items)

    def set(self, key: K, value: V) -> None:
        self._items[key] = (self._clock() + self.ttl, value)

    def get(self, key: K) -> V | None:
        item = self._items.get(key)
        if item is None:
            return None
        expires, value = item
        if expires <= self._clock():
            self._items.pop(key, None)
            return None
        self._items[key] = (self._clock() + self.ttl, value)
        return value

    def cleanup(self) -> int:
        """Drop expired entries and return how many were removed."""
        now = self._clock()
        expired = [k for k, (exp, _) in self._items.items() if exp <= now]
        for key in expired:
            del self._items[key]
        return len(expired)


async def run_periodic_cleanup(stores: list[TTLStore], interval_seconds: float = 300) -> None:
    """Background task: sweep expired entries until cancelled."""
    with contextlib.suppress(asyncio.CancelledError):
        while True:
            await asyncio.sleep(interval_seconds)
            removed = sum(store.cleanup() for store in stores)
            if removed:
                logger.info("Cleaned up %d expired entries", removed)
