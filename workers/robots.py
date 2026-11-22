from __future__ import annotations

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx


class RobotsCache:
    def __init__(self, user_agent: str):
        self.user_agent = user_agent
        self._cache: dict[str, RobotFileParser | None] = {}

    async def allowed(self, client: httpx.AsyncClient, url: str) -> bool:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._cache:
            robots_url = f"{base}/robots.txt"
            rp: RobotFileParser | None = None
            try:
                r = await client.get(robots_url, timeout=10)
                if r.status_code < 400:
                    rp = RobotFileParser()
                    rp.parse(r.text.splitlines())
            except Exception:
                rp = None
            self._cache[base] = rp
        rp = self._cache[base]
        if rp is None:
            return True
        return bool(rp.can_fetch(self.user_agent, url))
