from __future__ import annotations

from typing import Any

import httpx

from config.settings import settings


class TelegramChannel:
    async def send(self, alert: dict[str, Any]) -> dict[str, Any]:
        token = settings.telegram_bot_token
        chat_id = settings.telegram_chat_id
        if not token or not chat_id:
            return {"ok": False, "error": "telegram not configured"}
        text = (
            f"World Watcher Alert\n"
            f"Rule: {alert.get('rule_name')}\n"
            f"Title: {alert.get('title')}\n"
            f"Importance: {alert.get('importance')}\n"
            f"Reason: {alert.get('reason')}\n"
        )
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json={"chat_id": chat_id, "text": text})
            r.raise_for_status()
            return {"ok": True, "status_code": r.status_code}
