from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

from workers.base import WorkerContext


class NewsRSSWorker:
    type = "news_rss"

    def __init__(self, client: httpx.AsyncClient, robots, limiter, user_agent: str):
        self.client = client
        self.robots = robots
        self.limiter = limiter
        self.user_agent = user_agent

    async def run(self, ctx: WorkerContext) -> dict:
        feed_url = ctx.payload.get("url") or "https://hnrss.org/frontpage"
        await ctx.report(5, f"checking robots for {feed_url}")
        if not await self.robots.allowed(self.client, feed_url):
            await ctx.report(100, "blocked by robots.txt")
            return {"ok": False, "error": "robots_disallowed"}
        host = httpx.URL(feed_url).host or ""
        await self.limiter.wait(host)
        await ctx.report(30, f"fetching RSS {feed_url}")
        r = await self.client.get(feed_url, headers={"User-Agent": self.user_agent}, timeout=20)
        r.raise_for_status()
        await ctx.report(70, "parsing feed")
        items = _parse_feed(r.text)
        await ctx.report(100, f"fetched {len(items)} items")
        return {"ok": True, "items": items[:10]}


def _parse_feed(xml_text: str) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return []
    items = []
    # RSS
    for item in root.findall(".//item"):
        items.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "summary": (item.findtext("description") or "").strip()[:300],
            }
        )
    if items:
        return items
    # Atom
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//a:entry", ns):
        link_el = entry.find("a:link", ns)
        items.append(
            {
                "title": (entry.findtext("a:title", namespaces=ns) or "").strip(),
                "link": (link_el.attrib.get("href", "") if link_el is not None else "").strip(),
                "summary": (entry.findtext("a:summary", namespaces=ns) or entry.findtext("a:content", namespaces=ns) or "").strip()[:300],
            }
        )
    return items
