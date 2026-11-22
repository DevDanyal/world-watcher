from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ToolDef:
    name: str
    description: str
    schema: dict[str, Any]
    destructive: bool = False
    costs_money: bool = False
    handler: Callable[..., Any] | None = None


def default_tools() -> list[dict[str, Any]]:
    # OpenAI-style tool schema for LLMs; execution happens in runner.
    return [
        {
            "type": "function",
            "function": {
                "name": "start_workers",
                "description": "Start N workers of a type (news_rss, price, page_watch, mock)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "worker_type": {"type": "string"},
                        "count": {"type": "integer", "minimum": 1, "maximum": 20},
                    },
                    "required": ["worker_type", "count"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "stop_all_workers",
                "description": "Stop all running workers/engine jobs",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "show_alerts",
                "description": "Show recent alerts",
                "parameters": {
                    "type": "object",
                    "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "what_happened_today",
                "description": "Summarize today's system events and alerts",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]
