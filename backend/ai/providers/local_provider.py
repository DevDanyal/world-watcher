from __future__ import annotations

import json

import httpx

from backend.ai.providers.openai_provider import _fallback, _prompt
from backend.ai.schemas import AnalysisItem, ProviderSignals
from config.settings import settings


class LocalProvider:
    name = "local"

    def __init__(self):
        self.model = settings.local_ai_model
        self.base_url = settings.local_ai_base_url.rstrip("/")

    async def analyze(self, item: AnalysisItem) -> ProviderSignals:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    f"{self.base_url}/chat/completions",
                    json={
                        "model": self.model,
                        "temperature": 0.2,
                        "messages": [
                            {"role": "system", "content": "Return JSON only."},
                            {"role": "user", "content": _prompt(item)},
                        ],
                    },
                )
                r.raise_for_status()
                data = r.json()
                content = data["choices"][0]["message"]["content"]
                start = content.find("{")
                end = content.rfind("}") + 1
                return ProviderSignals.model_validate(json.loads(content[start:end]))
        except Exception:
            return _fallback(item)
