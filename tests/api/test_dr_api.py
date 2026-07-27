"""The disaster-recovery surface over HTTP (story 1.11, AD-32/AD-35): the DR status (admin only),
the truncation override, and the pre-flight capacity refusal. TestClient + SQLite.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import Base, TruncationMarker
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


def test_dr_status_is_admin_only(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "clerk@t.fr", "pw12345678", "Clerk", {"w"}, is_admin=False)
    with TestClient(app) as c:
        assert c.get("/api/admin/dr").status_code == 401
        _login(c, "clerk@t.fr")
        assert c.get("/api/admin/dr").status_code == 403


def test_dr_status_reports_overdue_and_footprint(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "boss@t.fr", "pw12345678", "Boss", {"w"}, is_admin=True)
    with TestClient(app) as c:
        _login(c, "boss@t.fr")
        body = c.get("/api/admin/dr").json()
    assert body["backup"]["overdue"] is True                 # no backup yet → overdue (AD-32)
    assert body["backup"]["interval_hours"] == 24            # the config-as-data default
    assert body["truncation"]["active"] is False
    assert body["design_target_footprint"]["piece_count"] == 100_000  # the stated footprint


def test_a_truncation_is_reported_and_cleared_by_an_audited_override(
    tmp_path: Path, monkeypatch
) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "boss@t.fr", "pw12345678", "Boss", {"w"}, is_admin=True)
    with store._sf() as s, s.begin():   # seed an active truncation marker
        s.add(TruncationMarker(
            tenant="t", detected_at=datetime.now(UTC), journal_seq=5, live_seq=2))
    with TestClient(app) as c:
        _login(c, "boss@t.fr")
        assert c.get("/api/admin/dr").json()["truncation"]["active"] is True
        # an empty reason is refused
        assert c.post("/api/admin/dr/truncation/clear", json={"reason": " "}).status_code == 400
        ok = c.post("/api/admin/dr/truncation/clear",
                    json={"reason": "restored from a verified backup"})
        assert ok.status_code == 200
        assert c.get("/api/admin/dr").json()["truncation"]["active"] is False


def test_ingest_is_refused_when_it_cannot_fit(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "boss@t.fr", "pw12345678", "Boss", {"w"}, is_admin=True)
    folder = tmp_path / "drop"
    folder.mkdir()
    (folder / "letter.txt").write_text("Maître…", encoding="utf-8")
    # the disk reports almost no free space → the pre-flight refuses the import (507), not at 70 %
    monkeypatch.setattr(
        app_module.shutil, "disk_usage", lambda _p: type("U", (), {"free": 1})())
    with TestClient(app) as c:
        _login(c, "boss@t.fr")
        r = c.post("/api/ingest", json={"folder": str(folder), "matter": "m", "scope": "w"})
    assert r.status_code == 507 and "refused" in r.json()["detail"]
