"""The configuration surface over HTTP (story 1.9, AD-25): admin-only reads and writes, every
write validated against the schema and audited, provenance exposed. TestClient + SQLite, no
network. The tenant comes from the session — a caller never edits another firm's configuration.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore
from apx.api import app as app_module
from apx.api.app import app

SECRET = "test-secret"


@pytest.fixture(autouse=True)
def _reset_state():
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()
    yield
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()


def _prepare(tmp_path: Path, monkeypatch) -> SqlStore:
    url = f"sqlite:///{tmp_path / 'apx.db'}"
    Base.metadata.create_all(create_engine(url))
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("APX_SECRET_KEY", SECRET)
    return SqlStore(sessionmaker(bind=create_engine(url), future=True))


def _login(c: TestClient, email: str, pw: str = "pw12345678", tenant: str = "t"):
    r = c.post("/api/login", json={"tenant": tenant, "email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r


def test_admin_reads_every_key_with_value_and_default(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "boss@t.fr", "pw12345678", "Boss", {"w"}, is_admin=True)
    with TestClient(app) as c:
        _login(c, "boss@t.fr")
        r = c.get("/api/admin/config")
    assert r.status_code == 200
    by_key = {item["key"]: item for item in r.json()}
    assert "interface_language" in by_key and by_key["interface_language"]["value"] == "fr"
    assert by_key["off_corpus_refusal_enabled"]["default"] is True


def test_admin_sets_a_value_and_it_is_audited(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "boss@t.fr", "pw12345678", "Boss", {"w"}, is_admin=True)
    with TestClient(app) as c:
        _login(c, "boss@t.fr")
        r = c.put("/api/admin/config/interface_language", json={"value": "en"})
        assert r.status_code == 200, r.text
        assert r.json() == {
            "key": "interface_language", "before": "fr", "after": "en", "changed": True}
        # persisted + reflected on the next read
        assert c.get("/api/admin/config").json()
    assert store.get_config("t", "interface_language") == "en"
    assert all(p.audited for p in store.config_provenance("t"))  # via the surface → audited


def test_a_bad_value_and_an_unknown_key_are_422(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "boss@t.fr", "pw12345678", "Boss", {"w"}, is_admin=True)
    with TestClient(app) as c:
        _login(c, "boss@t.fr")
        assert c.put("/api/admin/config/mfa_required", json={"value": "yes"}).status_code == 422
        assert c.put("/api/admin/config/nope", json={"value": 1}).status_code == 422


def test_config_surface_is_admin_only(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "clerk@t.fr", "pw12345678", "Clerk", {"w"}, is_admin=False)
    with TestClient(app) as c:
        _login(c, "clerk@t.fr")
        assert c.get("/api/admin/config").status_code == 403
        put = c.put("/api/admin/config/interface_language", json={"value": "en"})
        assert put.status_code == 403
        assert c.get("/api/admin/config/provenance").status_code == 403


def test_config_requires_authentication(tmp_path: Path, monkeypatch) -> None:
    _prepare(tmp_path, monkeypatch)
    with TestClient(app) as c:
        assert c.get("/api/admin/config").status_code == 401


def test_provenance_endpoint_reports_a_stored_value(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "boss@t.fr", "pw12345678", "Boss", {"w"}, is_admin=True)
    with TestClient(app) as c:
        _login(c, "boss@t.fr")
        c.put("/api/admin/config/model_provider", json={"value": "ollama"})
        prov = c.get("/api/admin/config/provenance").json()
    by_key = {p["key"]: p for p in prov}
    assert by_key["model_provider"]["value"] == "ollama"
    assert by_key["model_provider"]["audited"] is True
