from __future__ import annotations

from backend.ai.cache import AICache
from backend.ai.providers.anthropic_provider import AnthropicProvider
from backend.ai.providers.local_provider import LocalProvider
from backend.ai.providers.openai_provider import OpenAIProvider
from backend.ai.schemas import AIAnalysis, AnalysisItem
from backend.ai.scoring import score_importance
from config.settings import settings


class AIService:
    def __init__(self):
        self.cache = AICache()
        provider = settings.ai_provider
        if provider == "anthropic":
            self.provider = AnthropicProvider()
        elif provider == "local":
            self.provider = LocalProvider()
        else:
            self.provider = OpenAIProvider()

    async def analyze(self, item: AnalysisItem) -> AIAnalysis:
        key = self.cache.key_for(
            "v1", self.provider.name, self.provider.model, item.source_type, item.title, item.content
        )
        cached = self.cache.get(key)
        if cached:
            return AIAnalysis.model_validate({**cached, "cached": True})

        signals = await self.provider.analyze(item)
        importance = score_importance(signals)  # plain Python
        analysis = AIAnalysis(
            summary=signals.summary,
            importance=importance,
            reason=signals.reason,
            provider=self.provider.name,
            model=self.provider.model,
            cached=False,
        )
        self.cache.set(key, analysis.model_dump())
        return analysis
