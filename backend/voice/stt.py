from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class STTResult:
    text: str
    language: str


class WhisperSTT:
    def __init__(self, model_size: str = "small"):
        self.model_size = model_size
        self._model = None
        self._lock = asyncio.Lock()

    async def _ensure_model(self):
        if self._model is not None:
            return self._model
        async with self._lock:
            if self._model is not None:
                return self._model

            def load():
                from faster_whisper import WhisperModel

                # cpu + int8 for broad compatibility; adjust if gpu available
                return WhisperModel(self.model_size, device="cpu", compute_type="int8")

            self._model = await asyncio.to_thread(load)
            logger.info("Whisper model loaded: %s", self.model_size)
            return self._model

    async def transcribe_pcm16(self, pcm_bytes: bytes, sample_rate: int = 16000) -> STTResult:
        if not pcm_bytes:
            return STTResult(text="", language="en")
        try:
            model = await self._ensure_model()
            import numpy as np

            audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

            def run():
                segments, info = model.transcribe(audio, beam_size=1, vad_filter=True)
                text = "".join(seg.text for seg in segments).strip()
                lang = getattr(info, "language", None) or "en"
                return STTResult(text=text, language=lang)

            return await asyncio.to_thread(run)
        except Exception as exc:  # noqa: BLE001
            logger.exception("STT failed: %s", exc)
            return STTResult(text="", language="en")
