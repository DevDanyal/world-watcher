from __future__ import annotations

from typing import Protocol

from backend.ai.schemas import AnalysisItem, ProviderSignals


class AIProvider(Protocol):
    name: str
    model: str

    async def analyze(self, item: AnalysisItem) -> ProviderSignals: ...
