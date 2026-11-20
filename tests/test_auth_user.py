def test_register_login_me(client, unique_email):
    reg = client.post(
        "/api/auth/register",
        json={"email": unique_email, "password": "secret12", "displayName": "Alice"},
    )
    assert reg.status_code == 200, reg.text
    assert reg.json()["user"]["email"] == unique_email
    assert "quiz_session" in reg.cookies

    me = client.get("/api/user/me")
    assert me.status_code == 200
    assert me.json()["displayName"] == "Alice"

    client.post("/api/auth/logout")
    assert client.get("/api/user/me").status_code == 401

    login = client.post(
        "/api/auth/login",
        json={"email": unique_email, "password": "secret12"},
    )
    assert login.status_code == 200, login.text
    assert client.get("/api/user/me").status_code == 200


def test_leaderboard(client, unique_email):
    reg = client.post(
        "/api/auth/register",
        json={"email": unique_email, "password": "secret12", "displayName": "Bob"},
    )
    assert reg.status_code == 200, reg.text

    resp = client.get("/api/leaderboard")
    assert resp.status_code == 200
    body = resp.json()
    assert "leaders" in body
    assert body["me"] is not None
    assert body["me"]["displayName"] == "Bob"
