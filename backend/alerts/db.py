from __future__ import annotations

import json
import sqlite3
from typing import Any

from config.settings import settings


def get_conn() -> sqlite3.Connection:
    db_path = settings.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                conditions_json TEXT NOT NULL,
                channels_json TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                cooldown_seconds INTEGER NOT NULL DEFAULT 300,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER,
                event_fingerprint TEXT NOT NULL,
                source_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                importance INTEGER NOT NULL,
                reason TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                delivery_json TEXT NOT NULL,
                triggered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_alert_history_triggered_at ON alert_history(triggered_at);
            CREATE INDEX IF NOT EXISTS idx_alert_history_rule_fp ON alert_history(rule_id, event_fingerprint);
            """
        )
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    for k in ("conditions_json", "channels_json", "payload_json", "delivery_json"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except Exception:
                pass
    return d
