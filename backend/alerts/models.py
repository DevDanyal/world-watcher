from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

ConditionType = Literal["price_change", "keyword", "importance_gte"]


@dataclass
class AlertRule:
    id: int | None
    name: str
    source_type: str
    conditions: list[dict[str, Any]]
    channels: dict[str, bool] = field(default_factory=lambda: {"dashboard": True, "desktop": False, "telegram": False})
    enabled: bool = True
    cooldown_seconds: int = 300


@dataclass
class AlertEvent:
    source_type: str
    title: str
    content: str
    importance: int = 0
    reason: str = ""
    price_change_percent: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    triggered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "title": self.title,
            "content": self.content,
            "importance": self.importance,
            "reason": self.reason,
            "price_change_percent": self.price_change_percent,
            "metadata": self.metadata,
            "triggered_at": self.triggered_at,
        }
