"""Freshness and staleness of derived artefacts, over HTTP (Story 4.13, FR-58/AD-23/AD-40).

The property AD-23 exists for: *"300 pièces arrive, the sentence still reads '1 400 in the discarded
set', nothing is marked stale and it remains exportable as current."* Every test here moves ONE
input through the product's own existing seam — never through anything that knows freshness exists —
and asserts the artefact reads stale, names that input, and is refused as current.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apx.api.app import app
from apx.core.app.line import move_line, place_line
from apx.core.app.pin import pin_piece
from apx.core.app.rank import produce_ranking
from apx.core.domain.cascade import CascadeUnit
from apx.core.domain.config import CascadeConfig
from apx.core.domain.freshness import TRIGGER_KEYS
from apx.core.domain.ranking import RankingIdentityInputs
from apx.core.domain.triage import Label, PieceLabel, TriageOutcome
from apx.core.domain.triage_sets import PinSide
from tests.api.test_ingest_api import _login, _prepare, _reset_state  # noqa: F401 — autouse
from tests.scoring_fakes import FakeScorer, FixedJudge

TENANT, WALL, MATTER = "t", "wall", "m"
ADMIN = "admin@cab.fr"
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


def _rank(store, client: TestClient):  # noqa: ANN001,ANN202
    pieces = [pid for pid, _ in store.representatives(MATTER, TENANT, {WALL})]
    produce_ranking(
        [CascadeUnit(piece_id=p, text=p, chunk_ids=("c",)) for p in pieces],
        case_theory=None,
        scorer=FakeScorer({p: 0.95 - 0.2 * i for i, p in enumerate(pieces)}),
        judge=FixedJudge(), config=_cfg(), inputs=_inputs(), tenant=TENANT, matter=MATTER,
        actor="me.durand", scopes={WALL}, recorder=store)
    return pieces


def _ranked_matter(tmp_path: Path, monkeypatch, *, with_line: bool = True):  # noqa: ANN201
    """A real matter with a real corpus, a ranking, and (by default) a committed line."""
    store = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, ADMIN, "motdepasse", "Me Durand", {WALL}, is_admin=True)
    folder = tmp_path / "dossier"
    folder.mkdir()
    for name, text in _FILES.items():
        (folder / name).write_text(text, encoding="utf-8")
    client = TestClient(app)
    _login(client, ADMIN, pw="motdepasse")
    client.post("/api/ingest", json={"folder": str(folder), "matter": MATTER, "scope": WALL})
    pieces = _rank(store, client)
    if with_line:
        place_line(store, tenant=TENANT, matter=MATTER, actor="me.durand", scopes={WALL})
    return store, client, pieces


def _record_bound(store, client: TestClient) -> str:
    """Record a real confidence bound over the matter's discard pile, through the product's own
    act. Returns its artefact id."""
    reps = store.representatives(MATTER, TENANT, {WALL})
    store.save_labels(
        MATTER, TENANT, {WALL},
        TriageOutcome(tuple(PieceLabel(pid, Label.DISCARD, "écartée") for pid, _ in reps)),
        "criteria", actor="seed")
    sample = client.get(
        f"/api/matters/{MATTER}/recall/sample", params={"n": 2}).json()["sample"]
    r = client.post(f"/api/matters/{MATTER}/recall/review", json={
        "verdicts": [{"piece_id": s["piece_id"], "relevant": False} for s in sample],
        "confidence": 0.95})
    assert r.status_code == 200, r.text
    bound = client.get(f"/api/matters/{MATTER}/bound")
    assert bound.status_code == 200, bound.text
    return bound.json()["artefact_id"]


def _freshness(client: TestClient) -> list[dict]:
    r = client.get(f"/api/matters/{MATTER}/freshness")
    assert r.status_code == 200, r.text
    return r.json()


def _worklist(client: TestClient) -> list[dict]:
    r = client.get(f"/api/matters/{MATTER}/worklist")
    assert r.status_code == 200, r.text
    return r.json()


def _of(assessments: list[dict], kind: str) -> dict:
    matching = [a for a in assessments if a["kind"] == kind]
    assert matching, f"no {kind} artefact was stamped: {assessments}"
    return matching[-1]


def _import_more(client: TestClient, tmp_path: Path, *, names: tuple[str, ...]) -> None:
    """Ingest more pièces into the SAME matter, through the product's own ingest route."""
    second = tmp_path / "arrivage"
    second.mkdir(exist_ok=True)
    for i, name in enumerate(names):
        (second / name).write_text(f"Pièce arrivée après le classement n°{i}.", encoding="utf-8")
    r = client.post(
        "/api/ingest", json={"folder": str(second), "matter": MATTER, "scope": WALL})
    assert r.status_code == 200, r.text


# ── AC-1 — every trigger marks it stale, and names itself ───────────────────────────────────────
def test_a_freshly_produced_artefact_is_fresh_and_names_nothing(
    tmp_path: Path, monkeypatch
) -> None:
    _store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    assessments = _freshness(client)
    assert assessments, "producing a ranking and a line must stamp them"
    assert all(a["fresh"] for a in assessments), assessments
    assert all(a["changed"] == [] for a in assessments)
    assert _worklist(client) == []          # a fresh artefact is not work


def test_a_new_ranking_version_makes_the_earlier_one_stale(tmp_path: Path, monkeypatch) -> None:
    store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    first = _of(_freshness(client), "ranking")["artefact_id"]
    _rank(store, client)                     # an explicit re-rank — a NEW version beside the old
    after = {a["artefact_id"]: a for a in _freshness(client)}
    assert after[first]["fresh"] is False
    assert "ranking_version_no" in after[first]["changed"]
    assert "nouveau classement" in " ".join(after[first]["changed_fr"])


def test_a_line_move_makes_the_earlier_placement_and_the_bound_stale(
    tmp_path: Path, monkeypatch
) -> None:
    store, client, pieces = _ranked_matter(tmp_path, monkeypatch)
    bound_id = _record_bound(store, client)
    current = store.read_current_line(tenant=TENANT, matter=MATTER, scopes={WALL})
    target = next(p for p in pieces if p != current.last_retained_piece_id)
    priced = store.price_line_move(
        tenant=TENANT, matter=MATTER, scopes={WALL}, candidate_last_retained_piece_id=target)
    move_line(
        store, tenant=TENANT, matter=MATTER, actor="me.durand", scopes={WALL},
        last_retained_piece_id=target, expected_seq=current.seq,
        priced_statement=f"{priced.pieces_to_read_delta:+d} pièces à lire")
    after = {a["artefact_id"]: a for a in _freshness(client)}
    assert "line_seq" in after[bound_id]["changed"]           # the population's cut moved (FR-58)
    first_placement = next(
        a for a in after.values() if a["kind"] == "line" and not a["fresh"])
    assert "line_seq" in first_placement["changed"]           # superseded by the new placement
    # and the ranked ORDER is untouched: place/move write only the placement ledger, so telling
    # the lawyer her classement is out of date here would be false.
    assert _of([a for a in after.values()], "ranking")["fresh"] is True


def test_a_pin_makes_the_bound_stale_and_leaves_the_order_alone(
    tmp_path: Path, monkeypatch
) -> None:
    store, client, pieces = _ranked_matter(tmp_path, monkeypatch)
    bound_id = _record_bound(store, client)
    pin_piece(store, tenant=TENANT, matter=MATTER, actor="me.durand", piece_id=pieces[-1],
              side=PinSide.RETAIN, reason="pièce décisive", scopes={WALL})
    after = {a["artefact_id"]: a for a in _freshness(client)}
    # FR-58/PRD §pin: "a pin marks any existing confidence bound stale, because it changed the
    # population the draw was over".
    assert "pin_ledger_seq" in after[bound_id]["changed"]
    # but a pin moves exactly one pièce across the line (FR-43) — it changes neither the order
    # nor the cut, so neither is claimed stale.
    assert _of(list(after.values()), "ranking")["fresh"] is True


def test_a_case_theory_revision_makes_the_ranking_stale(tmp_path: Path, monkeypatch) -> None:
    _store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    r = client.put(f"/api/matters/{MATTER}/case-theory", json={"text": "Le bail est nul."})
    assert r.status_code == 200, r.text
    changed = _of(_freshness(client), "ranking")["changed"]
    assert "case_theory_version_no" in changed


def test_a_configuration_change_affecting_ranking_makes_it_stale(
    tmp_path: Path, monkeypatch
) -> None:
    _store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    r = client.put("/api/admin/config/similarity_threshold", json={"value": 0.42})
    assert r.status_code == 200, r.text
    assert "config_digest" in _of(_freshness(client), "ranking")["changed"]


def test_a_configuration_change_that_does_not_affect_ranking_does_not(
    tmp_path: Path, monkeypatch
) -> None:
    # The trigger is "a configuration change affecting retrieval, ranking or the estimator" — not
    # ANY configuration change. A staleness that fires on the interface language would train the
    # user to ignore the banner, which is how an honest signal becomes noise.
    _store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    r = client.put("/api/admin/config/backup_interval_hours", json={"value": 12})
    assert r.status_code == 200, r.text
    assert all(a["fresh"] for a in _freshness(client))


def test_a_scope_change_makes_the_artefacts_stale(tmp_path: Path, monkeypatch) -> None:
    store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    admin_id = next(u.id for u in store.list_users(TENANT) if u.email == ADMIN)
    store.grant_scope(TENANT, "admin", admin_id, "mur-2")
    _login(client, ADMIN, pw="motdepasse")     # the grant reaps the session (AD-15)
    r = client.post(f"/api/admin/matters/{MATTER}/rescope", json={"scope": "mur-2"})
    assert r.status_code == 200, r.text
    assert "scope_identity" in _of(_freshness(client), "ranking")["changed"]


def test_an_ingestion_into_a_ranked_matter_makes_the_ranking_stale(
    tmp_path: Path, monkeypatch
) -> None:
    # FR-58's headline case, and the one that was invisible before this story.
    _store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    _import_more(client, tmp_path, names=("nouvelle-1.txt", "nouvelle-2.txt"))
    assessment = _of(_freshness(client), "ranking")
    assert assessment["fresh"] is False
    assert "corpus_count" in assessment["changed"]
    assert "importation" in " ".join(assessment["changed_fr"])


def test_a_re_extraction_of_a_piece_makes_the_ranking_stale(tmp_path: Path, monkeypatch) -> None:
    # AD-40's eighth trigger. Re-extraction has no route yet, so the input is moved at the column
    # it is observed at — which is the point: the observable is the pièce's text identity, so ANY
    # future re-extraction path is covered without anyone remembering to wire it.
    from apx.adapters.store_postgres.models import Piece

    store, client, pieces = _ranked_matter(tmp_path, monkeypatch)
    before = _freshness(client)
    assert all(a["fresh"] for a in before)
    with store._sf() as session, session.begin():
        row = session.get(Piece, pieces[1])
        row.text_identity = "9" * 64          # the same pièce, read again, different text identity
    assessment = _of(_freshness(client), "ranking")
    assert assessment["fresh"] is False
    assert assessment["changed"] == ["extraction_digest"]   # and ONLY that: the count did not move
    assert "ré-extraction" in " ".join(assessment["changed_fr"])


@pytest.mark.parametrize("key", TRIGGER_KEYS)
def test_every_enumerated_trigger_has_a_test_here(key: str) -> None:
    """The eight triggers of FR-58/AD-23 each have a named test above. This asserts the mapping is
    complete: a trigger added to the domain with no test here fails the build."""
    covered = {
        "ranking_version_no": "test_a_new_ranking_version_makes_the_earlier_one_stale",
        "line_seq": "test_a_line_move_makes_the_earlier_placement_and_the_bound_stale",
        "pin_ledger_seq": "test_a_pin_makes_the_bound_stale_and_leaves_the_order_alone",
        "case_theory_version_no": "test_a_case_theory_revision_makes_the_ranking_stale",
        "config_digest": "test_a_configuration_change_affecting_ranking_makes_it_stale",
        "scope_identity": "test_a_scope_change_makes_the_artefacts_stale",
        "corpus_count": "test_an_ingestion_into_a_ranked_matter_makes_the_ranking_stale",
        "extraction_digest": "test_a_re_extraction_of_a_piece_makes_the_ranking_stale",
        "discard_population": "test_a_re_judge_makes_the_bound_stale_and_unexportable",
    }
    assert key in covered, f"trigger {key!r} has no test in this file (FR-58)"
    assert covered[key] in globals()


# ── AC-2 — a comparison, not a flag: nothing has to remember ────────────────────────────────────
def test_the_writer_that_moved_the_input_never_touched_freshness(
    tmp_path: Path, monkeypatch
) -> None:
    """The ingest route knows nothing about staleness — it imports pièces. The ranking still reads
    stale, because staleness is a COMPARISON of stamps and not a flag someone sets."""
    store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    stamps_before = store.read_artefact_stamps(tenant=TENANT, matter=MATTER, scopes={WALL})
    _import_more(client, tmp_path, names=("silencieuse.txt",))
    stamps_after = store.read_artefact_stamps(tenant=TENANT, matter=MATTER, scopes={WALL})
    assert stamps_after == stamps_before        # nothing was written to announce the staleness
    assert _of(_freshness(client), "ranking")["fresh"] is False


def test_a_produced_artefact_carries_a_stamp_it_cannot_be_produced_without(
    tmp_path: Path, monkeypatch
) -> None:
    store, _client, _ = _ranked_matter(tmp_path, monkeypatch)
    stamps = store.read_artefact_stamps(tenant=TENANT, matter=MATTER, scopes={WALL})
    kinds = {kind for kind, _, _, _, _ in stamps}
    assert kinds == {"ranking", "line"}
    for _kind, _aid, version_no, superseded, stamp in stamps:
        assert superseded is False                  # nothing has replaced them
        assert version_no == 1                      # each names the version it belongs to
        assert set(stamp.to_json()) and stamp.corpus_count == len(_FILES)


# ── AC-3 — never resolved by time, a background job, or being viewed ────────────────────────────
def test_reading_a_stale_artefact_five_times_leaves_it_stale(tmp_path: Path, monkeypatch) -> None:
    _store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    _import_more(client, tmp_path, names=("encore.txt",))
    verdicts = [tuple(_of(_freshness(client), "ranking")["changed"]) for _ in range(5)]
    assert verdicts == [("corpus_count",)] * 5      # identical every time — no drift, no expiry
    assert len(_worklist(client)) >= 1


def test_a_re_rank_produces_a_new_artefact_and_leaves_the_old_one_stale(
    tmp_path: Path, monkeypatch
) -> None:
    """FR-58: staleness is resolved by an explicit recomputation producing a NEW artefact — never
    by refreshing the old one. The old version stays readable and stays stale."""
    store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    old_id = _of(_freshness(client), "ranking")["artefact_id"]
    _import_more(client, tmp_path, names=("apres.txt",))
    assert not _of(_freshness(client), "ranking")["fresh"]
    _rank(store, client)                                     # the explicit, user-initiated act
    after = {a["artefact_id"]: a for a in _freshness(client) if a["kind"] == "ranking"}
    assert len(after) == 2                                   # a NEW artefact beside the old
    assert after[old_id]["fresh"] is False                    # the old one was NOT refreshed
    new_id = next(aid for aid in after if aid != old_id)
    assert after[new_id]["fresh"] is True                     # the new one is fresh by production
    # and the old version is still fully readable — nothing was overwritten (AD-7)
    r = client.get(f"/api/matters/{MATTER}/triage-table", params={"version": 1})
    assert r.status_code == 200


# ── AC-4 — the unranked count, stated wherever the sets are counted ─────────────────────────────
def test_pieces_imported_after_the_ranking_are_unranked_not_discarded(
    tmp_path: Path, monkeypatch
) -> None:
    """The 4.10 review's deferred finding, paid. Rank, then import: the dossier grew, the ranking
    did not, and the surface says so instead of letting the new pièces vanish."""
    _store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    before = client.get(f"/api/matters/{MATTER}/triage-table").json()
    assert before["unranked_count"] == 0
    _import_more(client, tmp_path, names=("tardive-1.txt", "tardive-2.txt", "tardive-3.txt"))
    body = client.get(f"/api/matters/{MATTER}/triage-table").json()
    assert body["ranked_count"] == before["ranked_count"]           # the ranking did not change
    assert body["corpus_count"] == before["corpus_count"] + 3       # the dossier did
    assert body["unranked_count"] == 3
    # they are in NEITHER set — not folded into the discarded pile (AD-19/FR-16)
    total = body["retained_count"] + body["discarded_count"] + body["unscored_count"]
    assert total == body["ranked_count"]
    assert len(body["rows"]) == body["ranked_count"]


def test_the_denominator_equation_holds_both_ways(tmp_path: Path, monkeypatch) -> None:
    _store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    _import_more(client, tmp_path, names=("x.txt",))
    b = client.get(f"/api/matters/{MATTER}/triage-table").json()
    assert b["ranked_count"] + b["unranked_count"] == b["corpus_count"]
    assert (b["retained_count"] + b["discarded_count"] + b["unscored_count"]
            + b["unsplit_count"] == b["ranked_count"])


# ── AC-6 — the worklist offers, and reading it acts on nothing ──────────────────────────────────
def test_an_ingestion_generates_a_worklist_line_offering_a_re_rank(
    tmp_path: Path, monkeypatch
) -> None:
    _store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    _import_more(client, tmp_path, names=("nouvelle.txt",))
    lines = _worklist(client)
    ranking = [line for line in lines if line["kind"] == "ranking"]
    assert ranking, lines
    assert ranking[0]["offer"] == "re-rank"
    assert "corpus_count" in ranking[0]["changed"]
    assert "Re-classer" in ranking[0]["offer_fr"]


def test_reading_the_worklist_starts_nothing_and_leaves_the_staleness(
    tmp_path: Path, monkeypatch
) -> None:
    store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    _import_more(client, tmp_path, names=("nouvelle.txt",))
    before = store.read_artefact_stamps(tenant=TENANT, matter=MATTER, scopes={WALL})
    for _ in range(3):
        assert _worklist(client)
    assert store.read_artefact_stamps(tenant=TENANT, matter=MATTER, scopes={WALL}) == before
    assert not _of(_freshness(client), "ranking")["fresh"]   # reading did not resolve it


def test_an_empty_worklist_is_a_read_result_and_an_unreadable_one_is_a_404(
    tmp_path: Path, monkeypatch
) -> None:
    _store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    assert _worklist(client) == []                                    # read, nothing stale
    assert client.get("/api/matters/inconnu/worklist").status_code == 404
    assert client.get("/api/matters/inconnu/freshness").status_code == 404


# ── FR-14 — out of scope and absent are the same non-disclosing answer ──────────────────────────
def test_out_of_scope_and_absent_are_indistinguishable(tmp_path: Path, monkeypatch) -> None:
    store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    store.create_user(TENANT, "autre@cab.fr", "motdepasse", "Autre", {"mur-3"}, is_admin=False)
    other = TestClient(app)
    _login(other, "autre@cab.fr", pw="motdepasse")
    for path in ("freshness", "worklist", "bound"):
        held = other.get(f"/api/matters/{MATTER}/{path}")
        absent = other.get(f"/api/matters/nexistepas/{path}")
        assert held.status_code == absent.status_code == 404
        assert held.json() == absent.json()      # byte-identical: the answer discloses nothing


# ── AC-5 — a stale bound cannot be exported as current, nor copied without its staleness ────────
def test_a_fresh_bound_exports_and_the_export_is_audited(tmp_path: Path, monkeypatch) -> None:
    store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    _record_bound(store, client)
    r = client.get(f"/api/matters/{MATTER}/bound/export")
    assert r.status_code == 200, r.text
    assert r.json()["exportable_as_current"] is True
    trail = client.get(f"/api/matters/{MATTER}/audit").json()
    assert any(e["action"] == "export-bound" for e in trail["entries"]), trail


def test_a_stale_bound_is_refused_as_current_and_the_refusal_writes_nothing(
    tmp_path: Path, monkeypatch
) -> None:
    """FR-58, and the PRD's 'blocking, not warning': a qualified export of a false number is still
    a false number in a bundle."""
    store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    _record_bound(store, client)
    _import_more(client, tmp_path, names=("tardive.txt",))       # the population grew underneath it
    before = len(client.get(f"/api/matters/{MATTER}/audit").json()["entries"])
    r = client.get(f"/api/matters/{MATTER}/bound/export")
    assert r.status_code == 409
    assert "périmé" in r.json()["detail"]
    assert "importation" in r.json()["detail"]                    # it NAMES what moved
    after = client.get(f"/api/matters/{MATTER}/audit").json()["entries"]
    assert len(after) == before                                   # a refusal is not an export
    assert not any(e["action"] == "export-bound" for e in after)


def test_the_copy_string_carries_the_staleness(tmp_path: Path, monkeypatch) -> None:
    store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    _record_bound(store, client)
    fresh = client.get(f"/api/matters/{MATTER}/bound").json()
    assert "à jour" in fresh["copy_text"] and "pertinentes" in fresh["copy_text"]
    _import_more(client, tmp_path, names=("tardive.txt",))
    stale = client.get(f"/api/matters/{MATTER}/bound").json()
    # FR-58: it "cannot be copied as text without its staleness in the copied string". The server
    # composes the sentence, so there is no branch that produces the number without its freshness.
    assert stale["exportable_as_current"] is False
    assert "périmé" in stale["copy_text"]
    assert "importation dans le dossier" in stale["copy_text"]
    assert str(stale["count_upper"]) in stale["copy_text"]        # the number is still in it


def test_a_bound_with_no_stamp_is_unverifiable_not_fresh(tmp_path: Path, monkeypatch) -> None:
    """A bound recorded before this story carries no stamp. That is an absence of evidence, not
    evidence of freshness — so it reads unverifiable and is refused as current."""
    from apx.adapters.store_postgres.models import ArtefactStamp

    store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    artefact_id = _record_bound(store, client)
    with store._sf() as session, session.begin():   # simulate the pre-4.13 bound
        session.query(ArtefactStamp).filter(
            ArtefactStamp.artefact_id == artefact_id).delete()
    body = client.get(f"/api/matters/{MATTER}/bound").json()
    assert body["freshness"] is None
    assert body["exportable_as_current"] is False
    assert "invérifiable" in body["status_fr"] and "invérifiable" in body["copy_text"]
    assert client.get(f"/api/matters/{MATTER}/bound/export").status_code == 409


def test_no_bound_recorded_is_its_own_state_not_a_bound_of_zero(
    tmp_path: Path, monkeypatch
) -> None:
    _store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    assert client.get(f"/api/matters/{MATTER}/bound").status_code == 404
    assert client.get(f"/api/matters/{MATTER}/bound/export").status_code == 404


# ── the artefact is compared against ITS OWN version, never the latest ──────────────────────────
def _move(store, version_no: int, avoid: str, pieces) -> None:  # noqa: ANN001
    """Move the line of ONE ranking version to some other pièce, through the real act."""
    current = store.read_current_line(
        tenant=TENANT, matter=MATTER, scopes={WALL}, version_no=version_no)
    target = next(p for p in pieces if p != current.last_retained_piece_id and p != avoid)
    priced = store.price_line_move(
        tenant=TENANT, matter=MATTER, scopes={WALL},
        candidate_last_retained_piece_id=target, version_no=version_no)
    move_line(
        store, tenant=TENANT, matter=MATTER, actor="me.durand", scopes={WALL},
        last_retained_piece_id=target, expected_seq=current.seq,
        priced_statement=f"{priced.pieces_to_read_delta:+d} pièces à lire", version_no=version_no)


def test_a_line_on_an_older_version_is_assessed_against_that_version_not_the_latest(
    tmp_path: Path, monkeypatch
) -> None:
    """A placement may be made over a ranking version that is NOT the latest. Its `line_seq`
    observable then belongs to that version, while the stamp's `ranking_version_no` observable is
    the *matter*'s maximum — a different number. Comparing the placement against the LATEST
    version's cut reads it FRESH while its own cut has moved twice underneath it: the catastrophic
    direction AD-23 is written for. So the assessment resolves each artefact's own version from the
    artefact itself.

    Verified as a regression: replacing `own_version_no` with `recorded.ranking_version_no` in
    `read_freshness` makes the final assertion below fail (fresh instead of stale)."""
    store, client, pieces = _ranked_matter(tmp_path, monkeypatch)          # v1 + a line on v1
    _rank(store, client)                                                   # v2
    place_line(store, tenant=TENANT, matter=MATTER, actor="me.durand", scopes={WALL})  # line on v2
    before = {a["artefact_id"] for a in _freshness(client) if a["kind"] == "line"}

    _move(store, 1, avoid="", pieces=pieces)          # v1 seq -> 2   (the artefact under test)
    moved_on_v1 = next(
        a["artefact_id"] for a in _freshness(client)
        if a["kind"] == "line" and a["artefact_id"] not in before)

    _move(store, 2, avoid="", pieces=pieces)          # v2 seq -> 2   (the decoy: same seq number)
    _move(store, 1, avoid="", pieces=pieces)          # v1 seq -> 3   (v1's own cut moves again)

    after = {a["artefact_id"]: a for a in _freshness(client)}
    # v1's seq is now 3; v2's is 2. The artefact under test recorded 2. Compared against ITS OWN
    # version it is stale; compared against the latest version it would coincide and read fresh.
    assert after[moved_on_v1]["fresh"] is False
    assert "line_seq" in after[moved_on_v1]["changed"]


def test_changing_where_the_line_falls_makes_the_placed_line_stale(
    tmp_path: Path, monkeypatch
) -> None:
    """`line_retain_bands` decides where the recommended cut falls (Story 4.8). A firm that widens
    or narrows the retain policy has changed an input to every placed line — FR-58's "configuration
    change affecting retrieval, ranking or the estimator" — so the line must not keep reading
    fresh."""
    _store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    assert all(a["fresh"] for a in _freshness(client))
    r = client.put("/api/admin/config/line_retain_bands", json={"value": ["confident-relevant"]})
    assert r.status_code == 200, r.text
    line = _of(_freshness(client), "line")
    assert line["fresh"] is False
    assert "config_digest" in line["changed"]


# ── the reviewer's confirmed findings, each with the scenario that reproduced it ────────────────
def _relabel(store, discarded: list[str]) -> None:
    """Re-judge the matter through the store's own label writer — the seam POST /judge reaches."""
    reps = [pid for pid, _ in store.representatives(MATTER, TENANT, {WALL})]
    store.save_labels(
        MATTER, TENANT, {WALL},
        TriageOutcome(tuple(
            PieceLabel(pid, Label.DISCARD if pid in discarded else Label.RELEVANT, "verdict")
            for pid in reps)),
        "criteria", actor="me.durand")


def test_a_re_judge_makes_the_bound_stale_and_unexportable(tmp_path: Path, monkeypatch) -> None:
    """FR-23: a bound is stale when *"the population it was drawn from"* has changed. That
    population is the discarded pile, and a re-judge moves it while touching no ranking version, no
    line, no pin and no corpus count. Before this observable existed the bound read *à jour* and
    exported 200 while speaking about a set that was no longer the set — AD-23's named failure with
    a different cause."""
    store, client, pieces = _ranked_matter(tmp_path, monkeypatch)
    _record_bound(store, client)                     # drawn over ALL pièces, discarded
    fresh = client.get(f"/api/matters/{MATTER}/bound").json()
    assert fresh["exportable_as_current"] is True
    population = fresh["population"]

    _relabel(store, discarded=list(pieces[:2]))      # the pile is a DIFFERENT set now
    stale = client.get(f"/api/matters/{MATTER}/bound").json()
    assert stale["population"] == population          # the bound still says what it said
    assert stale["exportable_as_current"] is False    # …but it no longer says it as current
    assert "discard_population" in stale["freshness"]["changed"]
    assert "jeu écarté" in stale["copy_text"]
    assert client.get(f"/api/matters/{MATTER}/bound/export").status_code == 409


def test_a_re_judge_that_keeps_the_count_but_changes_the_set_is_still_stale(
    tmp_path: Path, monkeypatch
) -> None:
    """The observable is a digest, not a count: swapping one pièce out of the pile and another in
    leaves the cardinality identical while the population is a different set — and a bound is a
    statement about a set."""
    store, client, pieces = _ranked_matter(tmp_path, monkeypatch)
    _relabel(store, discarded=list(pieces[:2]))
    sample = client.get(f"/api/matters/{MATTER}/recall/sample", params={"n": 2}).json()["sample"]
    r = client.post(f"/api/matters/{MATTER}/recall/review", json={
        "verdicts": [{"piece_id": s["piece_id"], "relevant": False} for s in sample],
        "confidence": 0.95})
    assert r.status_code == 200, r.text
    assert client.get(f"/api/matters/{MATTER}/bound").json()["exportable_as_current"] is True

    _relabel(store, discarded=list(pieces[1:3]))      # same COUNT (2), different SET
    body = client.get(f"/api/matters/{MATTER}/bound").json()
    assert body["exportable_as_current"] is False
    assert "discard_population" in body["freshness"]["changed"]


def test_accepting_the_offered_re_rank_discharges_the_worklist_line(
    tmp_path: Path, monkeypatch
) -> None:
    """FR-58's offer must be dischargeable. A superseded artefact keeps its verdict — it is still
    readable and the verdict is still true of it (AD-7) — but it is not work: the recomputation its
    line offered has already been performed. Otherwise the banner grows by one paragraph per act and
    the true alarm is dismissed with the false ones."""
    store, client, _ = _ranked_matter(tmp_path, monkeypatch)
    _import_more(client, tmp_path, names=("tardive.txt",))
    offers = _worklist(client)
    # the ranking AND the line drawn over it are both stale on the import, each named once
    assert {line["offer"] for line in offers} == {"re-rank", "re-line"}
    assert all(line["changed"] == ["corpus_count"] for line in offers)

    _rank(store, client)                              # the lawyer accepts the offer
    assert _worklist(client) == []                    # …and it is discharged

    # the superseded version is still readable and still honestly stale on the audit surface
    superseded = [a for a in _freshness(client) if a["kind"] == "ranking" and not a["fresh"]]
    assert len(superseded) == 1
    old = client.get(f"/api/matters/{MATTER}/triage-table", params={"version": 1})
    assert old.status_code == 200


def test_moving_the_line_does_not_leave_a_line_that_demands_to_be_replaced(
    tmp_path: Path, monkeypatch
) -> None:
    """The same defect on the line: after a move, the placement the user just superseded would
    otherwise generate *"La ligne — périmé depuis : un déplacement de la ligne"* about a line that
    is current."""
    store, client, pieces = _ranked_matter(tmp_path, monkeypatch)
    assert _worklist(client) == []
    _move(store, 1, avoid="", pieces=pieces)
    assert _worklist(client) == []                    # the move discharged itself
    _move(store, 1, avoid="", pieces=pieces)
    assert _worklist(client) == []


def test_a_worklist_line_never_names_an_artefact_that_is_not_the_live_one(
    tmp_path: Path, monkeypatch
) -> None:
    """Whatever the worklist offers must be about the artefact the surface is showing — the latest
    ranking version, the placement in force over it, the most recent bound."""
    store, client, pieces = _ranked_matter(tmp_path, monkeypatch)
    _record_bound(store, client)
    _rank(store, client)
    place_line(store, tenant=TENANT, matter=MATTER, actor="me.durand", scopes={WALL})
    _move(store, 1, avoid="", pieces=pieces)          # a move on the OLD version
    _import_more(client, tmp_path, names=("tardive.txt",))
    live = {
        "ranking": store.read_ranking(tenant=TENANT, matter=MATTER, scopes={WALL}).version_id,
        "bound": client.get(f"/api/matters/{MATTER}/bound").json()["artefact_id"],
    }
    for line in _worklist(client):
        if line["kind"] in live:
            assert line["artefact_id"] == live[line["kind"]], line
