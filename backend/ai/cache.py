from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from config.settings import settings


class AICache:
    def __init__(self, path: Path | None = None):
        self.path = path or (settings.db_path.parent / "ai_cache.sqlite3")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_cache (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    @staticmethod
    def key_for(*parts: Any) -> str:
        raw = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT value_json FROM ai_cache WHERE key = ?", (key,)).fetchone()
        if not row:
            return None
        return json.loads(row["value_json"])

    def set(self, key: str, value: dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ai_cache (key, value_json) VALUES (?, ?)",
                (key, json.dumps(value, ensure_ascii=False)),
            )
            conn.commit()
