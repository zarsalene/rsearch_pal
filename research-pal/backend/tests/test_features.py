"""Feature switches: each new feature has a switch in Settings."""
import sqlite3

from app import config, db, features
from helpers import upload, wait_ready


def test_list_needs_login(client):
    assert client.get("/api/features").status_code == 401
    assert client.put("/api/features", json={"features": {"chat": False}}).status_code == 401


def test_read_and_write_a_switch(client, auth_headers):
    h = auth_headers
    got = {f["name"]: f for f in client.get("/api/features", headers=h).json()}
    assert got["chat"]["enabled"] is True and got["chat"]["label"] and got["chat"]["description"]  # the default
    after = {f["name"]: f for f in client.put("/api/features", headers=h, json={"features": {"chat": False}}).json()}
    assert after["chat"]["enabled"] is False
    assert {f["name"]: f for f in client.get("/api/features", headers=h).json()}["chat"]["enabled"] is False  # it is saved
    assert db.get_feature("chat") is False
    client.put("/api/features", headers=h, json={"features": {"chat": True}})
    assert db.get_feature("chat") is True


def test_unknown_feature_is_refused_and_nothing_is_saved(client, auth_headers):
    r = client.put("/api/features", headers=auth_headers, json={"features": {"chat": False, "nope": True}})
    assert r.status_code == 400 and "nope" in r.json()["detail"]
    assert db.get_feature("chat") is None  # the good name was not saved either
    assert client.put("/api/features", headers=auth_headers, json={"features": {"chat": "maybe"}}).status_code == 422


def test_a_switched_off_feature_is_blocked_and_the_app_goes_on(client, auth_headers, fake_ai, sample_pdfs):
    h = auth_headers
    pid = upload(client, h, sample_pdfs["a.pdf"].path)
    wait_ready(client, h, pid)
    body = {"question": "What precision does AUTOMA reach?", "paper_ids": [pid]}
    assert client.post("/api/chat", headers=h, json=body).status_code == 200
    client.put("/api/features", headers=h, json={"features": {"chat": False}})
    r = client.post("/api/chat", headers=h, json=body)
    assert r.status_code == 403 and "switched off" in r.json()["detail"]
    assert client.get(f"/api/papers/{pid}", headers=h).status_code == 200  # the rest of the app works
    client.put("/api/features", headers=h, json={"features": {"chat": True}})
    assert client.post("/api/chat", headers=h, json=body).status_code == 200


def test_a_new_feature_uses_its_default(client, auth_headers, monkeypatch):
    monkeypatch.setitem(features.REGISTRY, "demo_off", {"label": "Demo", "description": "A test feature.", "default": False})
    got = {f["name"]: f["enabled"] for f in client.get("/api/features", headers=auth_headers).json()}
    assert got["demo_off"] is False and got["chat"] is True
    client.put("/api/features", headers=auth_headers, json={"features": {"demo_off": True}})
    assert features.is_enabled("demo_off") is True


def test_an_old_database_keeps_its_rows(client):
    """A database from before this sprint has no features table. init() adds it and keeps every row."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    old = config.DATA_DIR / "old.sqlite3"
    c = sqlite3.connect(old)
    c.executescript("CREATE TABLE papers(id TEXT PRIMARY KEY, filename TEXT, title TEXT, status TEXT, error TEXT, purpose TEXT, n_pages INTEGER DEFAULT 0, created_at REAL, updated_at REAL);"
                    "INSERT INTO papers(id, filename, title, status) VALUES('p1', 'old.pdf', 'Old paper', 'ready');")
    c.commit()
    c.close()
    real = config.DB_PATH
    try:
        config.DB_PATH = old
        db.init()
        assert db.get_paper("p1")["title"] == "Old paper"
        assert db.get_feature("chat") is None
        db.set_feature("chat", False)
        assert db.get_feature("chat") is False
    finally:
        config.DB_PATH = real
