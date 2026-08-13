"""The audit read endpoint after Story 5.5 — the chain each entry is counted on, and an honest
verdict per slice.

The case that matters is the mixed one: a matter whose history begins on the tenant chain (written
before this story, or migrated from it) and continues on its own. The endpoint must not fold the
two into a single ``verified`` boolean, because only one of them is a property the holder of a
scoped export can check for themselves.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apx.adapters.store_postgres.models import AuditRecord
from apx.api import app as app_module
from apx.api.app import app
from apx.core.app.ingest import IngestedFailure, IngestionResult
from apx.core.domain import audit
from apx.core.domain.failures import ErrorClass
from tests.api.test_ingest_api import _login, _prepare


@pytest.fixture(autouse=True)
def _reset_state():  # noqa: ANN202
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()
    yield
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()


def _seed(store, matter: str, scope: str) -> None:  # noqa: ANN001
    store.save(
        IngestionResult(failures=[IngestedFailure(
            filename="a.pdf", submitted_path="/dossier/a.pdf", matter=matter, tenant="t",
            error_class=ErrorClass.PASSWORD_PROTECTED, detail="x", custodian="Me Martin")]),
        scope=scope, actor="Me Dupont", matter=matter, tenant="t")


def test_every_entry_names_the_chain_it_is_counted_on(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@x.fr", "pw", "Me Durand", {"wall"})
    _seed(store, "m", "wall")
    with TestClient(app) as c:
        _login(c, "me@x.fr")
        body = c.get("/api/matters/m/audit").json()
    assert body["entries"]
    for e in body["entries"]:
        assert e["chain_scope"] == "m"
        assert e["chain_label_fr"] == "affaire « m »"


def test_the_matters_own_chain_is_reported_as_verifiable_in_isolation(
        tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@x.fr", "pw", "Me Durand", {"wall"})
    _seed(store, "m", "wall")
    with TestClient(app) as c:
        _login(c, "me@x.fr")
        body = c.get("/api/matters/m/audit").json()
    (own,) = [s for s in body["slices"] if s["chain_scope"] == "m"]
    assert own["verified"] and own["verifiable_in_isolation"] and own["broken_at"] is None
    assert body["verified"]


def test_a_pre_5_5_slice_is_reported_but_never_claimed_verifiable_in_isolation(
        tmp_path: Path, monkeypatch) -> None:
    """The migrated history sits on the tenant chain. It is verified here by recomputing the WHOLE
    tenant chain — which the holder of a scoped export cannot do, because the intervening links
    belong to matters outside their scope. Reporting one boolean over both slices would claim a
    property of bytes the reader does not hold."""
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@x.fr", "pw", "Me Durand", {"wall"})
    _seed(store, "m", "wall")
    # a legacy entry: on the tenant chain, naming the matter, written under the v1 recipe
    with store._sf() as s, s.begin():
        store._append_audit(
            s, "t", "m", "Me Dupont", audit.ACT_CONFIG_CHANGED,
            '{"key": "interface_language", "after": "fr"}', datetime.now(UTC))

    with TestClient(app) as c:
        _login(c, "me@x.fr")
        body = c.get("/api/matters/m/audit").json()

    slices = {s["chain_scope"]: s for s in body["slices"]}
    assert slices["m"]["verifiable_in_isolation"] is True
    assert slices[""]["verifiable_in_isolation"] is False
    assert slices[""]["label_fr"] == "chaîne du cabinet"
    # both slices are still shown to the reader — the history is not silently trimmed to the half
    # that happens to be provable
    assert {e["chain_scope"] for e in body["entries"]} == {"m", ""}


def test_a_tamper_on_the_matters_chain_names_the_link_that_broke(
        tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@x.fr", "pw", "Me Durand", {"wall"})
    _seed(store, "m", "wall")
    _seed(store, "m", "wall")
    with store._sf() as s, s.begin():
        row = s.query(AuditRecord).filter(
            AuditRecord.chain_scope == "m", AuditRecord.seq == 2).one()
        row.detail = "rewritten after the fact"
    with TestClient(app) as c:
        _login(c, "me@x.fr")
        body = c.get("/api/matters/m/audit").json()
    (own,) = [s for s in body["slices"] if s["chain_scope"] == "m"]
    assert not own["verified"] and own["broken_at"] == 2
    assert not body["verified"]


def test_the_trail_is_still_scope_checked(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "a@x.fr", "pw", "Me A", {"wall-a"})
    _seed(store, "m-b", "wall-b")
    with TestClient(app) as c:
        _login(c, "a@x.fr")
        assert c.get("/api/matters/m-b/audit").status_code == 403


def test_the_tenant_slice_is_always_reported_so_a_wholesale_removal_cannot_hide(
        tmp_path: Path, monkeypatch) -> None:
    """CONFIRMED BY REVIEW. The slice was built only when the reader still held entries on the
    tenant chain, so deleting a matter's pre-5.5 history made the slice vanish and the trail read
    clean and shorter — nothing said a slice had ever existed."""
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@x.fr", "pw", "Me Durand", {"wall"})
    _seed(store, "m", "wall")
    with TestClient(app) as c:
        _login(c, "me@x.fr")
        body = c.get("/api/matters/m/audit").json()
    scopes = {s["chain_scope"] for s in body["slices"]}
    assert scopes == {"m", ""}
    tenant_slice = next(s for s in body["slices"] if s["chain_scope"] == "")
    assert tenant_slice["entries"] == 0 and tenant_slice["verified"] is True
    assert tenant_slice["verifiable_in_isolation"] is False
