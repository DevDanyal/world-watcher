from __future__ import annotations

from typing import Any


class DashboardChannel:
    def __init__(self, engine):
        self.engine = engine

    async def send(self, alert: dict[str, Any]) -> dict[str, Any]:
        await self.engine._emit({"type": "alert", "alert": alert})  # intentional internal use for real-time broadcast
        await self.engine._emit(
            {
                "type": "event",
                "event": {
                    "ts": alert.get("triggered_at"),
                    "level": "alert",
                    "message": f"ALERT: {alert.get('rule_name')} - {alert.get('title')}",
                    "job_id": None,
                    "worker_id": None,
                },
            }
        )
        return {"ok": True}
