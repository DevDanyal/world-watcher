from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass, field

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.assistant.runner import AssistantRunner
from backend.security import SESSION_COOKIE, get_session
from backend.voice.llm import stream_reply
from backend.voice.stt import WhisperSTT
from backend.voice.tts import synthesize_stream
from config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@dataclass
class VoiceSession:
    ws: WebSocket
    runner: AssistantRunner
    stt: WhisperSTT
    gender: str = settings.default_voice_gender
    language: str = "en"
    audio_buffer: bytearray = field(default_factory=bytearray)
    speaking: bool = False
    last_voice_ts: float = field(default_factory=time.monotonic)
    utterance_start: float | None = None
    current_task: asyncio.Task | None = None
    interrupted: bool = False

    async def send(self, msg: dict):
        await self.ws.send_text(json.dumps(msg))

    def cancel_current(self):
        self.interrupted = True
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()


@router.websocket("/ws/voice")
async def voice_ws(websocket: WebSocket):
    token = websocket.cookies.get(SESSION_COOKIE)
    if not get_session(token):
        await websocket.close(code=4401)
        return
    await websocket.accept()

    runner = getattr(websocket.app.state, "assistant_runner", None)
    if runner is None:
        runner = AssistantRunner(websocket.app)
        websocket.app.state.assistant_runner = runner
    stt = getattr(websocket.app.state, "voice_stt", None)
    if stt is None:
        stt = WhisperSTT(settings.whisper_model)
        websocket.app.state.voice_stt = stt

    session = VoiceSession(ws=websocket, runner=runner, stt=stt)
    await session.send({"type": "ready", "message": "voice ready", "gender": session.gender})

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            mtype = msg.get("type")
            if mtype == "audio_chunk":
                await handle_audio_chunk(session, msg)
            elif mtype == "interrupt":
                session.cancel_current()
                await session.send({"type": "interrupted"})
            elif mtype == "set_voice":
                gender = msg.get("gender")
                if gender in ("male", "female"):
                    session.gender = gender
                    await session.send({"type": "voice_setting", "gender": gender})
            elif mtype == "command":
                # text fallback
                await schedule_utterance(session, msg.get("text", ""), session.language)
            elif mtype == "confirm":
                result = await session.runner.confirm(msg.get("action_id", ""), bool(msg.get("yes")))
                await session.send({"type": "confirm_result", "result": result})
            else:
                await session.send({"type": "error", "error": "unknown message type"})
    except WebSocketDisconnect:
        session.cancel_current()
        return


async def handle_audio_chunk(session: VoiceSession, msg: dict):
    try:
        pcm = base64.b64decode(msg.get("data", ""))
    except Exception:
        return
    if not pcm:
        return
    now = time.monotonic()
    session.audio_buffer.extend(pcm)
    if session.utterance_start is None:
        session.utterance_start = now
    # simple energy VAD over int16 pcm
    energy = _pcm_energy(pcm)
    is_voice = energy >= settings.voice_vad_threshold
    if is_voice:
        session.last_voice_ts = now
        if not session.speaking:
            session.speaking = True
            session.cancel_current()  # barge-in
            await session.send({"type": "vad", "state": "speech_start"})

    silence_ms = (now - session.last_voice_ts) * 1000
    utterance_s = now - (session.utterance_start or now)
    should_finalize = session.speaking and (silence_ms >= settings.voice_silence_ms or utterance_s >= settings.voice_max_utterance_s)
    if should_finalize:
        audio = bytes(session.audio_buffer)
        session.audio_buffer.clear()
        session.speaking = False
        session.utterance_start = None
        await session.send({"type": "vad", "state": "speech_end"})
        await schedule_utterance_audio(session, audio)


def _pcm_energy(pcm: bytes) -> float:
    if len(pcm) < 2:
        return 0.0
    import array

    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) - (len(pcm) % 2)])
    if not samples:
        return 0.0
    # normalized mean absolute amplitude
    return sum(abs(s) for s in samples) / (len(samples) * 32768.0)


async def schedule_utterance_audio(session: VoiceSession, pcm: bytes):
    session.cancel_current()
    session.interrupted = False
    session.current_task = asyncio.create_task(handle_utterance_audio(session, pcm))


async def schedule_utterance(session: VoiceSession, text: str, language: str):
    session.cancel_current()
    session.interrupted = False
    session.current_task = asyncio.create_task(handle_utterance_text(session, text, language))


async def handle_utterance_audio(session: VoiceSession, pcm: bytes):
    t0 = time.perf_counter()
    stt = await session.stt.transcribe_pcm16(pcm)
    if session.interrupted:
        return
    text = (stt.text or "").strip()
    language = stt.language or session.language or "en"
    session.language = language
    await session.send({"type": "stt", "text": text, "language": language})
    if not text:
        return
    await handle_utterance_text(session, text, language, t0=t0)


async def handle_utterance_text(session: VoiceSession, text: str, language: str, t0: float | None = None):
    t0 = t0 or time.perf_counter()
    # voice switch commands
    cmd = maybe_voice_command(text)
    if cmd:
        session.gender = cmd
        await session.send({"type": "voice_setting", "gender": cmd})
        reply_text = "Voice switched to female." if cmd == "female" else "Voice switched to male."
        await session.send({"type": "assistant_text", "text": reply_text, "language": language})
        await stream_tts(session, reply_text, language, t0)
        return

    # tool commands fast-path
    tool_result = await maybe_tool_command(session.runner, text)
    if tool_result is not None:
        reply_text = format_tool_result(tool_result, language)
        await session.send({"type": "assistant_text", "text": reply_text, "language": language, "tool_result": tool_result})
        await stream_tts(session, reply_text, language, t0)
        return

    # streaming LLM reply
    await session.send({"type": "assistant_start", "language": language})
    chunks: list[str] = []
    first_audio_sent = False
    sentence_buf = ""
    async for delta in stream_reply(text, language):
        if session.interrupted:
            return
        chunks.append(delta)
        sentence_buf += delta
        await session.send({"type": "assistant_delta", "delta": delta})
        if _sentence_ready(sentence_buf):
            sent, sentence_buf = await flush_tts(session, sentence_buf, language, t0, first_audio_sent)
            first_audio_sent = first_audio_sent or sent
    if sentence_buf.strip() and not session.interrupted:
        sent, _ = await flush_tts(session, sentence_buf, language, t0, first_audio_sent)
        first_audio_sent = first_audio_sent or sent
    full = "".join(chunks).strip()
    if full:
        await session.send({"type": "assistant_done", "text": full, "language": language})


async def flush_tts(session: VoiceSession, text: str, language: str, t0: float, first_audio_sent: bool):
    to_speak = text.strip()
    if not to_speak:
        return False, ""
    sent = False
    async for audio in synthesize_stream(to_speak, language, session.gender):
        if session.interrupted:
            return sent, ""
        b64 = base64.b64encode(audio).decode("ascii")
        msg: dict[str, object] = {"type": "tts_chunk", "audio_b64": b64, "format": "mp3"}
        if not first_audio_sent and not sent:
            ttfa = (time.perf_counter() - t0) * 1000
            msg["ttfa_ms"] = round(ttfa, 1)
            await session.send({"type": "metrics", "ttfa_ms": round(ttfa, 1)})
            first_audio_sent = True
        sent = True
        await session.send(msg)
    return sent, ""


async def stream_tts(session: VoiceSession, text: str, language: str, t0: float):
    first = False
    async for audio in synthesize_stream(text, language, session.gender):
        if session.interrupted:
            return
        b64 = base64.b64encode(audio).decode("ascii")
        msg: dict[str, object] = {"type": "tts_chunk", "audio_b64": b64, "format": "mp3"}
        if not first:
            ttfa = (time.perf_counter() - t0) * 1000
            msg["ttfa_ms"] = round(ttfa, 1)
            await session.send({"type": "metrics", "ttfa_ms": round(ttfa, 1)})
            first = True
        await session.send(msg)


def _sentence_ready(buf: str) -> bool:
    return len(buf) >= 60 and buf.rstrip().endswith((".", "!", "?", "\n"))


def maybe_voice_command(text: str) -> str | None:
    t = text.lower()
    if any(p in t for p in ["girl voice", "female voice", "woman voice", "change to girl", "switch to female"]):
        return "female"
    if any(p in t for p in ["boy voice", "male voice", "man voice", "switch to male"]):
        return "male"
    return None


async def maybe_tool_command(runner: AssistantRunner, text: str):
    t = text.lower().strip()
    if "show alerts" in t:
        return await runner.execute("show_alerts", {"limit": 20})
    if "what happened today" in t:
        return await runner.execute("what_happened_today", {})
    if "stop all workers" in t:
        return await runner.execute("stop_all_workers", {}, confirmed=False)
    if t.startswith("start ") and "workers" in t:
        parts = t.split()
        try:
            count = int(parts[1])
        except Exception:
            count = 1
        worker_type = "news_rss" if "news" in t else "price" if "price" in t else "page_watch" if "page" in t else "mock"
        return await runner.execute("start_workers", {"worker_type": worker_type, "count": count}, confirmed=False)
    return None


def format_tool_result(result: dict, language: str) -> str:
    if result.get("requires_confirmation"):
        return f"Confirmation required: {result.get('message')} Action ID {result.get('action_id')}."
    if result.get("ok") and "alerts" in result:
        alerts = result["alerts"]
        return f"Found {len(alerts)} alerts." if alerts else "No alerts found."
    if result.get("ok") and "summary" in result:
        s = result["summary"]
        return f"Today: {s.get('alert_count', 0)} alerts. Sources: {s.get('alerts_by_source', {})}."
    if result.get("ok"):
        return f"Done: {result}"
    return f"Error: {result.get('error','unknown')}"
