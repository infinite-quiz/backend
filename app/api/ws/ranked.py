"""WebSocket endpoint for ranked matches."""

from __future__ import annotations

import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.services import ranked_service
from app.services.ws_manager import ws_manager

router = APIRouter()


@router.websocket("/ws/ranked/{match_id}")
async def ranked_ws(
    websocket: WebSocket,
    match_id: str,
    user_id: str = Query(..., min_length=1),
) -> None:
    await ws_manager.connect(match_id, user_id, websocket)
    try:
        # auto-join on connect
        await ranked_service.handle_ws_event(match_id, user_id, {"type": "join"})
        while True:
            raw = await websocket.receive_text()
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                await ws_manager.send_user(
                    match_id, user_id, {"type": "error", "detail": "Invalid JSON"}
                )
                continue
            if not isinstance(event, dict) or "type" not in event:
                await ws_manager.send_user(
                    match_id, user_id, {"type": "error", "detail": "Event must have type"}
                )
                continue
            await ranked_service.handle_ws_event(match_id, user_id, event)
    except WebSocketDisconnect:
        ws_manager.disconnect(match_id, user_id)
        await ranked_service.on_disconnect(match_id, user_id)
    except Exception:
        ws_manager.disconnect(match_id, user_id)
        await ranked_service.on_disconnect(match_id, user_id)
        raise
