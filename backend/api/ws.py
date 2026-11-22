from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.security import SESSION_COOKIE, get_session

router = APIRouter()


@router.websocket("/ws/workers")
async def workers_ws(websocket: WebSocket):
    token = websocket.cookies.get(SESSION_COOKIE)
    if not get_session(token):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    engine = websocket.app.state.engine

    async def send(msg):
        try:
            await websocket.send_text(json.dumps(msg))
        except Exception:
            pass

    engine.add_listener(send)
    try:
        await websocket.send_text(json.dumps(engine.snapshot()))
        while True:
            # keep alive; client may send pings/commands later
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        engine.remove_listener(send)
