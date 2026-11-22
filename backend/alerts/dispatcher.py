from __future__ import annotations

import logging
from typing import Any

from backend.alerts.channels.dashboard import DashboardChannel
from backend.alerts.channels.desktop import DesktopChannel
from backend.alerts.channels.telegram import TelegramChannel
from backend.alerts.repository import AlertRepository

logger = logging.getLogger(__name__)


class AlertDispatcher:
    def __init__(self, repo: AlertRepository, engine):
        self.repo = repo
        self.engine = engine
        self.dashboard = DashboardChannel(engine)
        self.desktop = DesktopChannel()
        self.telegram = TelegramChannel()

    async def dispatch(self, alert: dict[str, Any]) -> dict[str, Any]:
        channels = alert.get("channels") or {}
        delivery: dict[str, Any] = {}
        if channels.get("dashboard", True):
            delivery["dashboard"] = await self.dashboard.send(alert)
        if channels.get("desktop"):
            try:
                delivery["desktop"] = await self.desktop.send(alert)
            except Exception as exc:  # noqa: BLE001
                logger.warning("desktop alert failed: %s", exc)
                delivery["desktop"] = {"ok": False, "error": str(exc)}
        if channels.get("telegram"):
            try:
                delivery["telegram"] = await self.telegram.send(alert)
            except Exception as exc:  # noqa: BLE001
                logger.warning("telegram alert failed: %s", exc)
                delivery["telegram"] = {"ok": False, "error": str(exc)}
        alert["delivery"] = delivery
        saved = self.repo.add_history(alert)
        return saved
