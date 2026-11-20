def test_solo_start_answer_and_results(client):
    start = client.post(
        "/api/quiz/start",
        json={
            "topic": "Космос",
            "count": 2,
            "difficulty": "easy",
            "player_name": "SoloPlayer",
        },
    )
    assert start.status_code == 200, start.text
    body = start.json()
    session_id = body["session_id"]
    q0 = body["questions"][0]

    ans = client.post(
        f"/api/quiz/{session_id}/answer",
        json={"question_id": q0["id"], "selected_index": 0},
    )
    assert ans.status_code == 200
    assert "lives_left" in ans.json()

    sync = client.post(
        "/api/solo/results",
        headers={"Idempotency-Key": "solo-1"},
        json={
            "version": 1,
            "session_id": session_id,
            "answers": [
                {"question_id": q0["id"], "selected_index": 0},
            ],
        },
    )
    assert sync.status_code == 200
    assert sync.json()["status"] == "saved"

    # idempotent
    sync2 = client.post(
        "/api/solo/results",
        headers={"Idempotency-Key": "solo-1"},
        json={"version": 1, "session_id": session_id, "answers": []},
    )
    assert sync2.status_code == 200
