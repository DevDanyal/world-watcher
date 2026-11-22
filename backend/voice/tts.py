from __future__ import annotations

import logging
from typing import AsyncIterator

logger = logging.getLogger(__name__)

# Reasonable default voices; edge-tts supports many languages.
VOICE_MAP = {
    ("en", "female"): "en-US-AriaNeural",
    ("en", "male"): "en-US-GuyNeural",
    ("es", "female"): "es-ES-ElviraNeural",
    ("es", "male"): "es-ES-AlvaroNeural",
    ("fr", "female"): "fr-FR-DeniseNeural",
    ("fr", "male"): "fr-FR-HenriNeural",
    ("de", "female"): "de-DE-KatjaNeural",
    ("de", "male"): "de-DE-ConradNeural",
    ("ar", "female"): "ar-SA-ZariyahNeural",
    ("ar", "male"): "ar-SA-HamedNeural",
    ("ur", "female"): "ur-PK-UzmaNeural",
    ("ur", "male"): "ur-PK-AsadNeural",
    ("hi", "female"): "hi-IN-SwaraNeural",
    ("hi", "male"): "hi-IN-MadhurNeural",
    ("pt", "female"): "pt-BR-FranciscaNeural",
    ("pt", "male"): "pt-BR-AntonioNeural",
    ("zh", "female"): "zh-CN-XiaoxiaoNeural",
    ("zh", "male"): "zh-CN-YunxiNeural",
    ("ja", "female"): "ja-JP-NanamiNeural",
    ("ja", "male"): "ja-JP-KeitaNeural",
}


def pick_voice(language: str, gender: str) -> str:
    lang = (language or "en").lower().split("-")[0]
    g = "male" if gender == "male" else "female"
    if (lang, g) in VOICE_MAP:
        return VOICE_MAP[(lang, g)]
    # try any same-language voice
    for (lang_code, voice_gender), voice in VOICE_MAP.items():
        if lang_code == lang and voice_gender == g:
            return voice
    return VOICE_MAP[("en", g)]


async def synthesize_stream(text: str, language: str, gender: str) -> AsyncIterator[bytes]:
    voice = pick_voice(language, gender)
    try:
        import edge_tts

        communicate = edge_tts.Communicate(text, voice)
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                yield chunk["data"]
    except Exception as exc:  # noqa: BLE001
        logger.exception("TTS failed for voice=%s: %s", voice, exc)
        return
