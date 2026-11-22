from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class WorkerContext:
    report: Any  # async callable(progress:int, action:str)
    payload: dict[str, Any] = field(default_factory=dict)


class SourceWorker(Protocol):
    type: str

    async def run(self, ctx: WorkerContext) -> dict[str, Any]: ...
