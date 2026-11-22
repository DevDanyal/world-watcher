from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "world-watcher"
    app_env: str = "development"
    log_level: str = "INFO"
    secret_key: str = "change-me-on-first-run"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    sqlite_path: str = "data/world_watcher.db"

    ai_provider: Literal["openai", "anthropic", "local"] = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-latest"
    local_ai_base_url: str = "http://localhost:11434/v1"
    local_ai_model: str = "llama3.1"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    whisper_model: str = "small"
    tts_provider: str = "edge-tts"
    default_voice_gender: Literal["male", "female"] = "female"
    voice_vad_threshold: float = 0.02
    voice_silence_ms: int = 700
    voice_max_utterance_s: int = 20

    user_agent: str = "world-watcher/0.1 (+https://localhost)"
    rate_limit_per_host_per_sec: float = 1.0
    worker_max_concurrency: int = Field(default=20, ge=1, le=20)
    worker_max_retries: int = Field(default=3, ge=0)
    worker_job_timeout_seconds: int = Field(default=60, ge=1)

    mock_mode: bool = True
    news_rss_urls: str = "https://hnrss.org/frontpage"
    price_symbols: str = "bitcoin:usd"
    watch_urls: str = "https://example.com"
    poll_interval_seconds: int = 60

    @property
    def db_path(self) -> Path:
        path = BASE_DIR / self.sqlite_path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
