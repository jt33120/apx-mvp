"""A *validation act* accepts the version that was on the screen, and says which.

Retro action **B2** — the Epic-5 retrospective's re-review of story 5.8 by the adversarial
fleet. Defect H7, reproduced by hand before this file was written.

FR-45's assertion is *"I have read this pièce and I accept the tool's assessment of it."* The
assessment belongs to one *ranking version* (AD-23 — no unqualified reference), and the drawer
prints which one on the button: *« Appréciation du classement n° 1. »*. The request carried no
version, and ``validate_pieces`` defaulted ``version_no=None``, which resolves **the current
version at commit time**. So a re-rank landing between the reading and the click moved what a
person is recorded as having accepted — silently, and toward whatever the tool now thinks.

Story 5.8 had already made this argument for the count: *"the count the lawyer was SHOWN, not one
re-derived at the click."* It was made for one half of the assertion and not the other. The version
is now required at the store, at the three routes, and in the client; and the bulk confirmation —
which named the count and never named the version — names it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apx.core.domain.validation import BatchSplit
from tests.api.test_ingest_api import _login, _prepare, _reset_state  # noqa: F401 — autouse
from tests.api.test_validation_api import MATTER, TENANT, V1, WALL, _rank, _ready

V2 = 2


def _versions(store) -> list[int]:  # noqa: ANN001
    return [v.version_no for v in store.list_ranking_versions(
        tenant=TENANT, matter=MATTER, scopes={WALL})]


# ── the act accepts the version it NAMES, never the one that happens to be current ─────────────

def test_an_act_naming_the_older_version_records_the_older_version(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """The defect, reproduced and reversed. A lawyer reads a *pièce* under version 1; a re-rank
    lands; she clicks. Before this story the entry said version 2 — an assessment she had never
    seen. It now says version 1, and the surface marks it stale, which is the honest pair: nothing
    is erased, nothing is invalidated, and the record does not claim she read what she did not."""
    store, client, pieces = _ready(tmp_path, monkeypatch)
    v1_id = store.read_ranking(tenant=TENANT, matter=MATTER, scopes={WALL}).version_id

    _rank(store, client)                                   # a second version arrives, unseen
    assert _versions(store) == [V2, V1] or sorted(_versions(store)) == [V1, V2]
    v2_id = store.read_ranking(tenant=TENANT, matter=MATTER, scopes={WALL}).version_id
    assert v2_id != v1_id

    r = client.post(f"/api/matters/{MATTER}/pieces/{pieces[0]}/validate?version_no={V1}")
    assert r.status_code == 200, r.text
    entry = r.json()["entries"][0]

    assert entry["ranking_version_id"] == v1_id, (
        "the act recorded acceptance of a version the lawyer was never shown")
    assert entry["stale"] is True                          # and the surface says so


def test_an_act_naming_the_current_version_records_it(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """The ordinary case, unchanged — the guard must not make the normal gesture harder."""
    store, client, pieces = _ready(tmp_path, monkeypatch)
    current = store.read_ranking(tenant=TENANT, matter=MATTER, scopes={WALL}).version_id
    r = client.post(f"/api/matters/{MATTER}/pieces/{pieces[0]}/validate?version_no={V1}")
    assert r.status_code == 200, r.text
    entry = r.json()["entries"][0]
    assert entry["ranking_version_id"] == current and entry["stale"] is False


def test_a_batch_accepts_the_version_it_names_for_every_piece(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """One gesture, one version, across every entry it writes. A batch resolving the version at the
    commit put a hundred and eighty entries on a ranking nobody had looked at."""
    store, client, pieces = _ready(tmp_path, monkeypatch)
    v1_id = store.read_ranking(tenant=TENANT, matter=MATTER, scopes={WALL}).version_id
    _rank(store, client)

    r = client.post(f"/api/matters/{MATTER}/validate-batch?version_no={V1}",
                    json={"piece_ids": pieces, "confirmed_count": len(pieces)})
    assert r.status_code == 200, r.text
    assert {e["ranking_version_id"] for e in r.json()["entries"]} == {v1_id}


# ── no version, no act ────────────────────────────────────────────────────────────────────────

def test_every_validation_route_refuses_a_request_that_names_no_version(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """Fail closed at the edge, before the act is attempted. An omitted version used to mean *the
    current one*, which is the flattering default on the record of what a person accepted."""
    store, client, pieces = _ready(tmp_path, monkeypatch)
    body = {"piece_ids": pieces, "confirmed_count": len(pieces)}

    assert client.post(
        f"/api/matters/{MATTER}/pieces/{pieces[0]}/validate").status_code == 422
    assert client.post(f"/api/matters/{MATTER}/validate-batch", json=body).status_code == 422
    assert client.post(
        f"/api/matters/{MATTER}/validate-batch/preview", json=body).status_code == 422
    assert store.read_validation_log(tenant=TENANT, matter=MATTER, scopes={WALL}) == ()


def test_the_store_refuses_an_act_with_no_version_too(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """The boundary is the store's, not the route's. A second caller — a manage command, a worker,
    a test — must not be able to reach the defaulting path, because there is no longer one."""
    store, _client, pieces = _ready(tmp_path, monkeypatch)
    with pytest.raises(TypeError, match="version_no"):
        store.validate_pieces(                                   # type: ignore[call-arg]
            tenant=TENANT, matter=MATTER, actor="Me Durand", piece_ids=[pieces[0]],
            scopes={WALL})


def test_an_act_naming_a_version_this_matter_does_not_have_is_refused(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """Absent and walled answer identically (FR-14), and nothing is written either way."""
    store, client, pieces = _ready(tmp_path, monkeypatch)
    r = client.post(f"/api/matters/{MATTER}/pieces/{pieces[0]}/validate?version_no=99")
    assert r.status_code == 403
    assert store.read_validation_log(tenant=TENANT, matter=MATTER, scopes={WALL}) == ()


# ── the confirmation names it ─────────────────────────────────────────────────────────────────

def test_the_bulk_confirmation_names_the_version(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """FR-45(a)'s dialog stated the count and the split and never said whose assessment she was
    accepting. The preview and the commit now take the same version, so the sentence describes the
    act the server will actually perform."""
    _store, client, pieces = _ready(tmp_path, monkeypatch)
    split = client.post(
        f"/api/matters/{MATTER}/validate-batch/preview?version_no={V1}",
        json={"piece_ids": pieces, "confirmed_count": len(pieces)}).json()
    assert split["version_no"] == V1
    assert f"classement n° {V1}" in split["sentence_fr"]


def test_the_split_sentence_still_leads_with_the_split() -> None:
    """The version is appended, never substituted: the split is the information FR-45(a) is about,
    and a sentence that opened with the version would bury it."""
    sentence = BatchSplit(total=180, opened=12, version_no=4).sentence_fr()
    assert sentence.startswith("Vous en avez ouvert 12.")
    assert "classement n° 4" in sentence
