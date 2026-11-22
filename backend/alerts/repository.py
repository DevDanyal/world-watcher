from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.alerts.db import get_conn, init_db, row_to_dict
from backend.alerts.models import AlertRule


class AlertRepository:
    def __init__(self):
        init_db()

    def list_rules(self) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute("SELECT * FROM rules ORDER BY id DESC").fetchall()
        return [row_to_dict(r) for r in rows]

    def create_rule(self, rule: AlertRule) -> dict[str, Any]:
        with get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO rules (name, source_type, conditions_json, channels_json, enabled, cooldown_seconds)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    rule.name,
                    rule.source_type,
                    json.dumps(rule.conditions),
                    json.dumps(rule.channels),
                    1 if rule.enabled else 0,
                    rule.cooldown_seconds,
                ),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM rules WHERE id = ?", (cur.lastrowid,)).fetchone()
        return row_to_dict(row)

    def delete_rule(self, rule_id: int) -> bool:
        with get_conn() as conn:
            cur = conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
            conn.commit()
            return cur.rowcount > 0

    def list_history(self, limit: int = 100) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM alert_history ORDER BY id DESC LIMIT ?", (max(1, min(limit, 500)),)
            ).fetchall()
        return [row_to_dict(r) for r in rows]

    def in_cooldown(self, rule_id: int, fingerprint: str, cooldown_seconds: int) -> bool:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=max(0, cooldown_seconds))
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM alert_history
                WHERE rule_id = ? AND event_fingerprint = ? AND triggered_at >= ?
                LIMIT 1
                """,
                (rule_id, fingerprint, cutoff.isoformat()),
            ).fetchone()
        return row is not None

    def add_history(self, record: dict[str, Any]) -> dict[str, Any]:
        with get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO alert_history (
                    rule_id, event_fingerprint, source_type, title, summary, importance, reason,
                    payload_json, delivery_json, triggered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.get("rule_id"),
                    record["event_fingerprint"],
                    record["source_type"],
                    record["title"],
                    record.get("summary", ""),
                    int(record.get("importance", 0)),
                    record.get("reason", ""),
                    json.dumps(record.get("payload", {})),
                    json.dumps(record.get("delivery", {})),
                    record.get("triggered_at", datetime.now(timezone.utc).isoformat()),
                ),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM alert_history WHERE id = ?", (cur.lastrowid,)).fetchone()
        return row_to_dict(row)
