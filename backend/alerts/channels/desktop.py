from __future__ import annotations

from typing import Any


class DesktopChannel:
    async def send(self, alert: dict[str, Any]) -> dict[str, Any]:
        try:
            from desktop_notifier import DesktopNotifier

            notifier = DesktopNotifier(app_name="World Watcher")
            await notifier.send(
                title=f"World Watcher: {alert.get('rule_name', 'Alert')}",
                message=f"{alert.get('title', '')}\n{alert.get('reason', '')}".strip(),
            )
            return {"ok": True}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
