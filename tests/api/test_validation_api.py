"""The *validation act* over HTTP (Story 5.8, FR-45 / FR-44 / FR-26).

FR-45's assertions are behavioural and they are made here, against the real store: a *matter* read
end to end yields **zero** acceptances; a batch records its split per *pièce* rather than stamping
it; a withdrawal appends; and the export's §7 becomes a real section carrying two registers that are
never pooled.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apx.api.app import app
from apx.core.app.line import place_line
from apx.core.app.rank import produce_ranking
from apx.core.domain import audit as AUDIT
from apx.core.domain.cascade import CascadeUnit
from apx.core.domain.config import CascadeConfig
from apx.core.domain.ranking import RankingIdentityInputs
from apx.core.domain.validation import ASSERTION_FR
from tests.api.test_ingest_api import _login, _prepare, _reset_state  # noqa: F401 — autouse
from tests.scoring_fakes import FakeScorer, FixedJudge

TENANT, WALL, MATTER = "t", "wall", "m"
ME = "me@x.fr"
# retro B2/H7: the act names the *ranking version* it accepts, and the boundary
# requires it. `_rank` produces the matter's first, so every act below accepts version 1.
V1 = 1
_FILES = {
    "bail.txt": "Contrat de bail commercial signé le 3 mars, clause résolutoire.",
    "facture.txt": "Facture EDF, 150 euros, échéance avril.",
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


def _rank(store, client: TestClient, *, matter: str = MATTER, scope: str = WALL) -> list[str]:  # noqa: ANN001
    """Rank whatever is in the corpus, and commit the line. Returns the pièce ids in rank order."""
    pieces = [pid for pid, _ in store.representatives(matter, TENANT, {scope})]
    units = [CascadeUnit(piece_id=p, text=p, chunk_ids=("c",)) for p in pieces]
    produce_ranking(
        units, case_theory=None,
        scorer=FakeScorer({p: 0.95 - 0.3 * i for i, p in enumerate(pieces)}),
        judge=FixedJudge(), config=_cfg(), inputs=_inputs(), tenant=TENANT, matter=matter,
        actor="Me Durand", scopes={scope}, recorder=store)
    place_line(store, tenant=TENANT, matter=matter, actor="Me Durand", scopes={scope})
    order = store.read_ranked_order(tenant=TENANT, matter=matter, scopes={scope})
    return [r.piece_id for r in order]


def _ready(tmp_path: Path, monkeypatch, *, scope: str = WALL, matter: str = MATTER):  # noqa: ANN001, ANN202
    """A real matter: a corpus on disk, ingested, ranked, with a committed line."""
    store = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, ME, "motdepasse", "Me Durand", {scope})
    folder = tmp_path / f"dossier-{matter}"
    folder.mkdir()
    for name, text in _FILES.items():
        (folder / name).write_text(text, encoding="utf-8")
    client = TestClient(app)
    _login(client, ME, pw="motdepasse")
    client.post("/api/ingest", json={"folder": str(folder), "matter": matter, "scope": scope})
    pieces = _rank(store, client, matter=matter, scope=scope)
    return store, client, pieces


# ── AC-4: "accepted as-is" exists ONLY where a validation act occurred ─────────────────────────

def test_a_matter_read_end_to_end_yields_zero_acceptances(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """FR-45's own assertion, made against the real surfaces: *a matter left open for an arbitrary
    period and scrolled end to end yields zero accepted-as-is entries.*

    Every read the interface can perform is exercised, repeatedly — the table, both drawers, the
    inventory, the audit trail — and the pièce is even OPENED in the viewer, which is the single
    most plausible thing to mistake for reading. None of it is a validation act, so none of it may
    produce an acceptance."""
    store, client, pieces = _ready(tmp_path, monkeypatch)
    store.audit_piece_open(
        tenant=TENANT, matter=MATTER, actor="Me Durand", piece_id=pieces[0])
    for _ in range(3):                            # "an arbitrary period", scrolled repeatedly
        client.get(f"/api/matters/{MATTER}/triage-table")
        for pid in pieces:
            client.get(f"/api/matters/{MATTER}/pieces/{pid}/drawer")
        client.get(f"/api/matters/{MATTER}/inventory")
        client.get(f"/api/matters/{MATTER}/audit")
    log = client.get(f"/api/matters/{MATTER}/validations").json()
    doc = client.post(f"/api/matters/{MATTER}/record/export?tier=numbers-only").json()

    assert log["entries"] == []
    assert doc["accepted_values"] == 0
    assert doc["validation_summary"]["read"] == 0
    assert doc["validation_summary"]["from_the_list"] == 0
    assert doc["validation_summary"]["never_validated"] == len(pieces)
    trail = store.read_audit(MATTER, TENANT, {WALL})
    assert not any(
        AUDIT.ACTS[e.action].act_class == AUDIT.CLASS_VALUE_ACCEPTED for e in trail.entries)


def test_opening_a_piece_is_not_validating_it(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """The one read closest to reading, kept apart from the act by design. Opening is recorded — it
    is what makes a later act provably after reading — and it produces no acceptance."""
    store, client, pieces = _ready(tmp_path, monkeypatch)
    store.audit_piece_open(
        tenant=TENANT, matter=MATTER, actor="Me Durand", piece_id=pieces[0])
    log = client.get(f"/api/matters/{MATTER}/validations").json()
    drawer = client.get(f"/api/matters/{MATTER}/pieces/{pieces[0]}/drawer").json()
    assert log["entries"] == []
    # …and the drawer now says what an act WOULD record, before she commits it
    assert drawer["validation_provenance"] == "read"
    assert drawer["validation_opened_at"] is not None


# ── AC-1..AC-3: the act, its sentence, and its provenance ─────────────────────────────────────

def test_the_control_carries_the_assertion_itself_not_a_verb(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    _store, client, pieces = _ready(tmp_path, monkeypatch)
    drawer = client.get(f"/api/matters/{MATTER}/pieces/{pieces[0]}/drawer").json()
    assert drawer["validation_assertion_fr"] == ASSERTION_FR
    offered = next(a for a in drawer["actions"] if a["action"] == AUDIT.ACT_VALIDATE_PIECE)
    assert offered["action_fr"] == ASSERTION_FR       # the sentence IS the control's own text
    assert offered["reversal_fr"]                     # and it names its own reversal
    assert drawer["pending_actions"] == []            # the disabled row is retired


def test_an_unopened_piece_says_so_before_the_act_and_records_it_after(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    _store, client, pieces = _ready(tmp_path, monkeypatch)
    drawer = client.get(f"/api/matters/{MATTER}/pieces/{pieces[0]}/drawer").json()
    assert drawer["validation_provenance"] == "from-the-list"
    assert "acceptée depuis la liste" in drawer["validation_provenance_fr"]
    assert "Vous n'avez pas ouvert" in drawer["validation_provenance_fr"]
    log = client.post(f"/api/matters/{MATTER}/pieces/{pieces[0]}/validate?version_no={V1}").json()
    entry = log["entries"][0]
    assert entry["provenance"] == "from-the-list" and entry["opened_at"] is None
    assert entry["actor"] == "Me Durand" and entry["batch_id"] is None


def test_the_opened_fact_is_this_actors_and_never_another_lawyers(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """The nearly-right referent this story's design is built against. Marc opened it; Claire
    validates it. Her entry must say *from the list* — the assertion is personal, and an entry
    inheriting a colleague's diligence is false about the person it names."""
    store, client, pieces = _ready(tmp_path, monkeypatch)
    store.create_user(TENANT, "marc@x.fr", "motdepasse", "Me Marc", {WALL})
    store.audit_piece_open(tenant=TENANT, matter=MATTER, actor="Me Marc", piece_id=pieces[0])
    drawer = client.get(f"/api/matters/{MATTER}/pieces/{pieces[0]}/drawer").json()
    log = client.post(f"/api/matters/{MATTER}/pieces/{pieces[0]}/validate?version_no={V1}").json()
    assert drawer["validation_provenance"] == "from-the-list"
    assert log["entries"][0]["provenance"] == "from-the-list"


def test_an_open_after_the_act_does_not_make_it_read(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """*Before* the act, strictly. An open recorded afterwards is a different gesture, and letting
    it colour an entry already written would let the record improve retroactively."""
    store, client, pieces = _ready(tmp_path, monkeypatch)
    client.post(f"/api/matters/{MATTER}/pieces/{pieces[0]}/validate?version_no={V1}")
    store.audit_piece_open(tenant=TENANT, matter=MATTER, actor="Me Durand", piece_id=pieces[0])
    log = client.get(f"/api/matters/{MATTER}/validations").json()
    assert log["entries"][0]["provenance"] == "from-the-list"


# ── AC-5: bulk is permitted and never undetectable ────────────────────────────────────────────

def test_the_batch_confirmation_states_the_count_and_the_split(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    store, client, pieces = _ready(tmp_path, monkeypatch)
    store.audit_piece_open(tenant=TENANT, matter=MATTER, actor="Me Durand", piece_id=pieces[0])
    split = client.post(
        f"/api/matters/{MATTER}/validate-batch/preview?version_no={V1}",
        json={"piece_ids": pieces, "confirmed_count": len(pieces)}).json()
    assert split["total"] == len(pieces) and split["opened"] == 1
    assert split["not_opened"] == len(pieces) - 1
    assert "depuis la liste" in split["sentence_fr"]
    # a preview writes nothing — it is what the dialog SAYS, not a step of the act
    assert store.read_validation_log(tenant=TENANT, matter=MATTER, scopes={WALL}) == ()


def test_a_batch_records_each_piece_s_own_provenance_never_a_blanket_stamp(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """FR-45(c) in as many words: *records for each pièce that it was not opened, unless it was.*
    One gesture, two different facts, and the same batch marker on both."""
    store, client, pieces = _ready(tmp_path, monkeypatch)
    store.audit_piece_open(tenant=TENANT, matter=MATTER, actor="Me Durand", piece_id=pieces[0])
    log = client.post(
        f"/api/matters/{MATTER}/validate-batch?version_no={V1}",
        json={"piece_ids": pieces, "confirmed_count": len(pieces)}).json()
    by_piece = {e["piece_id"]: e for e in log["entries"]}
    assert by_piece[pieces[0]]["provenance"] == "read"
    assert by_piece[pieces[1]]["provenance"] == "from-the-list"
    # one gesture: the SAME batch id and size on both, so a reader can group them
    assert by_piece[pieces[0]]["batch_id"] == by_piece[pieces[1]]["batch_id"] is not None
    assert by_piece[pieces[0]]["batch_size"] == by_piece[pieces[1]]["batch_size"] == len(pieces)


def test_a_batch_whose_count_does_not_match_the_selection_is_refused(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """The selection changed under the dialog: she confirmed a different act. Nothing is written."""
    store, client, pieces = _ready(tmp_path, monkeypatch)
    res = client.post(
        f"/api/matters/{MATTER}/validate-batch?version_no={V1}",
        json={"piece_ids": pieces, "confirmed_count": len(pieces) - 1})
    assert res.status_code == 400 and "confirms a different act" in res.json()["detail"]
    assert store.read_validation_log(tenant=TENANT, matter=MATTER, scopes={WALL}) == ()


def test_a_multi_piece_act_without_a_confirmation_is_refused(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """There is no unconfirmed bulk path. A body omitting the count is a 422 at the edge, and the
    store refuses a multi-pièce act with no confirmation even if one got past it."""
    store, client, pieces = _ready(tmp_path, monkeypatch)
    assert client.post(
        f"/api/matters/{MATTER}/validate-batch?version_no={V1}",
        json={"piece_ids": pieces}).status_code == 422
    with pytest.raises(ValueError, match="explicit confirmation"):
        store.validate_pieces(
            tenant=TENANT, matter=MATTER, actor="Me Durand", piece_ids=pieces, scopes={WALL},
            version_no=V1)


# ── AC-6: the reversal is an entry ────────────────────────────────────────────────────────────

def test_a_withdrawal_appends_and_erases_nothing(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    _store, client, pieces = _ready(tmp_path, monkeypatch)
    client.post(f"/api/matters/{MATTER}/pieces/{pieces[0]}/validate?version_no={V1}")
    log = client.post(
        f"/api/matters/{MATTER}/pieces/{pieces[0]}/validation/withdraw").json()
    again = client.post(f"/api/matters/{MATTER}/pieces/{pieces[0]}/validation/withdraw")
    assert [e["action"] for e in log["entries"]] == ["validated", "withdrawn"]
    assert again.status_code == 400                       # nothing in force to withdraw


def test_a_withdrawn_validation_is_counted_as_withdrawn_never_as_absent(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """*Never validated* and *validated then withdrawn* are different facts, and §7 keeps both."""
    _store, client, pieces = _ready(tmp_path, monkeypatch)
    client.post(f"/api/matters/{MATTER}/pieces/{pieces[0]}/validate?version_no={V1}")
    client.post(f"/api/matters/{MATTER}/pieces/{pieces[0]}/validation/withdraw")
    doc = client.post(f"/api/matters/{MATTER}/record/export?tier=numbers-only").json()
    summary = doc["validation_summary"]
    assert summary["withdrawn"] == 1
    assert summary["read"] == 0 and summary["from_the_list"] == 0
    assert doc["accepted_values"] == 0
    assert len(doc["validations"]) == 2               # the act AND its withdrawal, both printed


# ── AC-7: the acceptance names the version it accepted ────────────────────────────────────────

def test_a_re_rank_makes_the_acceptance_stale_and_invalidates_nothing(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    store, client, pieces = _ready(tmp_path, monkeypatch)
    client.post(f"/api/matters/{MATTER}/pieces/{pieces[0]}/validate?version_no={V1}")
    fresh = client.get(f"/api/matters/{MATTER}/validations").json()
    assert fresh["entries"][0]["stale"] is False
    _rank(store, client)                              # a second ranking version arrives
    after = client.get(f"/api/matters/{MATTER}/validations").json()
    entry = after["entries"][0]
    assert entry["stale"] is True
    assert entry["action"] == "validated"             # nothing erased, nothing invalidated
    assert entry["ranking_version_id"] != after["current_ranking_version_id"]


# ── AC-8: the export's two sections are real ──────────────────────────────────────────────────

def test_the_export_counts_the_two_registers_apart_and_retires_the_pending_blocks(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    store, client, pieces = _ready(tmp_path, monkeypatch)
    store.audit_piece_open(tenant=TENANT, matter=MATTER, actor="Me Durand", piece_id=pieces[0])
    client.post(f"/api/matters/{MATTER}/validate-batch?version_no={V1}",
                json={"piece_ids": pieces, "confirmed_count": len(pieces)})
    doc = client.post(f"/api/matters/{MATTER}/record/export?tier=numbers-only").json()
    summary = doc["validation_summary"]
    assert summary["read"] == 1
    assert summary["from_the_list"] == len(pieces) - 1
    assert summary["in_bulk"] == len(pieces) and summary["batches"] == 1
    assert summary["individually"] == 0
    assert doc["accepted_values"] == len(pieces)
    assert summary["never_validated"] == 0
    # the two blocks that named this story are gone — not replaced by a zero, RETIRED
    assert doc["pending"] == []


def test_the_acceptance_writes_two_entries_one_gesture_one_consequence(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """FR-24 §611 enumerates two recorded things and the record keeps them apart: *who validated
    what and when*, and *which values were accepted as-is*."""
    store, client, pieces = _ready(tmp_path, monkeypatch)
    client.post(f"/api/matters/{MATTER}/pieces/{pieces[0]}/validate?version_no={V1}")
    trail = store.read_audit(MATTER, TENANT, {WALL})
    actions = [e.action for e in trail.entries]
    assert actions.count(AUDIT.ACT_VALIDATE_PIECE) == 1
    assert actions.count(AUDIT.ACT_VALUES_ACCEPTED) == 1


# ── the wall ──────────────────────────────────────────────────────────────────────────────────

def test_validation_is_non_disclosing_outside_the_wall(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    store, client, pieces = _ready(tmp_path, monkeypatch, scope="wall-b", matter="m-b")
    store.create_user(TENANT, "a@x.fr", "motdepasse", "Me A", {"wall-a"})
    other = TestClient(app)
    _login(other, "a@x.fr", pw="motdepasse")
    walled = other.get("/api/matters/m-b/validations")
    absent = other.get("/api/matters/inexistante/validations")
    act = other.post(f"/api/matters/m-b/pieces/{pieces[0]}/validate?version_no={V1}")
    assert walled.status_code == absent.status_code == 404
    assert walled.json() == absent.json()             # the same answer, byte for byte
    assert act.status_code == 403
    assert store.read_validation_log(tenant=TENANT, matter="m-b", scopes={"wall-b"}) == ()


def test_a_piece_outside_the_ranking_cannot_be_accepted(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """A validation act accepts a NAMED version's assessment. There is none to accept for a pièce
    the ranking never saw, and inventing one is how an acceptance with no referent gets written."""
    _store, client, _pieces = _ready(tmp_path, monkeypatch)
    res = client.post(f"/api/matters/{MATTER}/pieces/jamais-classee/validate?version_no={V1}")
    assert res.status_code == 400 and "not in ranking version" in res.json()["detail"]


def test_two_gestures_over_the_same_selection_are_two_batches(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """The batch identifier answers §13's question 5 — *one gesture over how many* — so it must
    identify the GESTURE, not the selection. Hashing only (actor, version, pièces) gave the same id
    to the same set validated twice, and the export counted one batch where a lawyer had made two
    separate decisions."""
    _store, client, pieces = _ready(tmp_path, monkeypatch)
    body = {"piece_ids": pieces, "confirmed_count": len(pieces)}
    first = client.post(f"/api/matters/{MATTER}/validate-batch?version_no={V1}", json=body).json()
    second = client.post(f"/api/matters/{MATTER}/validate-batch?version_no={V1}", json=body).json()
    ids = {e["batch_id"] for e in second["entries"]}
    assert len(ids) == 2, "the second gesture must not inherit the first's identifier"
    assert {e["batch_id"] for e in first["entries"]} < ids


def test_never_validated_is_a_set_difference_not_a_subtraction(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """The two populations are not the same. The ledger is version-independent and holds acts over
    pièces a later ranking may no longer carry; the denominator is the CURRENT ranked set. A
    subtraction under-reports what nobody has looked at, and can go negative — which a clamp would
    have hidden as a flattering zero."""
    _store, client, pieces = _ready(tmp_path, monkeypatch)
    client.post(f"/api/matters/{MATTER}/pieces/{pieces[0]}/validate?version_no={V1}")
    doc = client.post(f"/api/matters/{MATTER}/record/export?tier=numbers-only").json()
    summary = doc["validation_summary"]
    # exactly the ranked pièces with no validation in force — never len(ranked) - len(entries)
    assert summary["never_validated"] == len(pieces) - 1
    assert summary["read"] + summary["from_the_list"] == 1
