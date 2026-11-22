from __future__ import annotations

import json

import httpx

from backend.ai.schemas import AnalysisItem, ProviderSignals
from config.settings import settings


class OpenAIProvider:
    name = "openai"

    def __init__(self):
        self.model = settings.openai_model
        self.api_key = settings.openai_api_key

    async def analyze(self, item: AnalysisItem) -> ProviderSignals:
        if not self.api_key:
            return _fallback(item)
        prompt = _prompt(item)
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": "Return JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            return ProviderSignals.model_validate(json.loads(content))


def _prompt(item: AnalysisItem) -> str:
    return (
        "Analyze this monitoring item. Return JSON with keys: "
        "summary (exactly 2 sentences), reason (one line), urgency (low|medium|high), "
        "impact (low|medium|high), novelty (low|medium|high). Do not calculate numeric scores.\n\n"
        f"Source: {item.source_type}\nTitle: {item.title}\nContent: {item.content}\nMetadata: {item.metadata}"
    )


def _fallback(item: AnalysisItem) -> ProviderSignals:
    return ProviderSignals(
        summary=f"{item.title}. Monitoring signal captured for review.",
        reason="Fallback used because AI provider key is missing.",
        urgency="medium",
        impact="medium",
        novelty="low",
    )
