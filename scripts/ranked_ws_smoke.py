"""
Smoke-test ranked match with 2 WebSocket clients.

Usage (server must be running on :8000):
  py -3 scripts/ranked_ws_smoke.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

import httpx
import websockets


def _log(who: str, msg: str) -> None:
    print(f"[{who}] {msg}")


async def _recv_until(
    ws: Any,
    who: str,
    wanted: set[str],
    timeout: float = 30.0,
) -> dict[str, Any]:
    async def _loop() -> dict[str, Any]:
        while True:
            raw = await ws.recv()
            data = json.loads(raw)
            etype = data.get("type", "?")
            _log(who, f"← {etype}: {json.dumps(data, ensure_ascii=False)[:280]}")
            if etype in wanted:
                return data
            if etype == "error":
                detail = str(data.get("detail", ""))
                if "Ban phase closed" in detail:
                    continue
                return data

    return await asyncio.wait_for(_loop(), timeout=timeout)


async def _drain_briefly(ws: Any, who: str, seconds: float = 0.25) -> None:
    try:
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=seconds)
            data = json.loads(raw)
            _log(who, f"← {data.get('type')}: {json.dumps(data, ensure_ascii=False)[:200]}")
    except (TimeoutError, asyncio.TimeoutError, websockets.ConnectionClosed):
        return


async def _play(
    name: str,
    ws: Any,
    *,
    ban_topic: str,
    answer_index: int,
    peer_connected: asyncio.Event,
    self_connected: asyncio.Event,
    both_banned: asyncio.Event,
    banned_count: dict[str, int],
    lock: asyncio.Lock,
) -> None:
    await _recv_until(ws, name, {"match_state", "ban_phase"})
    self_connected.set()
    await peer_connected.wait()
    await asyncio.sleep(0.15)

    await ws.send(json.dumps({"type": "ban_topics", "topics": [ban_topic]}))
    _log(name, f"→ ban_topics {[ban_topic]}")

    while not both_banned.is_set():
        data = await _recv_until(ws, name, {"ban_update", "match_state", "ban_phase"})
        if data.get("type") != "ban_update":
            continue
        async with lock:
            banned_count["n"] = len(
                {
                    p["user_id"]
                    for p in data.get("players", [])
                    if p.get("banned_topics")
                }
            )
            _log(name, f"bans seen from {banned_count['n']} player(s)")
            if banned_count["n"] >= 2:
                both_banned.set()

    await both_banned.wait()
    await _drain_briefly(ws, name)

    await ws.send(json.dumps({"type": "ready"}))
    _log(name, "→ ready")

    while True:
        data = await _recv_until(
            ws,
            name,
            {
                "match_start",
                "question",
                "answer_accepted",
                "round_result",
                "match_finished",
                "match_state",
                "ban_update",
                "opponent_left",
                "error",
            },
            timeout=60.0,
        )
        etype = data.get("type")
        if etype == "question":
            qid = data["question_id"]
            await ws.send(
                json.dumps(
                    {
                        "type": "answer",
                        "question_id": qid,
                        "selected_index": answer_index,
                    }
                )
            )
            _log(name, f"→ answer q={qid[:8]}… idx={answer_index}")
        elif etype == "match_finished":
            _log(name, f"DONE ranking={data.get('ranking')}")
            return
        elif etype == "error":
            detail = str(data.get("detail", ""))
            if "Ban phase closed" in detail:
                continue
            _log(name, f"ERROR {detail}")
            return


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base.rstrip("/")
    api = f"{base}/api/ranked"

    async with httpx.AsyncClient(timeout=30.0) as client:
        create = await client.post(
            f"{api}/matches",
            json={
                "user_id": "host_smoke",
                "display_name": "Host",
                "topic_candidates": ["Космос", "История", "Наука", "Кино", "Спорт"],
                "difficulty": "easy",
                "round_count": 2,
                "round_seconds": 15,
            },
        )
        create.raise_for_status()
        host_match = create.json()
        invite = host_match["invite_code"]
        ws_url = host_match["ws_url"]
        _log("REST", f"created match_id={host_match['match_id']} invite={invite}")
        _log("REST", f"ws_url={ws_url}")

        join = await client.post(
            f"{api}/matches/join",
            json={
                "user_id": "guest_smoke",
                "display_name": "Guest",
                "invite_code": invite,
            },
        )
        join.raise_for_status()
        body = join.json()
        _log("REST", f"joined status={body['status']} players={len(body['players'])}")

    host_connected = asyncio.Event()
    guest_connected = asyncio.Event()
    both_banned = asyncio.Event()
    banned_count = {"n": 0}
    lock = asyncio.Lock()

    async def host() -> None:
        url = f"{ws_url}?user_id=host_smoke"
        _log("HOST", f"connect {url}")
        async with websockets.connect(url) as ws:
            await _play(
                "HOST",
                ws,
                ban_topic="Кино",
                answer_index=1,
                peer_connected=guest_connected,
                self_connected=host_connected,
                both_banned=both_banned,
                banned_count=banned_count,
                lock=lock,
            )

    async def guest() -> None:
        url = f"{ws_url}?user_id=guest_smoke"
        _log("GUEST", f"connect {url}")
        async with websockets.connect(url) as ws:
            await _play(
                "GUEST",
                ws,
                ban_topic="Спорт",
                answer_index=0,
                peer_connected=host_connected,
                self_connected=guest_connected,
                both_banned=both_banned,
                banned_count=banned_count,
                lock=lock,
            )

    await asyncio.gather(host(), guest())


if __name__ == "__main__":
    asyncio.run(main())
