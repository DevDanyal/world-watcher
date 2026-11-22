from __future__ import annotations

import hashlib

import httpx

from workers.base import WorkerContext


class PageWatchWorker:
    type = "page_watch"

    def __init__(self, client: httpx.AsyncClient, robots, limiter, user_agent: str):
        self.client = client
        self.robots = robots
        self.limiter = limiter
        self.user_agent = user_agent
        self._hashes: dict[str, str] = {}

    async def run(self, ctx: WorkerContext) -> dict:
        url = ctx.payload.get("url")
        if not url:
            await ctx.report(100, "missing url")
            return {"ok": False, "error": "missing_url"}
        await ctx.report(10, f"checking robots for {url}")
        if not await self.robots.allowed(self.client, url):
            await ctx.report(100, "blocked by robots.txt")
            return {"ok": False, "error": "robots_disallowed"}
        host = httpx.URL(url).host or ""
        await self.limiter.wait(host)
        await ctx.report(40, f"fetching {url}")
        r = await self.client.get(url, headers={"User-Agent": self.user_agent}, timeout=20)
        r.raise_for_status()
        content_hash = hashlib.sha256(r.text.encode("utf-8", errors="ignore")).hexdigest()
        old = self._hashes.get(url)
        changed = old is not None and old != content_hash
        self._hashes[url] = content_hash
        await ctx.report(100, "changed" if changed else "no change")
        return {"ok": True, "url": url, "changed": changed, "hash": content_hash}
