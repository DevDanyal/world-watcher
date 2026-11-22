from __future__ import annotations

import asyncio
import inspect
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from backend.worker_engine.models import Job, JobContext, JobResult, WorkerState, WorkerStatus

logger = logging.getLogger(__name__)

EventListener = Callable[[dict[str, Any]], Awaitable[None] | None]


class WorkerEngine:
    def __init__(self, max_workers: int = 20):
        self.max_workers = max(1, min(max_workers, 20))
        self.queue: asyncio.Queue[Job | None] = asyncio.Queue()
        self.workers: list[WorkerState] = [
            WorkerState(id=i + 1, name=f"worker-{i + 1}") for i in range(self.max_workers)
        ]
        self._tasks: list[asyncio.Task[None]] = []
        self._listeners: list[EventListener] = []
        self._events: deque[dict[str, Any]] = deque(maxlen=300)
        self._running = False
        self._shutdown = asyncio.Event()
        self.stats = {"running": 0, "done": 0, "errors": 0, "queued": 0}

    def add_listener(self, listener: EventListener) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: EventListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def snapshot(self) -> dict[str, Any]:
        return {
            "type": "snapshot",
            "workers": [w.to_dict() for w in self.workers],
            "stats": dict(self.stats),
            "events": list(self._events),
        }

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._shutdown.clear()
        self._tasks = [asyncio.create_task(self._worker_loop(w), name=w.name) for w in self.workers]
        await self._emit({"type": "event", "event": self._event("system", "engine started")})

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._shutdown.set()
        for _ in self._tasks:
            await self.queue.put(None)
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self.stats["queued"] = self.queue.qsize()
        await self._emit_stats()
        await self._emit({"type": "event", "event": self._event("system", "engine stopped")})

    async def submit(self, job: Job) -> None:
        await self.queue.put(job)
        self.stats["queued"] = self.queue.qsize()
        await self._emit_stats()
        await self._emit(
            {
                "type": "event",
                "event": self._event("info", f"queued {job.name} ({job.task_type})", job=job),
            }
        )

    async def _worker_loop(self, worker: WorkerState) -> None:
        while True:
            job = await self.queue.get()
            self.stats["queued"] = self.queue.qsize()
            try:
                if job is None:
                    return
                await self._run_job(worker, job)
            finally:
                self.queue.task_done()
                await self._emit_stats()

    async def _run_job(self, worker: WorkerState, job: Job) -> JobResult:
        last_error: str | None = None
        attempts_allowed = job.max_retries + 1
        for attempt in range(1, attempts_allowed + 1):
            job.attempt = attempt
            worker.task_type = job.task_type
            worker.status = WorkerStatus.RUNNING
            worker.current_action = f"starting attempt {attempt}/{attempts_allowed}"
            worker.progress = 0
            self.stats["running"] += 1
            await self._emit_worker(worker)
            await self._emit(
                {
                    "type": "event",
                    "event": self._event(
                        "info", f"{worker.name} started {job.name} attempt {attempt}", job, worker
                    ),
                }
            )

            async def report(progress: int, action: str) -> None:
                worker.progress = max(0, min(100, int(progress)))
                worker.current_action = str(action)
                await self._emit_worker(worker)

            ctx = JobContext(job=job, worker=worker, report=report, is_cancelled=self._shutdown.is_set)
            try:
                result = await asyncio.wait_for(job.handler(ctx), timeout=job.timeout_seconds)
                worker.status = WorkerStatus.DONE
                worker.progress = 100
                worker.current_action = "done"
                self.stats["running"] = max(0, self.stats["running"] - 1)
                self.stats["done"] += 1
                await self._emit_worker(worker)
                await self._emit(
                    {
                        "type": "event",
                        "event": self._event(
                            "success", f"{job.name} completed on attempt {attempt}", job, worker
                        ),
                    }
                )
                self._reset_worker(worker)
                return JobResult(job.id, job.name, job.task_type, WorkerStatus.DONE, attempt, result=result)
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"
                self.stats["running"] = max(0, self.stats["running"] - 1)
                worker.status = WorkerStatus.ERROR
                worker.current_action = f"error: {last_error}"
                worker.progress = max(worker.progress, 0)
                await self._emit_worker(worker)
                await self._emit(
                    {
                        "type": "event",
                        "event": self._event(
                            "error",
                            f"{job.name} failed attempt {attempt}/{attempts_allowed}: {last_error}",
                            job,
                            worker,
                        ),
                    }
                )
                if attempt < attempts_allowed and not self._shutdown.is_set():
                    worker.status = WorkerStatus.IDLE
                    worker.current_action = f"retrying in backoff ({attempt}/{job.max_retries})"
                    worker.progress = 0
                    await self._emit_worker(worker)
                    await asyncio.sleep(min(0.05 * attempt, 0.2))

        self.stats["errors"] += 1
        self._reset_worker(worker, final_status=WorkerStatus.ERROR, action=f"failed: {last_error}")
        await self._emit_worker(worker)
        return JobResult(
            job.id, job.name, job.task_type, WorkerStatus.ERROR, attempts_allowed, error=last_error
        )

    def _reset_worker(
        self, worker: WorkerState, final_status: WorkerStatus = WorkerStatus.IDLE, action: str = "idle"
    ) -> None:
        worker.status = WorkerStatus.IDLE
        worker.task_type = None
        worker.current_action = action if final_status == WorkerStatus.ERROR else "idle"
        worker.progress = 0

    async def _emit_worker(self, worker: WorkerState) -> None:
        await self._emit({"type": "worker_update", "worker": worker.to_dict()})
        await self._emit_stats()

    async def _emit_stats(self) -> None:
        self.stats["queued"] = self.queue.qsize()
        await self._emit({"type": "stats", "stats": dict(self.stats)})

    async def _emit(self, message: dict[str, Any]) -> None:
        if message.get("type") == "event" and "event" in message:
            self._events.append(message["event"])
        for listener in list(self._listeners):
            try:
                result = listener(message)
                if inspect.isawaitable(result):
                    await result
            except Exception:  # noqa: BLE001
                logger.exception("event listener failed")

    def _event(self, level: str, message: str, job: Job | None = None, worker: WorkerState | None = None) -> dict[str, Any]:
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
            "job_id": job.id if job else None,
            "worker_id": worker.id if worker else None,
        }
