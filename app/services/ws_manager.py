"""In-memory WebSocket fan-out per match."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class MatchConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, dict[str, WebSocket]] = defaultdict(dict)

    async def connect(self, match_id: str, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        # replace previous socket for same user
        old = self._rooms[match_id].get(user_id)
        if old is not None and old is not websocket:
            try:
                await old.close(code=4000)
            except Exception:
                pass
        self._rooms[match_id][user_id] = websocket

    def disconnect(self, match_id: str, user_id: str) -> None:
        room = self._rooms.get(match_id)
        if not room:
            return
        room.pop(user_id, None)
        if not room:
            self._rooms.pop(match_id, None)

    async def send_user(self, match_id: str, user_id: str, payload: dict[str, Any]) -> None:
        ws = self._rooms.get(match_id, {}).get(user_id)
        if ws is None:
            return
        await ws.send_text(json.dumps(payload, default=str))

    async def broadcast(self, match_id: str, payload: dict[str, Any]) -> None:
        dead: list[str] = []
        for uid, ws in list(self._rooms.get(match_id, {}).items()):
            try:
                await ws.send_text(json.dumps(payload, default=str))
            except Exception:
                dead.append(uid)
        for uid in dead:
            self.disconnect(match_id, uid)

    def connected_user_ids(self, match_id: str) -> list[str]:
        return list(self._rooms.get(match_id, {}).keys())


ws_manager = MatchConnectionManager()
