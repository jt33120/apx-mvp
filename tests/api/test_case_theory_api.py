"""The case-theory HTTP surface (Story 4.1, FR-37): write / rewrite / withdraw / history, each
scope-gated and — for writes — audited. A matter whose wall the caller does not hold is a
non-disclosing 404 (FR-14), identical to an absent matter."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import AuditRecord, Base
from apx.adapters.store_postgres.store import SqlStore
from apx.api import app as app_module
from apx.api.app import app
from apx.core.app.ingest import IngestionResult


def _data(tmp_path):  # noqa: ANN001, ANN202
    """The data volume, in its own subdirectory.

    Story 7.1: APX_INGEST_ROOT is the test's tmp_path, and a root that can reach
    $APX_DATA_PATH/originals or /spool is refused — those hold another matter's
    retained documents and another user's upload. So the data volume sits BESIDE the
    ingestable tree rather than inside it, which is also how a deployment separates them.
    """
    d = tmp_path.parent / f"{tmp_path.name}-data"
    d.mkdir(exist_ok=True)
    return d


TENANT, WALL, OTHER = "t", "wall-a", "wall-b"


@pytest.fixture(autouse=True)
def _reset_state():  # noqa: ANN201
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()
    yield
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()


def _prepare(tmp_path: Path, monkeypatch) -> SqlStore:  # noqa: ANN001
    url = f"sqlite:///{tmp_path / 'apx.db'}"
    Base.metadata.create_all(create_engine(url))
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("APX_SECRET_KEY", "test-secret")
    monkeypatch.setenv("APX_DATA_PATH", str(_data(tmp_path)))
    store = SqlStore(sessionmaker(bind=create_engine(url), future=True))
    # a matter under WALL, created silently (no ingest audit noise)
    store.save(IngestionResult(), scope=WALL, actor="sys", matter="m", tenant=TENANT, audit=False)
    return store


def _login(c: TestClient, email: str = "me@cab.fr", pw: str = "password1") -> None:
    r = c.post("/api/login", json={"tenant": TENANT, "email": email, "password": pw})
    assert r.status_code == 200, r.text


def _case_theory_actions(store: SqlStore) -> list[str]:
    with store._sf() as s:
        rows = s.scalars(select(AuditRecord.action).where(AuditRecord.tenant == TENANT))
        return [a for a in rows if a.startswith("case_theory")]  # skip create_user etc. noise


def test_put_then_get_reflects_the_theory_and_a_version(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    store = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    c = TestClient(app)
    _login(c)
    r = c.put("/api/matters/m/case-theory", json={"text": "contestation licenciement"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["present"] and body["current"]["version_no"] == 1
    assert body["current"]["text"] == "contestation licenciement"
    got = c.get("/api/matters/m/case-theory").json()
    assert got["present"] and got["current"]["text"] == "contestation licenciement"


def test_a_second_put_appends_version_2_and_history_keeps_both(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    store = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    c = TestClient(app)
    _login(c)
    c.put("/api/matters/m/case-theory", json={"text": "v1"})
    r = c.put("/api/matters/m/case-theory", json={"text": "v2"})
    assert r.json()["current"]["version_no"] == 2
    hist = c.get("/api/matters/m/case-theory/versions").json()
    assert [[v["version_no"], v["text"]] for v in hist["versions"]] == [[1, "v1"], [2, "v2"]]


def test_delete_withdraws_but_history_is_retained(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    store = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    c = TestClient(app)
    _login(c)
    c.put("/api/matters/m/case-theory", json={"text": "v1"})
    r = c.delete("/api/matters/m/case-theory")
    assert r.status_code == 200 and r.json()["withdrawn"] and not r.json()["present"]
    hist = c.get("/api/matters/m/case-theory/versions").json()
    assert [v["version_no"] for v in hist["versions"]] == [1, 2]  # nothing hard-deleted (AD-7)
    assert hist["versions"][1]["withdrawn"] is True


def test_each_write_records_one_audit_entry(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    store = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    c = TestClient(app)
    _login(c)
    c.put("/api/matters/m/case-theory", json={"text": "v1"})
    c.delete("/api/matters/m/case-theory")
    assert _case_theory_actions(store) == ["case_theory_written", "case_theory_withdrawn"]


def test_a_user_without_the_wall_gets_a_non_disclosing_404(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    store = _prepare(tmp_path, monkeypatch)
    store.append_case_theory_version(tenant=TENANT, matter="m", actor="sys", text="secret")
    store.create_user(TENANT, "you@cab.fr", "password1", "Me Autre", {OTHER})  # never holds WALL
    c = TestClient(app)
    _login(c, "you@cab.fr")
    assert c.get("/api/matters/m/case-theory").status_code == 404
    assert c.put("/api/matters/m/case-theory", json={"text": "x"}).status_code == 404
    assert c.delete("/api/matters/m/case-theory").status_code == 404
    assert c.get("/api/matters/m/case-theory/versions").status_code == 404
    # the refused writes leaked nothing — the theory is untouched
    latest = store.list_case_theory_versions(tenant=TENANT, matter="m", scopes={WALL})
    assert [v.text for v in latest] == ["secret"]


def test_get_on_a_matter_with_no_theory_is_present_false(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    store = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    c = TestClient(app)
    _login(c)
    got = c.get("/api/matters/m/case-theory").json()
    assert got["present"] is False and got["current"] is None
