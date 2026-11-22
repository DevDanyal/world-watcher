from fastapi.testclient import TestClient


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "setup.db"))
    monkeypatch.setenv("MOCK_MODE", "true")
    from config import settings as s

    s.get_settings.cache_clear()
    s.settings.sqlite_path = str(tmp_path / "setup.db")
    import backend.main as m

    return TestClient(m.app)


def test_first_run_setup_endpoint(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        status = client.get("/api/auth/status")
        assert status.status_code == 200
        assert status.json() == {"initialized": False, "authenticated": False}

        r = client.post("/api/auth/setup", json={"password": "password123"})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["initialized"] is True
        assert body["authenticated"] is True
        assert "ww_session" in r.cookies

        r2 = client.post("/api/auth/setup", json={"password": "password123"})
        assert r2.status_code == 409
