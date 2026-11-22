from __future__ import annotations

import hashlib
import json
from typing import Any

from backend.alerts.models import AlertEvent
from backend.alerts.repository import AlertRepository


def _fingerprint(event: AlertEvent) -> str:
    base = json.dumps(
        {
            "source_type": event.source_type,
            "title": event.title,
            "content": event.content[:500],
            "price_change_percent": event.price_change_percent,
        },
        sort_keys=True,
    )
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


class AlertEngine:
    def __init__(self, repo: AlertRepository):
        self.repo = repo

    def evaluate(self, event: AlertEvent) -> list[dict[str, Any]]:
        matches = []
        for rule in self.repo.list_rules():
            if not rule.get("enabled"):
                continue
            if rule.get("source_type") not in (event.source_type, "*"):
                continue
            if self._matches(rule.get("conditions_json") or rule.get("conditions") or [], event):
                fp = _fingerprint(event)
                rule_id = int(rule["id"])
                cooldown = int(rule.get("cooldown_seconds", 300))
                if self.repo.in_cooldown(rule_id, fp, cooldown):
                    continue
                record = {
                    "rule_id": rule_id,
                    "rule_name": rule.get("name"),
                    "event_fingerprint": fp,
                    "source_type": event.source_type,
                    "title": event.title,
                    "summary": event.content[:280],
                    "importance": event.importance,
                    "reason": event.reason,
                    "payload": event.to_dict(),
                    "triggered_at": event.triggered_at,
                    "channels": rule.get("channels_json") or rule.get("channels") or {},
                }
                matches.append(record)
        return matches

    def _matches(self, conditions: list[dict[str, Any]], event: AlertEvent) -> bool:
        if not conditions:
            return False
        for cond in conditions:
            ctype = cond.get("type")
            if ctype == "price_change":
                pct = event.price_change_percent
                if pct is None:
                    return False
                direction = cond.get("direction", "drop")
                threshold = float(cond.get("percent_gte", 0))
                if direction == "drop" and not (pct <= -abs(threshold)):
                    return False
                if direction == "rise" and not (pct >= abs(threshold)):
                    return False
            elif ctype == "keyword":
                value = str(cond.get("value", "")).strip().lower()
                hay = f"{event.title}\n{event.content}".lower()
                if not value or value not in hay:
                    return False
            elif ctype == "importance_gte":
                if int(event.importance) < int(cond.get("value", 0)):
                    return False
            else:
                return False
        return True
