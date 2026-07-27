"""The content-free diagnostic endpoint over HTTP (story 1.10, AD-26): admin-only, tenant strictly
from the session (never cross-tenant), returns the registry's projection. TestClient + SQLite.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore
from apx.api import app as app_module
from apx.api.app import app
from apx.core.app.ingest import IngestedPiece, IngestionResult

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


def _piece(pid: str, tenant: str, matter: str) -> IngestedPiece:
    return IngestedPiece(
        id=pid, matter=matter, tenant=tenant, content_hash=pid * 8, text_key=pid * 8,
        provenance_path=f"/{pid}.pdf", custodian="c", extraction_method="text",
        extractor_version="v1", schema_version="s1", ingestion_timestamp=datetime.now(UTC),
        full_text="x", text_version="v")


def _login(c: TestClient, email: str, pw: str = "pw12345678", tenant: str = "t"):
    r = c.post("/api/login", json={"tenant": tenant, "email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r


def test_diagnostics_requires_authentication(tmp_path: Path, monkeypatch) -> None:
    _prepare(tmp_path, monkeypatch)
    with TestClient(app) as c:
        assert c.get("/api/admin/diagnostics").status_code == 401


def test_diagnostics_is_admin_only(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "clerk@t.fr", "pw12345678", "Clerk", {"w"}, is_admin=False)
    with TestClient(app) as c:
        _login(c, "clerk@t.fr")
        assert c.get("/api/admin/diagnostics").status_code == 403


def test_admin_gets_the_three_content_free_projectors(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "boss@t.fr", "pw12345678", "Boss", {"w"}, is_admin=True)
    store.save(IngestionResult(pieces=[_piece("p1", "t", "m1")]), "w", actor="a")
    with TestClient(app) as c:
        _login(c, "boss@t.fr")
        r = c.get("/api/admin/diagnostics")
    assert r.status_code == 200
    by_name = {item["projector"]: item for item in r.json()}
    assert {"corpus_counts", "error_class_histogram", "versions"} <= set(by_name)
    assert by_name["corpus_counts"]["values"] == {"pieces": 1, "failures": 0, "matters": 1}


def test_diagnostics_are_scoped_to_the_callers_tenant(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "boss@t.fr", "pw12345678", "Boss", {"w"}, is_admin=True)
    # tenant "t" has one piece; another tenant "other" has three — the admin of "t" must see 1
    store.save(IngestionResult(pieces=[_piece("p1", "t", "m1")]), "w", actor="a")
    store.save(IngestionResult(
        pieces=[_piece("q1", "other", "mo"), _piece("q2", "other", "mo"),
                _piece("q3", "other", "mo2")]), "w", actor="a")
    with TestClient(app) as c:
        _login(c, "boss@t.fr")
        counts = {item["projector"]: item for item in c.get("/api/admin/diagnostics").json()}
    assert counts["corpus_counts"]["values"]["pieces"] == 1   # only tenant t's data, never "other"
