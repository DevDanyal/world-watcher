from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.alerts.dispatcher import AlertDispatcher
from backend.alerts.engine import AlertEngine
from backend.alerts.models import AlertEvent, AlertRule
from backend.alerts.repository import AlertRepository

router = APIRouter(prefix="/alerts", tags=["alerts"])
repo = AlertRepository()


class RuleIn(BaseModel):
    name: str
    source_type: str = "*"
    conditions: list[dict] = Field(default_factory=list)
    channels: dict[str, bool] = Field(default_factory=lambda: {"dashboard": True, "desktop": False, "telegram": False})
    enabled: bool = True
    cooldown_seconds: int = 300


@router.get("/rules")
async def list_rules():
    return repo.list_rules()


@router.post("/rules")
async def create_rule(rule: RuleIn):
    return repo.create_rule(AlertRule(id=None, **rule.model_dump()))


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: int):
    ok = repo.delete_rule(rule_id)
    if not ok:
        raise HTTPException(404, "rule not found")
    return {"ok": True}


@router.get("/history")
async def history(limit: int = 100):
    return repo.list_history(limit)


@router.post("/test")
async def test_alert(request: Request):
    engine = request.app.state.engine
    alert_engine = AlertEngine(repo)
    dispatcher = AlertDispatcher(repo, engine)
    event = AlertEvent(source_type="news_rss", title="Test alert", content="keyword X mentioned", importance=8, reason="manual test")
    matches = alert_engine.evaluate(event)
    dispatched = []
    for m in matches:
        dispatched.append(await dispatcher.dispatch(m))
    return {"matches": len(matches), "dispatched": dispatched}
