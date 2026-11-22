import asyncio

import pytest

from backend.worker_engine import Job, WorkerEngine, WorkerStatus, make_mock_job


@pytest.mark.asyncio
async def test_worker_runs_job_and_reports_progress():
    engine = WorkerEngine(max_workers=2)
    updates = []
    engine.add_listener(lambda msg: updates.append(msg))
    await engine.start()
    job = make_mock_job("mock-1", steps=4, delay=0.01)
    await engine.submit(job)
    await asyncio.sleep(0.2)
    await engine.stop()

    worker_updates = [u["worker"] for u in updates if u["type"] == "worker_update"]
    assert worker_updates
    assert any(u["progress"] > 0 for u in worker_updates)
    assert any(u["status"] == "done" for u in worker_updates)
    assert engine.stats["done"] == 1


@pytest.mark.asyncio
async def test_retry_then_success():
    engine = WorkerEngine(max_workers=1)
    await engine.start()
    job = make_mock_job("flaky", steps=1, delay=0.01, fail_times=2, max_retries=3)
    await engine.submit(job)
    await asyncio.sleep(0.3)
    await engine.stop()
    assert engine.stats["done"] == 1
    assert engine.stats["errors"] == 0


@pytest.mark.asyncio
async def test_retry_exhaustion_marks_error():
    engine = WorkerEngine(max_workers=1)
    await engine.start()
    job = make_mock_job("always-fail", steps=1, delay=0.01, fail_times=10, max_retries=3)
    await engine.submit(job)
    await asyncio.sleep(0.5)
    await engine.stop()
    assert engine.stats["errors"] == 1


@pytest.mark.asyncio
async def test_timeout_is_retried_and_errors():
    engine = WorkerEngine(max_workers=1)

    async def slow(ctx):
        await ctx.report(10, "slow")
        await asyncio.sleep(0.2)
        return "ok"

    await engine.start()
    await engine.submit(Job(name="slow", task_type="mock", handler=slow, timeout_seconds=0.05, max_retries=2))
    await asyncio.sleep(0.6)
    await engine.stop()
    assert engine.stats["errors"] == 1


@pytest.mark.asyncio
async def test_concurrency_never_exceeds_20():
    engine = WorkerEngine(max_workers=20)
    running = 0
    peak = 0
    lock = asyncio.Lock()

    async def handler(ctx):
        nonlocal running, peak
        async with lock:
            running += 1
            peak = max(peak, running)
        await ctx.report(50, "working")
        await asyncio.sleep(0.05)
        async with lock:
            running -= 1
        return True

    await engine.start()
    for i in range(40):
        await engine.submit(Job(name=f"job-{i}", task_type="mock", handler=handler, timeout_seconds=1, max_retries=0))
    await asyncio.sleep(0.5)
    await engine.stop()
    assert peak <= 20
    assert engine.stats["done"] == 40


@pytest.mark.asyncio
async def test_worker_state_fields():
    engine = WorkerEngine(max_workers=3)
    snap = engine.snapshot()
    assert len(snap["workers"]) == 3
    w = snap["workers"][0]
    assert {"id", "name", "task_type", "status", "current_action", "progress"} <= w.keys()
    assert w["status"] == WorkerStatus.IDLE.value
