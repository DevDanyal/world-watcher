from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from backend.ai.schemas import AnalysisItem
from backend.ai.service import AIService
from backend.alerts.dispatcher import AlertDispatcher
from backend.alerts.engine import AlertEngine
from backend.alerts.models import AlertEvent
from backend.alerts.repository import AlertRepository
from backend.worker_engine import Job
from workers.base import WorkerContext
from workers.registry import WorkerRegistry

logger = logging.getLogger(__name__)


@dataclass
class Pipeline:
    engine: Any
    registry: WorkerRegistry
    ai: AIService
    alert_repo: AlertRepository
    alert_engine: AlertEngine
    dispatcher: AlertDispatcher

    @classmethod
    def create(cls, engine: Any) -> "Pipeline":
        repo = AlertRepository()
        alert_engine = AlertEngine(repo)
        return cls(
            engine=engine,
            registry=WorkerRegistry(),
            ai=AIService(),
            alert_repo=repo,
            alert_engine=alert_engine,
            dispatcher=AlertDispatcher(repo, engine),
        )

    async def close(self) -> None:
        await self.registry.close()

    async def process_item(self, source_type: str, item: dict[str, Any]) -> dict[str, Any]:
        title = str(item.get("title") or item.get("symbol") or item.get("url") or source_type)
        content = str(item.get("summary") or item.get("content") or item.get("url") or title)
        metadata = {k: v for k, v in item.items() if k not in {"title", "summary", "content"}}

        analysis = await self.ai.analyze(AnalysisItem(source_type=source_type, title=title, content=content, metadata=metadata))
        event = AlertEvent(
            source_type=source_type,
            title=title,
            content=content,
            importance=analysis.importance,
            reason=analysis.reason,
            price_change_percent=_to_float(item.get("change_24h")),
            metadata={"analysis": analysis.model_dump(), **metadata},
        )
        await self.engine._emit(
            {
                "type": "event",
                "event": {
                    "ts": event.triggered_at,
                    "level": "info",
                    "message": f"analyzed {source_type}: {title} (importance={analysis.importance})",
                    "job_id": None,
                    "worker_id": None,
                },
            }
        )
        matches = self.alert_engine.evaluate(event)
        dispatched = []
        for match in matches:
            dispatched.append(await self.dispatcher.dispatch(match))
        return {"analysis": analysis.model_dump(), "matches": len(matches), "dispatched": dispatched}

    async def run_source_job(self, worker_type: str, payload: dict[str, Any], ctx) -> dict[str, Any]:
        worker = self.registry.get(worker_type)
        if worker is None:
            raise ValueError(f"unknown worker type: {worker_type}")
        result = await worker.run(WorkerContext(report=ctx.report, payload=payload))
        items = _normalize_items(worker_type, payload, result)
        processed = []
        for item in items:
            processed.append(await self.process_item(worker_type, item))
        await ctx.report(100, f"{worker_type} processed {len(processed)} items")
        return {"result": result, "processed": processed}

    def make_source_job(self, worker_type: str, payload: dict[str, Any] | None = None, name: str | None = None) -> Job:
        payload = payload or {}

        async def handler(ctx):
            return await self.run_source_job(worker_type, payload, ctx)

        return Job(
            name=name or f"{worker_type}-job",
            task_type=worker_type,
            handler=handler,
            timeout_seconds=float(payload.get("timeout_seconds", 60)),
            max_retries=int(payload.get("max_retries", 3)),
            payload=payload,
        )

    async def seed_real_jobs(self) -> None:
        # minimal one-shot real jobs; can be replaced by scheduler/pollers
        await self.engine.submit(self.make_source_job("news_rss", {"url": "https://hnrss.org/frontpage"}, name="news-rss"))
        await self.engine.submit(self.make_source_job("price", {"symbol": "bitcoin", "vs": "usd"}, name="price-btc"))
        await self.engine.submit(self.make_source_job("page_watch", {"url": "https://example.com"}, name="page-watch-example"))


def _normalize_items(worker_type: str, payload: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    if not result.get("ok", True):
        return []
    if worker_type == "news_rss":
        return list(result.get("items", []))
    if worker_type == "price":
        return [
            {
                "title": f"{result.get('symbol')} price",
                "summary": f"{result.get('symbol')} is {result.get('price')} {result.get('vs')} ({result.get('change_24h')}% 24h)",
                "change_24h": result.get("change_24h"),
                "price": result.get("price"),
                "symbol": result.get("symbol"),
            }
        ]
    if worker_type == "page_watch":
        if result.get("changed"):
            return [{"title": f"Page changed: {result.get('url')}", "summary": f"Hash changed to {result.get('hash')}", "url": result.get("url")}]
        return []
    return [result]


def _to_float(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except Exception:
        return None
