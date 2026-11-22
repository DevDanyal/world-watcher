from __future__ import annotations

from backend.ai.schemas import ProviderSignals

WEIGHTS = {"low": 1, "medium": 2, "high": 3}


def score_importance(signals: ProviderSignals) -> int:
    # All numeric calculation done in plain Python (never by LLM).
    urgency = WEIGHTS[signals.urgency]
    impact = WEIGHTS[signals.impact]
    novelty = WEIGHTS[signals.novelty]
    raw = (impact * 0.45) + (urgency * 0.35) + (novelty * 0.20)  # 1..3
    scaled = 1 + ((raw - 1) / 2) * 9  # map 1..3 -> 1..10
    return max(1, min(10, int(round(scaled))))
