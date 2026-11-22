from __future__ import annotations

import json

import httpx

from backend.ai.providers.openai_provider import _fallback, _prompt
from backend.ai.schemas import AnalysisItem, ProviderSignals
from config.settings import settings


class AnthropicProvider:
    name = "anthropic"

    def __init__(self):
        self.model = settings.anthropic_model
        self.api_key = settings.anthropic_api_key

    async def analyze(self, item: AnalysisItem) -> ProviderSignals:
        if not self.api_key:
            return _fallback(item)
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 300,
                    "temperature": 0.2,
                    "messages": [{"role": "user", "content": _prompt(item)}],
                },
            )
            r.raise_for_status()
            data = r.json()
            content = data["content"][0]["text"]
            # best-effort JSON extraction
            start = content.find("{")
            end = content.rfind("}") + 1
            return ProviderSignals.model_validate(json.loads(content[start:end]))
