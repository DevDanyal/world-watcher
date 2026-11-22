from fastapi.testclient import TestClient


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("MOCK_MODE", "true")
    from config import settings as s

    s.get_settings.cache_clear()
    s.settings.sqlite_path = str(tmp_path / "api.db")
    import backend.main as m

    return TestClient(m.app)


def test_health_open_and_settings_requires_auth(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert client.get("/api/settings").status_code == 401


def test_worker_endpoints_and_ws_snapshot(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        client.post("/api/auth/setup", json={"password": "password123"})
        r = client.get("/api/workers")
        assert r.status_code == 200
        body = r.json()
        assert "workers" in body and "stats" in body and "events" in body

        r = client.post("/api/workers/mock?count=2")
        assert r.status_code == 200
        assert r.json()["queued"] == 2

        with client.websocket_connect("/ws/workers") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "snapshot"
            assert len(msg["workers"]) >= 1
