from __future__ import annotations

from fastapi import APIRouter, Request

from backend.worker_engine import make_mock_job
from config.settings import settings

router = APIRouter()


@router.get("/settings")
async def get_settings():
    return {
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "mock_mode": settings.mock_mode,
        "ai_provider": settings.ai_provider,
        "openai_model": settings.openai_model,
        "anthropic_model": settings.anthropic_model,
        "local_ai_model": settings.local_ai_model,
        "tts_provider": settings.tts_provider,
        "default_voice_gender": settings.default_voice_gender,
        "worker_max_concurrency": settings.worker_max_concurrency,
        "worker_max_retries": settings.worker_max_retries,
        "worker_job_timeout_seconds": settings.worker_job_timeout_seconds,
        "telegram_configured": bool(settings.telegram_bot_token and settings.telegram_chat_id),
        "openai_configured": bool(settings.openai_api_key),
        "anthropic_configured": bool(settings.anthropic_api_key),
        "cors_origins": settings.cors_origin_list,
    }


@router.get("/workers")
async def get_workers(request: Request):
    engine = request.app.state.engine
    return engine.snapshot()


@router.post("/workers/mock")
async def enqueue_mock(request: Request, count: int = 1):
    engine = request.app.state.engine
    for i in range(max(1, min(count, 50))):
        await engine.submit(make_mock_job(f"mock-api-{i+1}", steps=6, delay=0.3))
    return {"queued": count}


@router.post("/workers/real")
async def enqueue_real(request: Request, worker_type: str, payload: dict | None = None):
    pipeline = request.app.state.pipeline
    job = pipeline.make_source_job(worker_type, payload or {})
    await request.app.state.engine.submit(job)
    return {"queued": 1, "worker_type": worker_type, "mock_mode": settings.mock_mode}


@router.get("/stats")
async def stats(request: Request):
    return request.app.state.engine.stats
