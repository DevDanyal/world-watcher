from __future__ import annotations

import httpx

from config.settings import settings
from workers.rate_limit import HostRateLimiter
from workers.robots import RobotsCache
from workers.sources.news_rss import NewsRSSWorker
from workers.sources.page_watch import PageWatchWorker
from workers.sources.price import PriceWorker


class WorkerRegistry:
    def __init__(self):
        self.client = httpx.AsyncClient(follow_redirects=True, timeout=20)
        self.limiter = HostRateLimiter(settings.rate_limit_per_host_per_sec)
        self.robots = RobotsCache(settings.user_agent)
        self._workers = {
            "news_rss": NewsRSSWorker(self.client, self.robots, self.limiter, settings.user_agent),
            "price": PriceWorker(self.client, self.limiter),
            "page_watch": PageWatchWorker(self.client, self.robots, self.limiter, settings.user_agent),
        }

    def get(self, worker_type: str):
        return self._workers.get(worker_type)

    def types(self) -> list[str]:
        return sorted(self._workers.keys())

    async def close(self):
        await self.client.aclose()
