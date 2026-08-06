"""The triage table over HTTP (Story 4.10, FR-20/FR-16/FR-40/FR-42/FR-14).

The invariant the whole architecture was built around: **an edit changes that cell and nothing
else**. Asserted here the way the AC states it — N edits across N rows, then all N values must
hold — plus the change log beside each row (previous → new, author, timestamp), the refusals that
lose nothing, and the honesty of what the surface is allowed to show: a côté no route can set, an
unscored tail that is its own set, a line named by a pièce and never by an integer.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apx.api import app as app_module
from apx.api.app import app
from apx.core.app.line import place_line
from apx.core.app.rank import produce_ranking
from apx.core.domain.cascade import CascadeUnit
from apx.core.domain.config import CascadeConfig
from apx.core.domain.ranking import RankingIdentityInputs
from tests.api.test_ingest_api import _login, _prepare, _reset_state  # noqa: F401 — autouse
from tests.scoring_fakes import FakeScorer, FixedJudge

TENANT, WALL, MATTER = "t", "wall", "m"
ADMIN = "admin@cab.fr"
_TAXONOMY = ["Contrats", "Correspondance", "Jurisprudence"]
_FILES = {
    "bail.txt": "Contrat de bail commercial signé le 3 mars, clause résolutoire.",
    "facture.txt": "Facture EDF, 150 euros, échéance avril.",
    "note.txt": "Note interne sur la clause résolutoire du bail.",
    "annexe.txt": "Annexe technique au bail, plan des locaux.",
}


def _cfg() -> CascadeConfig:
    return CascadeConfig(uncertain_low=0.35, uncertain_high=0.65, calibration_sample=0,
                         stage3_max_share=1.0)


def _inputs() -> RankingIdentityInputs:
    return RankingIdentityInputs(
        case_theory_version_id=None, model_provider="mistral",
        model_endpoint="https://api.mistral.ai/v1", model_name="mistral-small-latest",
        prompt_version="cascade-question-v1", temperature=0.0, sampling={"top_p": 1.0},
        embedder_model_id="bge-m3", embedder_model_version="1.5",
        chunking_config_version="chunk-v1", schema_version="slice-a")


def _ranked_matter(tmp_path: Path, monkeypatch, *, with_line: bool = True):  # noqa: ANN201
    """A real matter: a corpus, a taxonomy, a ranking and (by default) a committed line."""
    store = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, ADMIN, "motdepasse", "Me Durand", {WALL}, is_admin=True)
    folder = tmp_path / "dossier"
    folder.mkdir()
    for name, text in _FILES.items():
        (folder / name).write_text(text, encoding="utf-8")
    client = TestClient(app)
    _login(client, ADMIN, pw="motdepasse")
    client.post("/api/ingest", json={"folder": str(folder), "matter": MATTER, "scope": WALL})
    store.set_config(TENANT, "admin", "taxonomy", _TAXONOMY)
    pieces = [pid for pid, _ in store.representatives(MATTER, TENANT, {WALL})]
    units = [CascadeUnit(piece_id=p, text=p, chunk_ids=("c",)) for p in pieces]
    produce_ranking(
        units, case_theory=None,
        scorer=FakeScorer({p: 0.95 - 0.2 * i for i, p in enumerate(pieces)}),
        judge=FixedJudge(), config=_cfg(), inputs=_inputs(), tenant=TENANT, matter=MATTER,
        actor="me.durand", scopes={WALL}, recorder=store)
    if with_line:
        place_line(store, tenant=TENANT, matter=MATTER, actor="me.durand", scopes={WALL})
    return store, client


def _table(client: TestClient) -> dict:
    r = client.get(f"/api/matters/{MATTER}/triage-table")
    assert r.status_code == 200, r.text
    return r.json()


def _set_label(client: TestClient, piece_id: str, label: str, **body: object):  # noqa: ANN201
    return client.put(
        f"/api/matters/{MATTER}/pieces/{piece_id}/label", json={"label": label, **body})


# ── AC-5 — the surface tells the truth about what it is ──────────────────────────────────────────
def test_the_table_names_its_ranking_version_and_partitions_the_matter(
    tmp_path: Path, monkeypatch
) -> None:
    _store, client = _ranked_matter(tmp_path, monkeypatch)
    body = _table(client)
    assert body["version_no"] >= 1 and body["version_id"]           # AD-23 — never unqualified
    assert body["basis"] and body["created_at"]
    total = body["retained_count"] + body["discarded_count"] + body["unscored_count"]
    assert total == body["corpus_count"] == len(body["rows"])       # the equation is true (FR-16)
    assert body["taxonomy"] == _TAXONOMY                            # the select's only options
    sides = {r["side"] for r in body["rows"]}
    assert sides <= {"retained", "discarded", "unscored", "unsplit"}


def test_the_line_is_named_by_a_piece_never_by_a_bare_integer(tmp_path: Path, monkeypatch) -> None:
    _store, client = _ranked_matter(tmp_path, monkeypatch)
    line = _table(client)["line"]
    assert line["placed"] is True
    assert line["last_retained_piece_id"]          # the IDENTITY is what the line is stored by
    assert line["basis"]                           # and it states what it was founded on (FR-17)


def test_an_unplaced_line_is_an_honest_state_not_a_line_at_rank_zero(
    tmp_path: Path, monkeypatch
) -> None:
    _store, client = _ranked_matter(tmp_path, monkeypatch, with_line=False)
    body = _table(client)
    assert body["line"]["placed"] is False and body["line"]["last_retained_piece_id"] is None
    # with no cut, nothing is retained or discarded: the ranked rows are UNSPLIT, a fourth honest
    # state. Calling them "écartées" would be exactly the lie FR-16 forbids.
    assert body["retained_count"] == 0 and body["discarded_count"] == 0
    assert body["unsplit_count"] == len(body["rows"]) - body["unscored_count"]
    assert {r["side"] for r in body["rows"]} <= {"unsplit", "unscored"}


def test_confidence_is_read_only_and_a_missing_one_is_shown_as_not_derived(
    tmp_path: Path, monkeypatch
) -> None:
    _store, client = _ranked_matter(tmp_path, monkeypatch)
    for row in _table(client)["rows"]:
        # FR-42/AD-19: the flag says whether a number exists; it is never imputed as 0
        assert row["confidence_derived"] == (row["confidence"] is not None)
        assert "confidence" not in {k for k in row if k.startswith("set_")}


def test_no_route_can_set_a_cote(tmp_path: Path, monkeypatch) -> None:
    """AC-5: the côté is a derived VIEW (AD-39). There is no endpoint that stores one, and sending
    a side to the label endpoint changes nothing about it."""
    _store, client = _ranked_matter(tmp_path, monkeypatch)
    before = _table(client)
    row = before["rows"][0]
    _set_label(client, row["piece_id"], "Contrats", side="retained")
    after = _table(client)
    assert {r["piece_id"]: r["side"] for r in after["rows"]} == \
           {r["piece_id"]: r["side"] for r in before["rows"]}
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert not any("side" in p or "cote" in p for p in paths)


# ── AC-1 — an edit changes that cell and nothing else ────────────────────────────────────────────
def test_n_edits_across_n_rows_all_hold(tmp_path: Path, monkeypatch) -> None:
    """The named requirement that turned out to be the architecture's invariant (FR-20)."""
    _store, client = _ranked_matter(tmp_path, monkeypatch)
    before = _table(client)
    chosen = {r["piece_id"]: _TAXONOMY[i % len(_TAXONOMY)]
              for i, r in enumerate(before["rows"])}
    for piece_id, label in chosen.items():                       # N edits, one row at a time
        r = _set_label(client, piece_id, label)
        assert r.status_code == 200, r.text
    after = _table(client)
    got = {r["piece_id"]: r["label"] for r in after["rows"]}
    assert got == chosen                                          # ALL N values hold
    assert all(r["label_source"] == "human" for r in after["rows"])
    # and nothing else moved: same order, same ranks, same sides, same confidences
    assert [r["piece_id"] for r in after["rows"]] == [r["piece_id"] for r in before["rows"]]
    for a, b in zip(after["rows"], before["rows"], strict=True):
        assert (a["rank"], a["side"], a["confidence"]) == (b["rank"], b["side"], b["confidence"])
    assert after["version_no"] == before["version_no"]            # no edit re-ranked anything


def test_editing_one_row_does_not_touch_another_rows_log(tmp_path: Path, monkeypatch) -> None:
    _store, client = _ranked_matter(tmp_path, monkeypatch)
    rows = _table(client)["rows"]
    first, second = rows[0]["piece_id"], rows[1]["piece_id"]
    _set_label(client, first, "Contrats")
    log = client.get(f"/api/matters/{MATTER}/pieces/{second}/label/log").json()["entries"]
    assert log == []                                              # untouched pièce, empty log


# ── AC-3 — the change log beside the row, immediately ────────────────────────────────────────────
def test_an_edit_returns_its_change_log_entry_with_previous_new_author_and_time(
    tmp_path: Path, monkeypatch
) -> None:
    _store, client = _ranked_matter(tmp_path, monkeypatch)
    piece = _table(client)["rows"][0]["piece_id"]
    body = _set_label(client, piece, "Contrats").json()
    assert body["seq"] == 1
    entry = body["entries"][-1]                                   # returned WITH the write (FR-20)
    assert entry["previous"] == "unlabelled"       # never null — a value, not an absence
    assert entry["label"] == "Contrats"
    assert entry["set_by"] == "Me Durand" and entry["at"]   # the lawyer's NAME, not an email
    assert entry["source"] == "human"
    second = _set_label(client, piece, "Jurisprudence").json()["entries"][-1]
    assert (second["previous"], second["label"]) == ("Contrats", "Jurisprudence")


def test_the_matter_level_log_carries_every_row_newest_first(tmp_path: Path, monkeypatch) -> None:
    _store, client = _ranked_matter(tmp_path, monkeypatch)
    rows = _table(client)["rows"]
    for row in rows[:3]:
        _set_label(client, row["piece_id"], "Contrats")
    entries = client.get(f"/api/matters/{MATTER}/change-log").json()["entries"]
    assert len(entries) == 3
    assert {e["piece_id"] for e in entries} == {r["piece_id"] for r in rows[:3]}
    assert [e["at"] for e in entries] == sorted((e["at"] for e in entries), reverse=True)


def test_a_revert_appends_a_new_entry_and_never_erases_the_one_it_reverts(
    tmp_path: Path, monkeypatch
) -> None:
    _store, client = _ranked_matter(tmp_path, monkeypatch)
    piece = _table(client)["rows"][0]["piece_id"]
    _set_label(client, piece, "Contrats")
    _set_label(client, piece, "Correspondance")
    body = client.post(
        f"/api/matters/{MATTER}/pieces/{piece}/label/revert", json={"to_seq": 1}).json()
    assert body["seq"] == 3                                       # a NEW entry, not a rewrite
    labels = [e["label"] for e in body["entries"]]
    assert labels == ["Contrats", "Correspondance", "Contrats"]   # the whole history stays readable


# ── AC-6 — a refusal loses nothing ───────────────────────────────────────────────────────────────
def test_an_out_of_taxonomy_label_is_refused_and_the_cell_is_unchanged(
    tmp_path: Path, monkeypatch
) -> None:
    _store, client = _ranked_matter(tmp_path, monkeypatch)
    piece = _table(client)["rows"][0]["piece_id"]
    r = _set_label(client, piece, "Une catégorie inventée")
    assert r.status_code == 422                                   # can never leak (FR-40)
    assert _table(client)["rows"][0]["label"] == "unlabelled"


def test_a_stale_expected_seq_is_refused_so_an_edit_never_silently_overwrites(
    tmp_path: Path, monkeypatch
) -> None:
    _store, client = _ranked_matter(tmp_path, monkeypatch)
    piece = _table(client)["rows"][0]["piece_id"]
    _set_label(client, piece, "Contrats")                         # someone edits (seq 1)
    r = _set_label(client, piece, "Jurisprudence", expected_seq=0)  # a client holding a stale view
    assert r.status_code == 409
    assert _table(client)["rows"][0]["label"] == "Contrats"       # the committed value stands


def test_two_writers_who_both_saw_an_unlabelled_row_do_not_silently_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    """The review's confirmed high finding. Every row starts never-labelled, so its `label_seq`
    reads back null; a client that forwards that null disarms the conditional commit for exactly
    the first edit of every row and the second writer wins in silence. The client now sends 0 —
    this codebase's "I observed no entries" — and the guard arms from the very first edit."""
    _store, client = _ranked_matter(tmp_path, monkeypatch)
    piece = _table(client)["rows"][0]["piece_id"]
    first = _set_label(client, piece, "Contrats", expected_seq=0)
    second = _set_label(client, piece, "Jurisprudence", expected_seq=0)   # a second stale view
    assert first.status_code == 200 and second.status_code == 409
    assert _table(client)["rows"][0]["label"] == "Contrats"   # the first writer's value stands


def test_a_label_write_for_a_piece_not_in_the_matter_is_refused_and_writes_nothing(
    tmp_path: Path, monkeypatch
) -> None:
    """The review's confirmed medium finding. The ledger has no foreign key to `piece` (AD-7 forbids
    the cascade one would invite), so an unchecked identifier at the HTTP boundary would become a
    permanent, undeletable row naming a pièce that never existed — visible in the matter's change
    log, an evidential surface."""
    _store, client = _ranked_matter(tmp_path, monkeypatch)
    for phantom in ("pas-une-piece", "x" * 200):
        r = client.put(f"/api/matters/{MATTER}/pieces/{phantom}/label", json={"label": "Contrats"})
        assert r.status_code == 404, f"{phantom} -> {r.status_code}"
        assert r.json()["detail"] == "dossier introuvable"          # non-disclosing (FR-14)
    # a traversal-shaped identifier never reaches the handler at all (the router normalises it)
    traversal = client.put(
        f"/api/matters/{MATTER}/pieces/../../etc/passwd/label", json={"label": "Contrats"})
    assert 400 <= traversal.status_code < 500
    revert = client.post(
        f"/api/matters/{MATTER}/pieces/pas-une-piece/label/revert", json={"to_seq": 1})
    assert revert.status_code == 404
    assert client.get(f"/api/matters/{MATTER}/change-log").json()["entries"] == []


def test_a_matter_outside_the_wall_is_the_same_404_as_an_absent_one(
    tmp_path: Path, monkeypatch
) -> None:
    store, client = _ranked_matter(tmp_path, monkeypatch)
    store.create_user(TENANT, "autre@cab.fr", "motdepasse", "Me Autre", {"wall-b"})
    _login(client, "autre@cab.fr", pw="motdepasse")
    outside = client.get(f"/api/matters/{MATTER}/triage-table")
    absent = client.get("/api/matters/dossier-qui-n-existe-pas/triage-table")
    assert outside.status_code == absent.status_code == 404
    assert outside.json()["detail"] == absent.json()["detail"]     # indistinguishable (FR-14)
    assert client.put(
        f"/api/matters/{MATTER}/pieces/x/label", json={"label": "Contrats"}).status_code == 404


def test_a_matter_with_no_ranking_yet_is_a_state_not_an_empty_table(
    tmp_path: Path, monkeypatch
) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, ADMIN, "motdepasse", "Me Durand", {WALL}, is_admin=True)
    folder = tmp_path / "d"
    folder.mkdir()
    (folder / "a.txt").write_text("une pièce", encoding="utf-8")
    client = TestClient(app)
    _login(client, ADMIN, pw="motdepasse")
    client.post("/api/ingest", json={"folder": str(folder), "matter": MATTER, "scope": WALL})
    # never an empty table pretending to be a result — the client renders its own honest state
    assert client.get(f"/api/matters/{MATTER}/triage-table").status_code == 404


@pytest.fixture(autouse=True)
def _no_cached_store():  # noqa: ANN202
    app_module._store.cache_clear()
    yield
    app_module._store.cache_clear()
