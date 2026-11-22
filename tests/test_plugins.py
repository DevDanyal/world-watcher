import httpx
import pytest

from workers.base import WorkerContext
from workers.registry import WorkerRegistry


@pytest.mark.asyncio
async def test_registry_has_plugins():
    reg = WorkerRegistry()
    try:
        assert set(reg.types()) >= {"news_rss", "price", "page_watch"}
    finally:
        await reg.close()


@pytest.mark.asyncio
async def test_news_plugin_parses_feed(monkeypatch):
    reg = WorkerRegistry()

    async def fake_get(url, headers=None, timeout=20):
        return httpx.Response(200, request=httpx.Request("GET", url), text="""<?xml version='1.0'?><rss><channel>
        <item><title>Test</title><link>http://example.com</link><description>Hello</description></item>
        </channel></rss>""")

    reg.client.get = fake_get  # type: ignore
    reg.robots.allowed = lambda client, url: _async_true()  # type: ignore

    reports = []

    async def report(p, a):
        reports.append((p, a))

    out = await reg.get("news_rss").run(WorkerContext(report=report, payload={"url": "http://example.com/feed"}))
    await reg.close()
    assert out["ok"] is True
    assert out["items"][0]["title"] == "Test"
    assert reports[-1][0] == 100


async def _async_true():
    return True
