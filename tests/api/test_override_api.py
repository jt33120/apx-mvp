"""The *override* over HTTP (Story 5.6, FR-25) — the register override endpoint and the audit
trail's separate override count and filter.

The edge is where "cannot be committed without a reason" has to hold for a real client: an omitted
field is refused by the schema before the act is attempted, a blank one is refused by the one
validator, and neither writes anything. The trail read reports the overrides separately from
ordinary modifications and says how much of the record a filtered view is not showing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apx.api import app as app_module
from apx.api.app import app
from apx.core.app.ingest import IngestedFailure, IngestionResult
from apx.core.domain.failures import ErrorClass
from apx.core.domain.override import GROUND_REGISTER_EXIT, reason_from_detail
from tests.api.test_ingest_api import _login, _prepare

REASON = "source détruite chez le client — écartée en connaissance de cause"


@pytest.fixture(autouse=True)
def _reset_state():  # noqa: ANN202
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()
    yield
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()


def _seed_failure(store, matter: str, scope: str) -> str:  # noqa: ANN001
    store.save(
        IngestionResult(failures=[IngestedFailure(
            filename="a.pdf", submitted_path="/dossier/a.pdf", matter=matter, tenant="t",
            error_class=ErrorClass.CORRUPT_FILE, detail="x", custodian="Me Martin")]),
        actor="Me Dupont", scope=scope, matter=matter, tenant="t")
    return store.register(matter, "t", {scope})[0].id


def test_an_override_closes_the_entry_and_records_its_reason(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@x.fr", "pw", "Me Durand", {"wall"})
    entry_id = _seed_failure(store, "m", "wall")
    with TestClient(app) as c:
        _login(c, "me@x.fr")
        res = c.post(f"/api/register/{entry_id}/override", json={"reason": REASON})
        assert res.status_code == 200
        assert res.json() == {"entry_id": entry_id, "resolution_state": "overridden"}

        entry = c.get("/api/matters/m/register").json()["entries"][0]
        assert entry["resolution_state"] == "overridden" and not entry["retryable"]

        trail = c.get("/api/matters/m/audit").json()
        overrides = [e for e in trail["entries"] if e["override"]]
        assert len(overrides) == 1
        assert overrides[0]["override_ground"] == GROUND_REGISTER_EXIT
        assert overrides[0]["override_ground_fr"]                    # said in the lawyer's language
        assert reason_from_detail(overrides[0]["detail"]) == REASON  # verbatim (FR-25)


def test_a_blank_reason_is_refused_and_the_entry_stays_open(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@x.fr", "pw", "Me Durand", {"wall"})
    entry_id = _seed_failure(store, "m", "wall")
    with TestClient(app) as c:
        _login(c, "me@x.fr")
        assert c.post(f"/api/register/{entry_id}/override", json={"reason": "   "}).status_code \
            == 400
        assert c.get("/api/matters/m/register").json()["entries"][0]["resolution_state"] == "open"


def test_an_omitted_reason_never_reaches_the_act(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@x.fr", "pw", "Me Durand", {"wall"})
    entry_id = _seed_failure(store, "m", "wall")
    with TestClient(app) as c:
        _login(c, "me@x.fr")
        # no default and no `| None` on the field: the schema refuses it at the edge (422)
        assert c.post(f"/api/register/{entry_id}/override", json={}).status_code == 422
        assert c.get("/api/matters/m/register").json()["entries"][0]["resolution_state"] == "open"


def test_a_walled_entry_and_an_absent_one_answer_identically(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "a@x.fr", "pw", "Me A", {"wall-a"})
    entry_id = _seed_failure(store, "m-b", "wall-b")
    with TestClient(app) as c:
        _login(c, "a@x.fr")
        walled = c.post(f"/api/register/{entry_id}/override", json={"reason": REASON})
        absent = c.post("/api/register/deadbeef/override", json={"reason": REASON})
        # same status AND same body: a difference either way is a map of what exists behind a wall
        assert walled.status_code == absent.status_code == 403
        assert walled.json() == absent.json()


def test_an_entry_that_moved_is_refused_rather_than_re_closed(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@x.fr", "pw", "Me Durand", {"wall"})
    entry_id = _seed_failure(store, "m", "wall")
    with TestClient(app) as c:
        _login(c, "me@x.fr")
        c.post(f"/api/register/{entry_id}/override", json={"reason": REASON})
        second = c.post(f"/api/register/{entry_id}/override", json={"reason": "je réessaie"})
        assert second.status_code == 400 and "not open" in second.json()["detail"]


def test_the_trail_counts_overrides_separately_and_the_filter_does_not_shrink_the_count(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@x.fr", "pw", "Me Durand", {"wall"})
    entry_id = _seed_failure(store, "m", "wall")
    with TestClient(app) as c:
        _login(c, "me@x.fr")
        c.post(f"/api/register/{entry_id}/override", json={"reason": REASON})

        whole = c.get("/api/matters/m/audit").json()
        assert whole["overrides"] == 1
        assert whole["entries_total"] == len(whole["entries"]) > 1   # ordinary acts are there too

        filtered = c.get("/api/matters/m/audit?overrides_only=true").json()
        assert len(filtered["entries"]) == 1 and filtered["entries"][0]["override"]
        # the counts describe the record, not the page
        assert filtered["overrides"] == 1
        assert filtered["entries_total"] == whole["entries_total"]
        assert filtered["verified"] == whole["verified"]


def test_a_matter_with_no_override_says_zero(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@x.fr", "pw", "Me Durand", {"wall"})
    _seed_failure(store, "m", "wall")
    with TestClient(app) as c:
        _login(c, "me@x.fr")
        trail = c.get("/api/matters/m/audit").json()
        assert trail["overrides"] == 0
        assert all(not e["override"] and e["override_ground"] is None for e in trail["entries"])
        assert c.get("/api/matters/m/audit?overrides_only=true").json()["entries"] == []
