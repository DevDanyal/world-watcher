from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AnalysisItem(BaseModel):
    source_type: str
    title: str
    content: str
    metadata: dict = Field(default_factory=dict)


class ProviderSignals(BaseModel):
    summary: str
    reason: str
    urgency: Literal["low", "medium", "high"]
    impact: Literal["low", "medium", "high"]
    novelty: Literal["low", "medium", "high"]

    @field_validator("summary")
    @classmethod
    def two_sentences(cls, v: str) -> str:
        text = " ".join(v.strip().split())
        # naive sentence split; good enough for validation guard
        sentences = [s.strip() for s in text.replace("?", ".").replace("!", ".").split(".") if s.strip()]
        if len(sentences) < 2:
            text = text.rstrip(".") + ". Additional context is limited."
        return text

    @field_validator("reason")
    @classmethod
    def one_line(cls, v: str) -> str:
        return " ".join(v.strip().splitlines()).strip()[:180]


class AIAnalysis(BaseModel):
    summary: str
    importance: int = Field(ge=1, le=10)
    reason: str
    provider: str
    model: str
    cached: bool = False
