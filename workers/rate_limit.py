from __future__ import annotations

import asyncio
import time
from collections import defaultdict


class HostRateLimiter:
    def __init__(self, per_host_per_sec: float = 1.0):
        self.min_interval = 1.0 / max(per_host_per_sec, 0.1)
        self._last: dict[str, float] = defaultdict(float)
        self._lock = asyncio.Lock()

    async def wait(self, host: str) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last[host]
            wait_for = self.min_interval - elapsed
            if wait_for > 0:
                await asyncio.sleep(wait_for)
            self._last[host] = time.monotonic()
