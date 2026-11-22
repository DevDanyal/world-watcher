import pytest

from backend.ai.schemas import AIAnalysis
from backend.alerts.models import AlertRule
from backend.pipeline import Pipeline
from backend.worker_engine import WorkerEngine


class FakeAI:
    async def analyze(self, item):
        return AIAnalysis(
            summary=f"{item.title}. It matched monitored conditions.",
            importance=8,
            reason="Contains monitored keyword with high impact.",
            provider="fake",
            model="fake-1",
            cached=False,
        )


@pytest.mark.asyncio
async def test_full_pipeline_fake_news_triggers_alert(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "integration.db"))
    monkeypatch.setenv("MOCK_MODE", "true")
    from config import settings as s

    s.get_settings.cache_clear()

    engine = WorkerEngine(max_workers=2)
    pipeline = Pipeline.create(engine)
    pipeline.ai = FakeAI()  # deterministic test, no external AI
    pipeline.alert_repo.create_rule(
        AlertRule(
            id=None,
            name="Keyword X important",
            source_type="news_rss",
            conditions=[{"type": "keyword", "value": "keyword X"}, {"type": "importance_gte", "value": 7}],
            channels={"dashboard": True, "desktop": False, "telegram": False},
            cooldown_seconds=0,
        )
    )

    events = []
    engine.add_listener(lambda msg: events.append(msg))
    await engine.start()

    result = await pipeline.process_item(
        "news_rss",
        {"title": "Breaking: keyword X detected", "summary": "A news item mentions keyword X in market context."},
    )

    await engine.stop()
    await pipeline.close()

    assert result["matches"] == 1
    assert result["dispatched"]
    assert any(m.get("type") == "alert" for m in events)
    history = pipeline.alert_repo.list_history()
    assert len(history) == 1
    assert history[0]["rule_id"] is not None
