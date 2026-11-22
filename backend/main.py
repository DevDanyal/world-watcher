from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.alerts.api import router as alerts_router
from backend.api.routes import router as api_router
from backend.api.ws import router as ws_router
from backend.assistant.api import router as assistant_router
from backend.auth import router as auth_router
from backend.middleware import AuthMiddleware, install_log_redaction
from backend.pipeline import Pipeline
from backend.security import init_auth_db
from backend.voice.api import router as voice_router
from backend.worker_engine import WorkerEngine, make_mock_job
from config.settings import settings

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
install_log_redaction()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_auth_db()
    engine = WorkerEngine(max_workers=settings.worker_max_concurrency)
    pipeline = Pipeline.create(engine)
    app.state.engine = engine
    app.state.pipeline = pipeline
    await engine.start()

    async def seed():
        await asyncio.sleep(0.2)
        if settings.mock_mode:
            for i in range(8):
                await engine.submit(make_mock_job(f"mock-{i+1}", steps=8, delay=0.4, fail_times=1 if i == 3 else 0))
        else:
            await pipeline.seed_real_jobs()

    seed_task = asyncio.create_task(seed())
    try:
        yield
    finally:
        seed_task.cancel()
        await pipeline.close()
        await engine.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
allowed_origins = [o for o in settings.cors_origin_list if o] or ["http://localhost:5173", "http://127.0.0.1:5173"]
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(api_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")
app.include_router(assistant_router, prefix="/api")
app.include_router(voice_router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "app": settings.app_name,
        "mock_mode": settings.mock_mode,
        "cors_origins": settings.cors_origin_list,
    }
