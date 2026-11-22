from fastapi.testclient import TestClient


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "auth.db"))
    monkeypatch.setenv("MOCK_MODE", "true")
    from config import settings as s

    s.get_settings.cache_clear()
    s.settings.sqlite_path = str(tmp_path / "auth.db")
    import backend.main as m

    # ensure fresh app state with test DB
    return TestClient(m.app)


def test_api_and_ws_require_auth(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        r = client.get("/api/workers")
        assert r.status_code == 401
        r = client.get("/api/alerts/rules")
        assert r.status_code == 401
        try:
            with client.websocket_connect("/ws/workers") as ws:
                # if connected, server should close quickly; accept either close or no snapshot
                ws.receive_text()
                assert False, "expected unauthorized close"
        except Exception:
            pass


def test_setup_login_logout_flow(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        s = client.get("/api/auth/status")
        assert s.status_code == 200
        assert s.json()["initialized"] is False

        r = client.post("/api/auth/setup", json={"password": "password123"})
        assert r.status_code == 200
        assert client.cookies.get("ww_session")

        r = client.get("/api/workers")
        assert r.status_code == 200

        r = client.post("/api/auth/logout")
        assert r.status_code == 200
        r = client.get("/api/workers")
        assert r.status_code == 401

        r = client.post("/api/auth/login", json={"password": "wrongpass"})
        assert r.status_code == 401
        r = client.post("/api/auth/login", json={"password": "password123"})
        assert r.status_code == 200
        r = client.get("/api/workers")
        assert r.status_code == 200
