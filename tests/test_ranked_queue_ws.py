def _recv_until(ws, wanted: set[str], limit: int = 60):
    last = None
    for _ in range(limit):
        last = ws.receive_json()
        if last.get("type") in wanted:
            return last
    raise AssertionError(f"expected one of {wanted}, last={last}")


def _play_until_finished(host_ws, guest_ws, host_idx: int = 1, guest_idx: int = 0):
    host_done = False
    guest_done = False
    host_finished = None
    guest_finished = None

    for _ in range(200):
        if not host_done:
            msg = host_ws.receive_json()
            t = msg.get("type")
            if t == "question":
                host_ws.send_json(
                    {
                        "type": "answer",
                        "question_id": msg["question_id"],
                        "selected_index": host_idx,
                    }
                )
            elif t == "match_finished":
                host_finished = msg
                host_done = True
        if not guest_done:
            msg = guest_ws.receive_json()
            t = msg.get("type")
            if t == "question":
                guest_ws.send_json(
                    {
                        "type": "answer",
                        "question_id": msg["question_id"],
                        "selected_index": guest_idx,
                    }
                )
            elif t == "match_finished":
                guest_finished = msg
                guest_done = True
        if host_done and guest_done:
            break

    assert host_done and guest_done
    return host_finished, guest_finished


def test_queue_matchmaking_and_autostart(client):
    q1 = client.post("/api/ranked/queue", json={"user_id": "host1", "display_name": "Host"})
    assert q1.status_code == 200
    assert q1.json()["status"] == "searching"

    q2 = client.post("/api/ranked/queue", json={"user_id": "guest1", "display_name": "Guest"})
    assert q2.status_code == 200
    assert q2.json()["status"] == "matched"
    match_id = q2.json()["match_id"]
    assert match_id

    cur = client.get("/api/ranked/current", params={"user_id": "guest1"})
    assert cur.status_code == 200
    assert cur.json()["status"] == "matched"
    assert cur.json()["match_id"] == match_id

    with client.websocket_connect(f"/ws/ranked/{match_id}?user_id=host1") as host_ws:
        with client.websocket_connect(f"/ws/ranked/{match_id}?user_id=guest1") as guest_ws:
            _recv_until(host_ws, {"match_state", "ban_phase"})
            _recv_until(guest_ws, {"match_state", "ban_phase"})

            host_ws.send_json({"type": "ban_topics", "topics": ["Кино"]})
            guest_ws.send_json({"type": "ban_topics", "topics": ["Спорт"]})

            host_fin, guest_fin = _play_until_finished(host_ws, guest_ws)
            assert "rating_delta" in host_fin
            assert "ranking" in host_fin
            assert guest_fin["match_id"] == match_id


def test_leave_match(client):
    created = client.post(
        "/api/ranked/matches",
        json={"user_id": "h2", "display_name": "H", "round_count": 2},
    )
    assert created.status_code == 200
    match_id = created.json()["match_id"]

    joined = client.post(
        f"/api/ranked/matches/{match_id}/join",
        json={"user_id": "g2", "display_name": "G"},
    )
    assert joined.status_code == 200

    left = client.post(
        f"/api/ranked/matches/{match_id}/leave",
        json={"user_id": "g2"},
    )
    assert left.status_code == 200
    assert left.json()["status"] in {"cancelled", "finished"}
    assert left.json()["finish_reason"] == "leave"


def test_match_snapshot_has_reconnect_fields(client):
    created = client.post(
        "/api/ranked/matches",
        json={"user_id": "h3", "display_name": "H", "round_count": 1, "round_seconds": 20},
    )
    match_id = created.json()["match_id"]
    client.post(
        f"/api/ranked/matches/{match_id}/join",
        json={"user_id": "g3", "display_name": "G"},
    )

    with client.websocket_connect(f"/ws/ranked/{match_id}?user_id=h3") as host_ws:
        with client.websocket_connect(f"/ws/ranked/{match_id}?user_id=g3") as guest_ws:
            _recv_until(host_ws, {"match_state", "ban_phase"})
            _recv_until(guest_ws, {"match_state", "ban_phase"})
            host_ws.send_json({"type": "ban_topics", "topics": []})
            guest_ws.send_json({"type": "ban_topics", "topics": []})

            q = None
            for _ in range(40):
                msg = host_ws.receive_json()
                if msg.get("type") == "question":
                    q = msg
                    break
            assert q is not None
            host_ws.send_json(
                {"type": "answer", "question_id": q["question_id"], "selected_index": 1}
            )
            _recv_until(host_ws, {"answer_accepted"})

            snap = client.get(
                f"/api/ranked/matches/{match_id}",
                params={"user_id": "h3"},
            )
            assert snap.status_code == 200
            body = snap.json()
            assert body["status"] == "in_progress"
            assert body["current_question"] is not None
            assert body["current_question"]["question_id"] == q["question_id"]
            assert body["own_answer"] is not None
            assert body["own_answer"]["selected_index"] == 1
