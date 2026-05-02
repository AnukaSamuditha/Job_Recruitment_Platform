from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.ws.broadcast import ScreeningBroadcaster

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/screening/{run_id}")
async def screening_ws(
    websocket: WebSocket,
    run_id: str,
) -> None:
    broadcaster: ScreeningBroadcaster = websocket.app.state.broadcaster
    await websocket.accept()
    q = broadcaster.subscribe(run_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30.0)
                await websocket.send_text(json.dumps(event))
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        logger.debug("WS disconnect run_id=%s", run_id)
    finally:
        broadcaster.unsubscribe(run_id, q)
