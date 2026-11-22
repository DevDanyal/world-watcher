from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable


class WorkerStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class WorkerState:
    id: int
    name: str
    task_type: str | None = None
    status: WorkerStatus = WorkerStatus.IDLE
    current_action: str = "idle"
    progress: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "task_type": self.task_type,
            "status": self.status.value,
            "current_action": self.current_action,
            "progress": self.progress,
        }


ProgressReporter = Callable[[int, str], Awaitable[None]]
JobHandler = Callable[["JobContext"], Awaitable[Any]]


@dataclass
class JobContext:
    job: "Job"
    worker: WorkerState
    report: ProgressReporter
    is_cancelled: Callable[[], bool]


@dataclass
class Job:
    name: str
    task_type: str
    handler: JobHandler
    timeout_seconds: float = 60.0
    max_retries: int = 3
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    attempt: int = 0


@dataclass
class JobResult:
    job_id: str
    name: str
    task_type: str
    status: WorkerStatus
    attempts: int
    result: Any = None
    error: str | None = None
