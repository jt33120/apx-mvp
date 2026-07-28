"""The failure-register read API (Story 2.6, FR-5/FR-49) — thin pass-throughs to the store use
cases, with the Chinese-wall scope enforced. The retry/bulk-retry HTTP surface and the register
screen are the deferred UX pass; these read + export endpoints are the wired, testable contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apx.api import app as app_module
from apx.api.app import app
from apx.core.app.ingest import IngestedFailure, IngestionResult
from apx.core.domain.failures import ErrorClass

# reuse the API test harness (a real SQLite store + session secret + a login helper)
from tests.api.test_ingest_api import _login, _prepare


@pytest.fixture(autouse=True)
def _reset_state():  # noqa: ANN202 — the app's cached store is per-DATABASE_URL; reset per test
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()
    yield
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()


def _seed_failure(store, matter: str, scope: str) -> None:  # noqa: ANN001
    store.save(
        IngestionResult(failures=[IngestedFailure(
            filename="a.pdf", submitted_path="/dossier/a.pdf", matter=matter, tenant="t",
            error_class=ErrorClass.PASSWORD_PROTECTED, detail="x", custodian="Me Martin")]),
        scope=scope, matter=matter, tenant="t")


def test_register_endpoints_return_the_entry_within_scope(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@x.fr", "pw", "Me Durand", {"wall"})
    _seed_failure(store, "m", "wall")
    with TestClient(app) as c:
        _login(c, "me@x.fr")
        one = c.get("/api/matters/m/register").json()
        assert len(one["entries"]) == 1
        e = one["entries"][0]
        assert e["error_class"] == "password-protected" and e["cardinality"] == "one"
        assert e["custodian"] == "Me Martin" and e["retryable"] and e["resolution_state"] == "open"
        allv = c.get("/api/register").json()
        assert {x["path"] for x in allv["entries"]} == {"/dossier/a.pdf"}
        exp = c.get("/api/register/export").json()
        assert len(exp["entries"]) == 1


def test_register_is_scope_filtered(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "a@x.fr", "pw", "Me A", {"wall-a"})
    _seed_failure(store, "m-b", "wall-b")            # a failure behind a wall the caller lacks
    with TestClient(app) as c:
        _login(c, "a@x.fr")
        assert c.get("/api/matters/m-b/register").status_code == 403   # fail closed
        assert c.get("/api/register").json()["entries"] == []          # tenant-wide: nothing held
