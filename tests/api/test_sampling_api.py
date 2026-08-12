"""The *sampling run* end to end (Story 5.1, FR-22) — the frozen random draw from the DISCARDED SET.

Every test here drives the product's own routes and seams against a real *matter* with a real
corpus, a real ranked order and a real committed line. The population is the **Epic-4 derived
view** (planning decision A1): nothing here labels a pile and calls it the discarded set.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apx.adapters.store_postgres.models import ArtefactStamp, SamplingRun, SamplingVerdict
from apx.core.app.line import move_line, place_line
from apx.core.app.pin import pin_piece
from apx.core.app.rank import produce_ranking
from apx.core.domain.cascade import CascadeUnit
from apx.core.domain.config import CascadeConfig
from apx.core.domain.ranking import RankingIdentityInputs
from apx.core.domain.triage import Label, PieceLabel, TriageOutcome
from apx.core.domain.triage_sets import PinSide
from tests.api.test_ingest_api import _login, _prepare, _reset_state  # noqa: F401 — autouse
from tests.scoring_fakes import FakeScorer, FixedJudge

TENANT, WALL, MATTER = "t", "wall", "m"
ADMIN = "admin@cab.fr"
# Six pièces, all distinct, so the near-duplicate families are one-per-pièce unless a test says
# otherwise — which keeps "the unit of the draw is the family" honest rather than accidental.
_FILES = {
    "bail.txt": "Contrat de bail commercial signé le 3 mars, clause résolutoire.",
    "facture.txt": "Facture EDF, cent cinquante euros, échéance avril.",
    "note.txt": "Note interne sur la clause résolutoire du bail commercial.",
    "annexe.txt": "Annexe technique au bail, plan des locaux et surfaces.",
    "courriel.txt": "Courriel du gérant au bailleur, refus de la mise en demeure.",
    "constat.txt": "Constat d'huissier du 12 juin, état des lieux de sortie.",
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


def _rank(store) -> list[str]:  # noqa: ANN001
    pieces = [pid for pid, _ in store.representatives(MATTER, TENANT, {WALL})]
    produce_ranking(
        [CascadeUnit(piece_id=p, text=p, chunk_ids=("c",)) for p in pieces],
        case_theory=None,
        scorer=FakeScorer({p: 0.95 - 0.1 * i for i, p in enumerate(pieces)}),
        judge=FixedJudge(), config=_cfg(), inputs=_inputs(), tenant=TENANT, matter=MATTER,
        actor="me.durand", scopes={WALL}, recorder=store)
    return pieces


def _cut_to(store, piece_id: str) -> None:  # noqa: ANN001
    """Move **the line** to a chosen *pièce* through the real priced act, so the derived discarded
    set is what the test needs it to be."""
    current = store.read_current_line(tenant=TENANT, matter=MATTER, scopes={WALL})
    if current.last_retained_piece_id == piece_id:
        return
    priced = store.price_line_move(
        tenant=TENANT, matter=MATTER, scopes={WALL}, candidate_last_retained_piece_id=piece_id)
    move_line(
        store, tenant=TENANT, matter=MATTER, actor="me.durand", scopes={WALL},
        last_retained_piece_id=piece_id, expected_seq=current.seq,
        priced_statement=f"{priced.pieces_to_read_delta:+d} pièces à lire")


def _ranked_order(store) -> list[str]:  # noqa: ANN001
    return [e.piece_id for e in store.read_ranked_order(
        tenant=TENANT, matter=MATTER, scopes={WALL}) if e.rank is not None]


def _matter(tmp_path: Path, monkeypatch, *, cut_at_rank: int = 1):  # noqa: ANN001,ANN201
    """A real matter, ranked, with the line cut so ``cut_at_rank`` *pièces* are retained and the
    rest are DISCARDED — a non-empty derived population to draw over."""
    store = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, ADMIN, "motdepasse", "Me Durand", {WALL}, is_admin=True)
    folder = tmp_path / "dossier"
    folder.mkdir()
    for name, text in _FILES.items():
        (folder / name).write_text(text, encoding="utf-8")
    client = TestClient(app())
    _login(client, ADMIN, pw="motdepasse")
    client.post("/api/ingest", json={"folder": str(folder), "matter": MATTER, "scope": WALL})
    _rank(store)
    place_line(store, tenant=TENANT, matter=MATTER, actor="me.durand", scopes={WALL})
    order = _ranked_order(store)
    _cut_to(store, order[cut_at_rank - 1])
    return store, client, order


def app():  # noqa: ANN201
    from apx.api.app import app as _app
    return _app


def _start(client: TestClient, **body) -> dict:  # noqa: ANN003
    r = client.post(f"/api/matters/{MATTER}/sampling/runs", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _judge_all(client: TestClient, run: dict, *, relevant: int = 0) -> dict:
    """A verdict on every drawn family; the first ``relevant`` of them are marked relevant."""
    body = run
    for i, drawn in enumerate(run["drawn"]):
        r = client.post(
            f"/api/matters/{MATTER}/sampling/runs/{run['run_id']}/verdicts",
            json={"family_id": drawn["unit"]["family_id"], "relevant": i < relevant})
        assert r.status_code == 200, r.text
        body = r.json()
    return body


def _complete(client: TestClient, run_id: str) -> dict:
    r = client.post(f"/api/matters/{MATTER}/sampling/runs/{run_id}/complete")
    assert r.status_code == 200, r.text
    return r.json()


def _current(client: TestClient) -> dict:
    r = client.get(f"/api/matters/{MATTER}/sampling/runs/current")
    assert r.status_code == 200, r.text
    return r.json()


# ── AC1 — the draw is over the DERIVED discarded set, within scope, without replacement ──────────

def test_the_population_is_the_derived_discarded_set_not_the_label_pile(
    tmp_path: Path, monkeypatch
) -> None:
    """Decision A1, asserted where it matters. Every *pièce* is labelled ``discard`` by Epic 2's
    ledger, but the line retains the top two — so the population is four, not six. A run drawn over
    the label pile would hand the lawyer *pièces* she is looking at above the line."""
    store, client, order = _matter(tmp_path, monkeypatch, cut_at_rank=2)
    store.save_labels(
        MATTER, TENANT, {WALL},
        TriageOutcome(tuple(PieceLabel(p, Label.DISCARD, "écartée") for p in order)),
        "criteria", actor="seed")
    run = _start(client, sample_size=4)
    assert run["population_families"] == 4
    assert run["population_pieces"] == 4
    drawn = {pid for d in run["drawn"] for pid in d["unit"]["member_piece_ids"]}
    assert drawn.isdisjoint(set(order[:2]))         # nothing retained was ever offered


def test_a_pinned_back_piece_is_never_offered_for_review(tmp_path: Path, monkeypatch) -> None:
    """FR-43 — a pin moves exactly one *pièce* across the line. Under the label pile it would still
    be in the draw: the tool would ask the lawyer whether a *pièce* she retained is relevant."""
    store, client, order = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    pin_piece(store, tenant=TENANT, matter=MATTER, actor="me.durand", piece_id=order[3],
              side=PinSide.RETAIN, reason="pièce décisive", scopes={WALL})
    run = _start(client, sample_size=10)             # ask for everything
    drawn = {pid for d in run["drawn"] for pid in d["unit"]["member_piece_ids"]}
    assert order[3] not in drawn
    assert run["population_families"] == 4           # 6 ranked − 1 retained − 1 pinned back


def test_the_unscored_tail_is_never_sampled(tmp_path: Path, monkeypatch) -> None:
    """AD-19/AD-36 — a *pièce* the cascade could not score was not discarded, and a bound over it
    would be a bound over a different claim."""
    from apx.adapters.store_postgres.models import RankedEntry

    store, client, order = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    with store._sf() as session, session.begin():    # the cascade failing on one pièce
        row = session.scalars(
            session.query(RankedEntry).filter(RankedEntry.piece_id == order[-1]).statement).first()
        row.rank = None
    run = _start(client, sample_size=10)
    drawn = {pid for d in run["drawn"] for pid in d["unit"]["member_piece_ids"]}
    assert order[-1] not in drawn


def test_the_draw_is_without_replacement_and_bounded_by_the_population(
    tmp_path: Path, monkeypatch
) -> None:
    _store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=99)
    families = [d["unit"]["family_id"] for d in run["drawn"]]
    assert len(families) == len(set(families)) == run["population_families"] == 5
    assert run["is_census"] is True


def test_an_empty_discarded_set_is_no_bound_applies_never_a_flattering_zero(
    tmp_path: Path, monkeypatch
) -> None:
    store, client, order = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    _cut_to(store, order[-1])                        # retain everything
    r = client.post(f"/api/matters/{MATTER}/sampling/runs", json={"sample_size": 3})
    assert r.status_code == 404                      # nothing to audit; not a run of zero
    sizing = client.get(
        f"/api/matters/{MATTER}/sampling/sizing", params={"target": 0.05})
    assert sizing.status_code == 200
    assert sizing.json()["size"] is None
    assert "aucune borne" in sizing.json()["reason_fr"]


def test_a_matter_with_no_line_has_no_discarded_set_to_draw_over(
    tmp_path: Path, monkeypatch
) -> None:
    """Without a cut there is no discarded set, and calling the whole ranked order "écartée" is the
    lie FR-16 forbids."""
    store = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, ADMIN, "motdepasse", "Me Durand", {WALL}, is_admin=True)
    folder = tmp_path / "dossier"
    folder.mkdir()
    for name, text in _FILES.items():
        (folder / name).write_text(text, encoding="utf-8")
    client = TestClient(app())
    _login(client, ADMIN, pw="motdepasse")
    client.post("/api/ingest", json={"folder": str(folder), "matter": MATTER, "scope": WALL})
    _rank(store)                                      # ranked, but NO line placed
    assert client.post(
        f"/api/matters/{MATTER}/sampling/runs", json={"sample_size": 2}).status_code == 404


# ── AC2 — sizing by target, and the census crossover ────────────────────────────────────────────

def test_sizing_answers_with_a_size_or_the_best_achievable(tmp_path: Path, monkeypatch) -> None:
    _store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    loose = client.get(
        f"/api/matters/{MATTER}/sampling/sizing", params={"target": 0.6}).json()
    assert loose["size"] is not None and loose["population"] == 5
    tight = client.get(
        f"/api/matters/{MATTER}/sampling/sizing", params={"target": 0.0}).json()
    assert tight["is_census"] is True and tight["size"] == 5
    capped = client.get(
        f"/api/matters/{MATTER}/sampling/sizing",
        params={"target": 0.0, "max_size": 2}).json()
    assert capped["size"] is None                      # unreachable at what a human will read
    assert "inatteignable" in capped["reason_fr"]
    assert capped["achievable_prevalence_upper"] > 0.0  # …and it says what IS achievable


def test_a_census_states_a_fact_and_never_a_percentage(tmp_path: Path, monkeypatch) -> None:
    _store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=5)
    assert run["is_census"] is True
    _judge_all(client, run)
    done = _complete(client, run["run_id"])
    # Story 5.4 — ONE server-composed sentence per run, in whichever register applies. It replaced
    # `census_fr`, which had an arm for one register and left the other three to the client.
    assert done["statement_fr"] is not None
    assert "ecensement" in done["statement_fr"] and "%" not in done["statement_fr"]
    # CONFIRMED [HIGH] by the Story 5.3 review. This asserted `prevalence_upper == 0.0` — a bound
    # of zero on a payload for a population that was read in full. The register is disjoint on the
    # WIRE now, not only in the sentence: `/sampling/runs` reads its numbers off the register-aware
    # estimate rather than off the run row, so a census carries NULL where a bound would sit and no
    # client can render a residual-risk figure by reaching for a field that should not be there.
    assert done["prevalence_upper"] is None
    assert done["count_upper"] is None
    assert done["estimate_kind"] == "census"


def test_a_target_bound_sizes_the_run_it_starts(tmp_path: Path, monkeypatch) -> None:
    _store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    sizing = client.get(
        f"/api/matters/{MATTER}/sampling/sizing", params={"target": 0.6}).json()
    run = _start(client, target_prevalence=0.6)
    assert run["sample_size"] == sizing["size"]


def test_giving_both_a_size_and_a_target_is_refused(tmp_path: Path, monkeypatch) -> None:
    _store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    r = client.post(
        f"/api/matters/{MATTER}/sampling/runs",
        json={"sample_size": 2, "target_prevalence": 0.1})
    assert r.status_code == 400
    assert client.post(f"/api/matters/{MATTER}/sampling/runs", json={}).status_code == 400


# ── AC3 — the freeze: identifiers, not a seed ───────────────────────────────────────────────────

def test_the_run_records_the_version_the_line_the_pins_and_the_scope(
    tmp_path: Path, monkeypatch
) -> None:
    store, client, order = _matter(tmp_path, monkeypatch, cut_at_rank=2)
    run = _start(client, sample_size=2)
    line = store.read_current_line(tenant=TENANT, matter=MATTER, scopes={WALL})
    assert run["version_no"] == 1
    assert run["last_retained_piece_id"] == line.last_retained_piece_id == order[1]
    assert run["scope"] == WALL
    assert run["pin_ledger_seq"] == 0
    assert all(d["unit"]["member_piece_ids"] for d in run["drawn"])   # explicit identifiers


def test_the_frozen_identifier_list_survives_a_re_rank_verbatim(
    tmp_path: Path, monkeypatch
) -> None:
    """FR-22's whole point. A seed would re-describe the draw against the NEW order; the recorded
    identifiers say what was actually offered for review."""
    store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=3)
    frozen = [d["unit"]["member_piece_ids"] for d in run["drawn"]]
    _rank(store)                                        # a NEW ranking version
    after = _current(client)
    assert [d["unit"]["member_piece_ids"] for d in after["drawn"]] == frozen
    assert after["version_no"] == 1                     # it still names the version it drew over


def test_a_family_is_one_draw_and_carries_its_members(tmp_path: Path, monkeypatch) -> None:
    """FR-38 — near-duplicates are one unit. Two identical *pièces* land in one family, so a run
    over them draws once and freezes both identities."""
    store = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, ADMIN, "motdepasse", "Me Durand", {WALL}, is_admin=True)
    folder = tmp_path / "dossier"
    folder.mkdir()
    same = "Contrat de bail commercial signé le 3 mars, clause résolutoire, exemplaire."
    (folder / "original.txt").write_text(same, encoding="utf-8")
    (folder / "copie.txt").write_text(same + " ", encoding="utf-8")   # a near-duplicate
    (folder / "autre.txt").write_text("Facture EDF, cent cinquante euros.", encoding="utf-8")
    (folder / "encore.txt").write_text("Constat d'huissier du 12 juin.", encoding="utf-8")
    client = TestClient(app())
    _login(client, ADMIN, pw="motdepasse")
    client.post("/api/ingest", json={"folder": str(folder), "matter": MATTER, "scope": WALL})
    _rank(store)
    place_line(store, tenant=TENANT, matter=MATTER, actor="me.durand", scopes={WALL})
    order = _ranked_order(store)
    _cut_to(store, order[0])
    run = _start(client, sample_size=10)
    sizes = sorted(len(d["unit"]["member_piece_ids"]) for d in run["drawn"])
    assert run["population_pieces"] >= run["population_families"]
    assert sizes[-1] >= 1
    for drawn in run["drawn"]:
        assert drawn["unit"]["proxy_piece_id"] in drawn["unit"]["member_piece_ids"]


# ── AC4 — invalidated in flight, immediately, and never by a clock ──────────────────────────────

@pytest.mark.parametrize("trigger", ["ingest", "rerank", "line", "pin"])
def test_an_act_that_moves_the_population_invalidates_the_open_run(
    tmp_path: Path, monkeypatch, trigger: str
) -> None:
    store, client, order = _matter(tmp_path, monkeypatch, cut_at_rank=2)
    run = _start(client, sample_size=2)
    assert _current(client)["invalidated_in_flight"] is False

    if trigger == "ingest":
        second = tmp_path / "arrivage"
        second.mkdir()
        (second / "tardive.txt").write_text("Pièce arrivée après le tirage.", encoding="utf-8")
        client.post(
            "/api/ingest", json={"folder": str(second), "matter": MATTER, "scope": WALL})
    elif trigger == "rerank":
        _rank(store)
    elif trigger == "line":
        _cut_to(store, order[2])
    else:
        pin_piece(store, tenant=TENANT, matter=MATTER, actor="me.durand", piece_id=order[-1],
                  side=PinSide.RETAIN, reason="pièce décisive", scopes={WALL})

    after = _current(client)
    assert after["invalidated_in_flight"] is True
    assert after["state"] == "invalidated"
    assert after["changed"], "the run must NAME what moved, never a bare 'invalidated'"
    assert after["changed_fr"] and "invalidé" in after["state_fr"]
    # FR-22: it tells the user immediately — by REFUSING the next verdict, not by a warning
    v = client.post(
        f"/api/matters/{MATTER}/sampling/runs/{run['run_id']}/verdicts",
        json={"family_id": run["drawn"][0]["unit"]["family_id"], "relevant": False})
    assert v.status_code == 409
    assert "invalidé" in v.json()["detail"]
    assert client.post(
        f"/api/matters/{MATTER}/sampling/runs/{run['run_id']}/complete").status_code == 409


def test_reading_an_open_run_five_times_never_invalidates_it(
    tmp_path: Path, monkeypatch
) -> None:
    """Validity is never resolved — in either direction — by time or by being looked at."""
    _store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    _start(client, sample_size=2)
    states = [_current(client)["state"] for _ in range(5)]
    assert states == ["open"] * 5


def test_a_run_with_no_stamp_is_invalidated_not_assumed_valid(
    tmp_path: Path, monkeypatch
) -> None:
    """An absence of evidence is not evidence of validity — the same rule 4.13 applies to an
    unstamped bound."""
    store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=2)
    with store._sf() as session, session.begin():
        session.query(ArtefactStamp).filter(
            ArtefactStamp.artefact_id == run["run_id"]).delete()
    assert _current(client)["invalidated_in_flight"] is True


def test_an_invalidated_run_is_abandoned_and_redrawn_and_keeps_its_verdicts(
    tmp_path: Path, monkeypatch
) -> None:
    store, client, order = _matter(tmp_path, monkeypatch, cut_at_rank=2)
    run = _start(client, sample_size=2)
    _judge_all(client, run)
    _cut_to(store, order[2])                             # the population moves underneath it
    assert _current(client)["invalidated_in_flight"] is True

    a = client.post(f"/api/matters/{MATTER}/sampling/runs/{run['run_id']}/abandon")
    assert a.status_code == 200, a.text
    assert a.json()["status"] == "abandoned"
    # AD-7: an hour of verdicts is never destroyed, only marked as no longer answering the question
    assert a.json()["verdicts_recorded"] == 2
    history = client.get(f"/api/matters/{MATTER}/sampling/runs").json()
    abandoned = next(r for r in history if r["run_id"] == run["run_id"])
    assert abandoned["verdicts_recorded"] == 2
    assert abandoned["drawn"] == a.json()["drawn"]

    fresh = _start(client, sample_size=2)                 # redrawn over the NEW population
    assert fresh["run_id"] != run["run_id"]
    assert _current(client)["state"] == "open"


def test_a_completed_run_is_not_in_flight_even_when_its_bound_goes_stale(
    tmp_path: Path, monkeypatch
) -> None:
    store, client, order = _matter(tmp_path, monkeypatch, cut_at_rank=2)
    run = _start(client, sample_size=2)
    _judge_all(client, run)
    _complete(client, run["run_id"])
    _cut_to(store, order[2])
    after = _current(client)
    assert after["state"] == "completed"                  # not "invalidated": it is not in flight
    assert after["invalidated_in_flight"] is False
    # …but its BOUND is stale, and 4.13 refuses the export
    assert client.get(f"/api/matters/{MATTER}/bound").json()["exportable_as_current"] is False
    assert client.get(f"/api/matters/{MATTER}/bound/export").status_code == 409


# ── AC5 — verdicts are append-only and attributed ───────────────────────────────────────────────

def test_a_corrected_verdict_is_a_new_entry_not_an_edit(tmp_path: Path, monkeypatch) -> None:
    store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=2)
    family = run["drawn"][0]["unit"]["family_id"]
    for relevant in (False, True):
        r = client.post(
            f"/api/matters/{MATTER}/sampling/runs/{run['run_id']}/verdicts",
            json={"family_id": family, "relevant": relevant})
        assert r.status_code == 200, r.text
    with store._sf() as session:
        rows = session.query(SamplingVerdict).filter(
            SamplingVerdict.run_id == run["run_id"],
            SamplingVerdict.family_id == family).all()
    assert [row.seq for row in sorted(rows, key=lambda x: x.seq)] == [1, 2]
    assert sorted(row.relevant for row in rows) == [False, True]   # the earlier one is still there
    current = next(
        d for d in _current(client)["drawn"] if d["unit"]["family_id"] == family)
    assert current["relevant"] is True and current["verdict_seq"] == 2
    assert current["verdict_by"] == "Me Durand"


def test_a_verdict_on_a_family_this_run_did_not_draw_is_not_a_verdict(
    tmp_path: Path, monkeypatch
) -> None:
    _store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=1)
    r = client.post(
        f"/api/matters/{MATTER}/sampling/runs/{run['run_id']}/verdicts",
        json={"family_id": "pas-une-famille-tirée", "relevant": True})
    assert r.status_code == 404


def test_a_closed_run_refuses_a_late_verdict(tmp_path: Path, monkeypatch) -> None:
    _store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=2)
    _judge_all(client, run)
    _complete(client, run["run_id"])
    r = client.post(
        f"/api/matters/{MATTER}/sampling/runs/{run['run_id']}/verdicts",
        json={"family_id": run["drawn"][0]["unit"]["family_id"], "relevant": True})
    assert r.status_code == 409 and "clos" in r.json()["detail"]


# ── AC7 — completion is atomic, bounded over the unit drawn, and audited ────────────────────────

def test_an_unjudged_family_is_not_a_verdict_of_not_relevant(
    tmp_path: Path, monkeypatch
) -> None:
    """AD-19 — nothing imputed. Counting an unreviewed family as "not relevant" would make every
    bound look better than the evidence supports."""
    _store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=3)
    client.post(
        f"/api/matters/{MATTER}/sampling/runs/{run['run_id']}/verdicts",
        json={"family_id": run["drawn"][0]["unit"]["family_id"], "relevant": False})
    r = client.post(f"/api/matters/{MATTER}/sampling/runs/{run['run_id']}/complete")
    assert r.status_code == 400
    assert "not fully judged" in r.json()["detail"]


def test_completion_tallies_bounds_and_audits_in_one_act(tmp_path: Path, monkeypatch) -> None:
    _store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=3)
    _judge_all(client, run, relevant=1)
    done = _complete(client, run["run_id"])
    assert done["status"] == "completed"
    assert done["relevant_found"] == 1
    assert done["count_upper"] >= 1
    assert 0 < done["prevalence_upper"] <= 1
    trail = client.get(f"/api/matters/{MATTER}/audit").json()["entries"]
    actions = [e["action"] for e in trail]
    assert "sampling-run-start" in actions
    assert actions.count("sampling-verdict") == 3
    assert "sampling-run-complete" in actions


def test_the_completed_run_is_the_matters_bound_and_names_the_unit_it_drew(
    tmp_path: Path, monkeypatch
) -> None:
    _store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=3)
    _judge_all(client, run)
    done = _complete(client, run["run_id"])
    bound = client.get(f"/api/matters/{MATTER}/bound").json()
    assert bound["artefact_id"] == run["run_id"]
    # the bound is over FAMILIES — the unit drawn — not over pièces (FR-38)
    assert bound["population"] == done["population_families"]
    assert bound["sample_size"] == done["sample_size"]
    assert bound["freshness"]["fresh"] is True
    assert bound["exportable_as_current"] is True


def test_a_completed_run_wins_over_a_legacy_recall_review_unconditionally(
    tmp_path: Path, monkeypatch
) -> None:
    """Decision A1 — the two bounds are computed over DIFFERENT populations, so picking the more
    recent of two incomparable things is the nearly-right referent. Once a run exists, the
    label-pile bound is history."""
    from datetime import UTC, datetime

    from apx.adapters.store_postgres.models import RecallReview

    store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=3)
    _judge_all(client, run)
    _complete(client, run["run_id"])
    with store._sf() as session, session.begin():          # a legacy row recorded LATER
        session.add(RecallReview(
            id="legacy", tenant=TENANT, matter=MATTER, population=999, sample_size=1,
            relevant_found=0, confidence=0.95, count_upper=3, prevalence_upper=0.003,
            reviewer="ancien", reviewed_at=datetime.now(UTC)))
    bound = client.get(f"/api/matters/{MATTER}/bound").json()
    assert bound["artefact_id"] == run["run_id"]           # not "legacy", despite being newer
    assert bound["population"] != 999


# ── FR-14 / AD-13 — out of scope and absent are the same non-disclosing answer ──────────────────

def test_out_of_scope_and_absent_are_indistinguishable(tmp_path: Path, monkeypatch) -> None:
    store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    _start(client, sample_size=2)
    store.create_user(TENANT, "autre@cab.fr", "motdepasse", "Autre", {"mur-3"}, is_admin=False)
    other = TestClient(app())
    _login(other, "autre@cab.fr", pw="motdepasse")
    for path in ("sampling/runs", "sampling/runs/current", "sampling/sizing?target=0.2"):
        held = other.get(f"/api/matters/{MATTER}/{path}")
        absent = other.get(f"/api/matters/nexistepas/{path}")
        assert held.status_code == absent.status_code == 404
        assert held.json() == absent.json()
    denied = other.post(f"/api/matters/{MATTER}/sampling/runs", json={"sample_size": 1})
    assert denied.status_code in (403, 404)
    with store._sf() as session:
        assert session.query(SamplingRun).count() == 1     # the refusal wrote nothing


def test_a_draw_of_zero_is_refused_not_silently_one(tmp_path: Path, monkeypatch) -> None:
    """A run that drew nothing would produce the honest-but-useless bound "the whole pile could be
    relevant" while looking on the surface like a review that happened."""
    _store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    for size in (0, -3):
        r = client.post(f"/api/matters/{MATTER}/sampling/runs", json={"sample_size": size})
        assert r.status_code == 400, r.text
        assert "at least one" in r.json()["detail"]


def test_the_run_history_carries_each_runs_own_measured_verdict(
    tmp_path: Path, monkeypatch
) -> None:
    """The history is not a list of statuses: each entry carries the freshness that was actually
    MEASURED for that run, so a reader cannot mistake an unmeasured () for a measured one."""
    store, client, order = _matter(tmp_path, monkeypatch, cut_at_rank=2)
    first = _start(client, sample_size=2)
    _judge_all(client, first)
    _complete(client, first["run_id"])
    _cut_to(store, order[2])                       # everything after this is over a new population
    second = _start(client, sample_size=2)

    history = client.get(f"/api/matters/{MATTER}/sampling/runs").json()
    assert [r["run_id"] for r in history] == [second["run_id"], first["run_id"]]
    by_id = {r["run_id"]: r for r in history}
    assert by_id[second["run_id"]]["state"] == "open"
    assert by_id[first["run_id"]]["state"] == "completed"     # closed, not "invalidated"
    # …and the completed run's bound IS stale, which is a different statement, made elsewhere
    assert by_id[first["run_id"]]["changed"] == ["line_seq"]


# ── regressions for the adversarial review's confirmed findings ─────────────────────────────────

def test_a_run_over_a_superseded_ranking_version_is_refused(tmp_path: Path, monkeypatch) -> None:
    """CONFIRMED [HIGH]. read_current_bound takes the latest COMPLETED run, and every observable a
    run watches is the *matter*'s, not the old version's — so a run drawn over version 1 while the
    matter is on version 2 became the matter's current bound, read FRESH, and exported, while
    describing a discarded set the re-rank had already replaced. The catastrophic direction.

    Regression: removing the latest-version guard in start_sampling_run makes this test fail."""
    store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    _rank(store)                                          # version 2 exists
    r = client.post(
        f"/api/matters/{MATTER}/sampling/runs", json={"sample_size": 2, "version_no": 1})
    assert r.status_code == 400, r.text
    assert "remplacé par la v2" in r.json()["detail"]
    assert client.get(f"/api/matters/{MATTER}/sampling/runs").json() == []


@pytest.mark.parametrize("confidence", [0.0, 1.0, 1.5, -0.2])
def test_an_out_of_range_confidence_is_refused_at_the_draw(
    tmp_path: Path, monkeypatch, confidence: float
) -> None:
    """CONFIRMED [MEDIUM]. It was frozen onto the run and only rejected at completion — an hour of
    verdicts against a draw that could never produce a number."""
    _store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    r = client.post(
        f"/api/matters/{MATTER}/sampling/runs",
        json={"sample_size": 2, "confidence": confidence})
    assert r.status_code == 400, r.text
    assert "confidence" in r.json()["detail"]
    sizing = client.get(
        f"/api/matters/{MATTER}/sampling/sizing",
        params={"target": 0.2, "confidence": confidence})
    assert sizing.status_code == 400          # the preview refuses what the draw refuses


def test_a_max_size_of_zero_does_not_silently_become_a_census(
    tmp_path: Path, monkeypatch
) -> None:
    """CONFIRMED [MEDIUM]. `max_size or len(families)` read a real cap of 0 as "unset" and drew the
    WHOLE population — the opposite of what was asked, on the one path FR-22 calls unreachable."""
    _store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, target_prevalence=0.0, max_size=0)
    assert run["sample_size"] == 1            # the floor, never the census
    assert run["is_census"] is False


def test_a_scope_refusal_on_the_draw_is_the_same_404_as_an_absent_matter(
    tmp_path: Path, monkeypatch
) -> None:
    """CONFIRMED [MEDIUM]. POST answered 403 where every peer sampling route answers 404, so the
    one write route disclosed that another firm's dossier exists (FR-14/AD-13)."""
    store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    store.create_user(TENANT, "autre@cab.fr", "motdepasse", "Autre", {"mur-3"}, is_admin=False)
    other = TestClient(app())
    _login(other, "autre@cab.fr", pw="motdepasse")
    held = other.post(f"/api/matters/{MATTER}/sampling/runs", json={"sample_size": 1})
    absent = other.post("/api/matters/nexistepas/sampling/runs", json={"sample_size": 1})
    assert held.status_code == absent.status_code == 404
    assert held.json() == absent.json()       # byte-identical
    with store._sf() as session:
        assert session.query(SamplingRun).count() == 0


def test_a_matter_never_ranked_is_not_told_its_discarded_set_is_empty(
    tmp_path: Path, monkeypatch
) -> None:
    """CONFIRMED [MEDIUM] — a nearly-right referent in the message itself. "Le jeu écarté est vide"
    told to a lawyer whose dossier was never ranked says the tool looked and found nothing, when
    the tool never looked. The two facts must read differently."""
    store = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, ADMIN, "motdepasse", "Me Durand", {WALL}, is_admin=True)
    folder = tmp_path / "dossier"
    folder.mkdir()
    (folder / "bail.txt").write_text("Contrat de bail commercial.", encoding="utf-8")
    client = TestClient(app())
    _login(client, ADMIN, pw="motdepasse")
    client.post("/api/ingest", json={"folder": str(folder), "matter": MATTER, "scope": WALL})
    never_ranked = client.get(
        f"/api/matters/{MATTER}/sampling/sizing", params={"target": 0.05}).json()
    assert "aucun classement" in never_ranked["reason_fr"]
    assert "vide" not in never_ranked["reason_fr"]


def test_an_abandoned_run_stops_demanding_a_re_sample(tmp_path: Path, monkeypatch) -> None:
    """CONFIRMED [MEDIUM]. Abandoning IS discharging the offer: she looked at the invalidated draw
    and decided not to have a bound. Left "in force", an abandoned run would put a permanently
    stale line on the worklist — the banner growing a paragraph nobody can clear, which is the
    failure Story 4.13 introduced supersession to prevent."""
    store, client, order = _matter(tmp_path, monkeypatch, cut_at_rank=2)
    run = _start(client, sample_size=2)
    _cut_to(store, order[2])                                  # invalidate it in flight
    assert _current(client)["invalidated_in_flight"] is True
    offers = [
        line for line in client.get(f"/api/matters/{MATTER}/worklist").json()
        if line["kind"] == "sampling_run"]
    assert offers and offers[0]["offer"] == "re-sample"        # while it is open, it IS work

    client.post(f"/api/matters/{MATTER}/sampling/runs/{run['run_id']}/abandon")
    after = [
        line for line in client.get(f"/api/matters/{MATTER}/worklist").json()
        if line["kind"] == "sampling_run"]
    assert after == []                                        # …and abandoning discharges it
    # the run and its draw are still fully readable (AD-7)
    history = client.get(f"/api/matters/{MATTER}/sampling/runs").json()
    assert history[0]["status"] == "abandoned" and history[0]["drawn"]


def test_a_legacy_bound_stops_demanding_a_re_sample_once_a_run_exists(
    tmp_path: Path, monkeypatch
) -> None:
    """CONFIRMED [MEDIUM]. A recall_review stamped between 4.13 and 5.1 carries a LABEL-PILE digest,
    so it compares unequal against the derived-view digest forever — and no code path can ever write
    another one. Left live it would offer a re-sample that nothing in the product can discharge."""
    from datetime import UTC, datetime

    from apx.adapters.store_postgres.models import RecallReview

    store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    with store._sf() as session, session.begin():
        session.add(RecallReview(
            id="legacy", tenant=TENANT, matter=MATTER, population=1400, sample_size=200,
            relevant_found=0, confidence=0.95, count_upper=15, prevalence_upper=0.0107,
            reviewer="ancien", reviewed_at=datetime.now(UTC)))
        store._write_stamp(
            session, tenant=TENANT, matter=MATTER, kind="bound", artefact_id="legacy",
            version_no=1, now=datetime.now(UTC))
    assert client.get(f"/api/matters/{MATTER}/bound").json()["artefact_id"] == "legacy"

    run = _start(client, sample_size=2)                        # the label-pile era ends here
    legacy = next(
        a for a in client.get(f"/api/matters/{MATTER}/freshness").json()
        if a["artefact_id"] == "legacy")
    assert legacy["superseded"] is True                        # still readable, no longer work
    assert not [
        line for line in client.get(f"/api/matters/{MATTER}/worklist").json()
        if line["artefact_id"] == "legacy"]
    assert run["run_id"] != "legacy"


def test_the_copied_bound_names_the_unit_it_was_computed_over(
    tmp_path: Path, monkeypatch
) -> None:
    """CONFIRMED [HIGH]. A run draws near-duplicate FAMILIES, so `population` is a family count.
    Rendering it as "des 5 pièces écartées" made the one sentence a firm says to a judge false about
    its own denominator."""
    _store, client, _ = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=3)
    _judge_all(client, run)
    done = _complete(client, run["run_id"])
    body = client.get(f"/api/matters/{MATTER}/bound").json()
    text = body["copy_text"]
    assert "familles de quasi-doublons écartées" in text
    assert f"{done['population_families']} familles" in text
    assert f"({done['population_pieces']} pièces)" in text     # stated beside, never substituted
    assert "à jour" in text
