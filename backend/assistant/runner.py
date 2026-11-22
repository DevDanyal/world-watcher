from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.alerts.repository import AlertRepository
from backend.worker_engine import make_mock_job

CONFIRM_REQUIRED = {"start_workers", "stop_all_workers"}


class AssistantRunner:
    def __init__(self, app):
        self.app = app
        self.repo = AlertRepository()
        self.pending: dict[str, dict[str, Any]] = {}

    async def execute(self, tool: str, args: dict[str, Any], confirmed: bool = False) -> dict[str, Any]:
        if tool in CONFIRM_REQUIRED and not confirmed:
            action_id = f"pending-{len(self.pending)+1}-{int(datetime.now().timestamp())}"
            self.pending[action_id] = {"tool": tool, "args": args, "created_at": datetime.now(timezone.utc).isoformat()}
            return {
                "ok": False,
                "requires_confirmation": True,
                "action_id": action_id,
                "message": f"Confirm action '{tool}' with args {args}.",
            }

        if tool == "start_workers":
            return await self._start_workers(**args)
        if tool == "stop_all_workers":
            return await self._stop_all()
        if tool == "show_alerts":
            limit = int(args.get("limit", 20))
            return {"ok": True, "alerts": self.repo.list_history(limit)}
        if tool == "what_happened_today":
            return {"ok": True, "summary": self._daily_summary()}
        return {"ok": False, "error": f"unknown tool: {tool}"}

    async def confirm(self, action_id: str, yes: bool) -> dict[str, Any]:
        action = self.pending.pop(action_id, None)
        if not action:
            return {"ok": False, "error": "pending action not found"}
        if not yes:
            return {"ok": True, "cancelled": True, "action_id": action_id}
        return await self.execute(action["tool"], action["args"], confirmed=True)

    async def _start_workers(self, worker_type: str = "mock", count: int = 1) -> dict[str, Any]:
        engine = self.app.state.engine
        count = max(1, min(int(count), 20))
        for i in range(count):
            # Real plugin dispatch can be wired here; mock keeps command functional now.
            await engine.submit(make_mock_job(f"{worker_type}-{i+1}", task_type=worker_type, steps=6, delay=0.3))
        return {"ok": True, "started": count, "worker_type": worker_type}

    async def _stop_all(self) -> dict[str, Any]:
        engine = self.app.state.engine
        await engine.stop()
        await engine.start()
        return {"ok": True, "stopped": "all", "restarted_engine": True}

    def _daily_summary(self) -> dict[str, Any]:
        history = self.repo.list_history(200)
        today = datetime.now(timezone.utc).date().isoformat()
        todays = [h for h in history if str(h.get("triggered_at", ""))[:10] == today]
        by_source: dict[str, int] = {}
        for h in todays:
            s = h.get("source_type", "unknown")
            by_source[s] = by_source.get(s, 0) + 1
        return {
            "date": today,
            "alert_count": len(todays),
            "alerts_by_source": by_source,
            "recent": todays[:5],
        }
