from __future__ import annotations

import asyncio
from typing import Any

from backend.worker_engine.models import Job, JobContext


async def mock_sleep_task(ctx: JobContext) -> dict[str, Any]:
    steps = int(ctx.job.payload.get("steps", 5))
    delay = float(ctx.job.payload.get("delay", 0.2))
    fail_times = int(ctx.job.payload.get("fail_times", 0))
    for i in range(steps):
        if ctx.is_cancelled():
            raise asyncio.CancelledError()
        progress = int(((i + 1) / steps) * 100)
        await ctx.report(progress, f"{ctx.job.name}: step {i + 1}/{steps}")
        await asyncio.sleep(delay)
    if fail_times >= ctx.job.attempt:
        raise RuntimeError(f"intentional failure on attempt {ctx.job.attempt}")
    return {"ok": True, "steps": steps}


def make_mock_job(
    name: str,
    *,
    task_type: str = "mock",
    steps: int = 5,
    delay: float = 0.2,
    fail_times: int = 0,
    timeout_seconds: float = 30.0,
    max_retries: int = 3,
) -> Job:
    return Job(
        name=name,
        task_type=task_type,
        handler=mock_sleep_task,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        payload={"steps": steps, "delay": delay, "fail_times": fail_times},
    )
