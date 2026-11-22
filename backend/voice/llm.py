from __future__ import annotations

import logging
from typing import AsyncIterator

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)

SYSTEM_TEMPLATE = (
    "You are World Watcher, a real-time monitoring assistant. "
    "Reply in the same language as the user. The user's detected language code is: {language}. "
    "Be concise, clear, and helpful. If the user asks for system actions, explain what action is needed."
)


async def stream_reply(text: str, language: str) -> AsyncIterator[str]:
    prompt = SYSTEM_TEMPLATE.format(language=language)
    provider = settings.ai_provider
    try:
        if provider == "anthropic" and settings.anthropic_api_key:
            async for chunk in _stream_anthropic(prompt, text):
                yield chunk
            return
        if provider == "local":
            async for chunk in _stream_openai_compat(settings.local_ai_base_url, settings.local_ai_model, "", prompt, text):
                yield chunk
            return
        if settings.openai_api_key:
            async for chunk in _stream_openai_compat("https://api.openai.com/v1", settings.openai_model, settings.openai_api_key, prompt, text):
                yield chunk
            return
    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM stream failed: %s", exc)

    # Fallback: deterministic, still language-aware prompt not possible without model; keep simple.
    yield f"I heard you: {text}"


async def _stream_openai_compat(base_url: str, model: str, api_key: str, system: str, user: str) -> AsyncIterator[str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "stream": True,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.4,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    import json

                    obj = json.loads(data)
                    delta = obj["choices"][0]["delta"].get("content")
                    if delta:
                        yield delta
                except Exception:
                    continue


async def _stream_anthropic(system: str, user: str) -> AsyncIterator[str]:
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": settings.anthropic_model,
        "max_tokens": 500,
        "system": system,
        "stream": True,
        "messages": [{"role": "user", "content": user}],
    }
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                try:
                    import json

                    obj = json.loads(data)
                    if obj.get("type") == "content_block_delta":
                        delta = obj.get("delta", {}).get("text")
                        if delta:
                            yield delta
                except Exception:
                    continue
