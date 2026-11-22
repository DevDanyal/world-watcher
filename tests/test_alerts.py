from backend.alerts.engine import AlertEngine
from backend.alerts.models import AlertEvent
from backend.alerts.repository import AlertRepository


def test_alert_rule_matching(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setenv("SQLITE_PATH", str(db))
    from config import settings as s

    s.get_settings.cache_clear()
    s.settings.sqlite_path = str(db)
    repo = AlertRepository()
    repo.create_rule(
        __import__("backend.alerts.models", fromlist=["AlertRule"]).AlertRule(
            id=None,
            name="drop",
            source_type="price",
            conditions=[{"type": "price_change", "direction": "drop", "percent_gte": 5}],
            channels={"dashboard": True, "desktop": False, "telegram": False},
        )
    )
    engine = AlertEngine(repo)
    matches = engine.evaluate(AlertEvent(source_type="price", title="BTC", content="down", price_change_percent=-6.2))
    assert len(matches) == 1
    assert matches[0]["rule_name"] == "drop"
