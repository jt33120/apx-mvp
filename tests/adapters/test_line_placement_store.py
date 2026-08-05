"""place_line + read_current_line (Story 4.8, FR-17): the tool draws the line and commits.

The system chooses the cut recall-first and STORES it by the identity of the last retained pièce —
never a bare integer — over a named ranking version, append-only. An import that adds pièces (a new
version) never moves what the line designates; placing the line never reorders the order. On
SQLite."""

from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import Base, LinePlacement
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestionResult
from apx.core.domain.cascade import Band, CascadeResult, PieceJudgement, Stage
from apx.core.domain.config import CascadeConfig
from apx.core.domain.ranking import RankingIdentityInputs, assemble_identity, rank_cascade

_CFG = CascadeConfig(uncertain_low=0.35, uncertain_high=0.65, calibration_sample=20,
                     stage3_max_share=0.5)


def _sf():  # noqa: ANN202
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    return sessionmaker(bind=e, future=True)


def _identity():  # noqa: ANN202
    inputs = RankingIdentityInputs(
        case_theory_version_id=None, model_provider="mistral",
        model_endpoint="https://api.mistral.ai/v1", model_name="mistral-small-latest",
        prompt_version="cascade-question-v1", temperature=0.0, sampling={"top_p": 1.0},
        embedder_model_id="bge-m3", embedder_model_version="1.5",
        chunking_config_version="chunk-v1", schema_version="slice-a")
    return assemble_identity(
        inputs=inputs, basis="intrinsic", uncertain_low=0.35, uncertain_high=0.65,
        calibration_sample=20, stage3_max_share=0.5)


def _judged(pid: str, band: Band, score: float) -> PieceJudgement:
    return PieceJudgement.judged(piece_id=pid, family_id=f"fam-{pid}", is_representative=True,
                                 stage_reached=Stage.STAGE_2, band=band, score=score)


def _order(pairs):  # noqa: ANN001,ANN202
    judgements = [_judged(pid, band, score) for pid, band, score in pairs]
    families = {j.family_id: (j.piece_id,) for j in judgements}
    result = CascadeResult(
        judgements=tuple(judgements), families=families, unscored=(), stage3_share=0.5,
        over_stage3_floor=False, basis="intrinsic")
    return rank_cascade(result, _CFG)


def _store_with_ranking(store=None):  # noqa: ANN001,ANN202
    """A store with matter 'm' (scope 'w') and a recorded ranking: rel(rank1), dis(rank2)."""
    store = store or SqlStore(_sf())
    store.save(IngestionResult(), scope="w", actor="setup", matter="m", tenant="t", audit=False)
    store.record_ranking(
        tenant="t", matter="m", actor="a", identity=_identity(),
        order=_order([("rel", Band.CONFIDENT_RELEVANT, 0.9), ("dis", Band.CONFIDENT_DISCARD, 0.1)]))
    return store


# ── AC-1 — the basis is inherited from the ranking version (case-theory or intrinsic) ───────────
def test_line_basis_is_inherited_from_the_ranking_version() -> None:
    ct = SimpleNamespace(basis="case-theory", case_theory_version_id="ctv-123")
    assert SqlStore._line_basis(ct) == "case-theory:ctv-123"
    intr = SimpleNamespace(basis="intrinsic", case_theory_version_id=None)
    assert SqlStore._line_basis(intr).startswith("intrinsic:")
    assert "document-type" in SqlStore._line_basis(intr)  # names the intrinsic signals (FR-38)


def test_place_line_commits_recall_first_and_names_the_last_retained_piece() -> None:
    store = _store_with_ranking()
    view = store.place_line(tenant="t", matter="m", actor="claire", scopes={"w"})
    assert view is not None
    assert view.last_retained_piece_id == "rel"       # deepest retain-band pièce (dis is discard)
    assert view.basis.startswith("intrinsic:")        # inherited from the ranking version
    assert view.seq == 1 and len(view.version_id) == 64  # names its version (AD-23)


# ── AC-2 — the current line is a VIEW naming its version, identified by the pièce ────────────────
def test_read_current_line_is_a_view_naming_its_version() -> None:
    store = _store_with_ranking()
    store.place_line(tenant="t", matter="m", actor="claire", scopes={"w"})
    cur = store.read_current_line(tenant="t", matter="m", scopes={"w"})
    assert cur is not None and cur.last_retained_piece_id == "rel" and cur.version_no == 1


def test_no_line_placed_yet_reads_none() -> None:
    store = _store_with_ranking()  # ranking exists, but no line placed
    assert store.read_current_line(tenant="t", matter="m", scopes={"w"}) is None


# ── AC-4 (invariant) — placing the line never reorders the underlying ranked order ──────────────
def test_placing_the_line_never_reorders_the_ranked_order() -> None:
    store = _store_with_ranking()
    before = [(r.piece_id, r.rank) for r in store.read_ranked_order(
        tenant="t", matter="m", scopes={"w"})]
    store.place_line(tenant="t", matter="m", actor="claire", scopes={"w"})
    after = [(r.piece_id, r.rank) for r in store.read_ranked_order(
        tenant="t", matter="m", scopes={"w"})]
    assert before == after  # byte-identical — the line is a different table


# ── AC-3 (failure path) — an import that adds pièces never moves what the line designates ────────
def test_the_line_stays_bound_to_its_version_when_an_import_adds_pieces() -> None:
    store = _store_with_ranking()
    store.place_line(tenant="t", matter="m", actor="claire", scopes={"w"}, version_no=1)
    # an import re-ranks and adds a pièce → a NEW version 2 (the order within v1 is immutable)
    store.record_ranking(
        tenant="t", matter="m", actor="a", identity=_identity(),
        order=_order([("rel", Band.CONFIDENT_RELEVANT, 0.9), ("dis", Band.CONFIDENT_DISCARD, 0.1),
                      ("new", Band.CONFIDENT_RELEVANT, 0.8)]))
    v1 = store.read_current_line(tenant="t", matter="m", scopes={"w"}, version_no=1)
    assert v1 is not None and v1.last_retained_piece_id == "rel" and v1.seq == 1  # unmoved
    # v2 has no line yet — the line did not silently jump onto the larger set
    assert store.read_current_line(tenant="t", matter="m", scopes={"w"}, version_no=2) is None


# ── AC-5 — honest non-commitment: no retain-band pièce → no line, nothing stored ────────────────
def test_all_confident_discard_commits_to_no_line() -> None:
    store = SqlStore(_sf())
    store.save(IngestionResult(), scope="w", actor="s", matter="m", tenant="t", audit=False)
    store.record_ranking(
        tenant="t", matter="m", actor="a", identity=_identity(),
        order=_order([("dis", Band.CONFIDENT_DISCARD, 0.1)]))
    assert store.place_line(tenant="t", matter="m", actor="claire", scopes={"w"}) is None
    assert store.read_current_line(tenant="t", matter="m", scopes={"w"}) is None
    with store._sf() as s:  # nothing written to the ledger
        assert s.scalar(select(func.count()).select_from(LinePlacement)) == 0


# ── append-only — a second placement is a new seq, the prior row stays ──────────────────────────
def test_a_second_placement_appends_a_new_seq() -> None:
    store = _store_with_ranking()
    first = store.place_line(tenant="t", matter="m", actor="claire", scopes={"w"})
    second = store.place_line(tenant="t", matter="m", actor="claire", scopes={"w"})
    assert first.seq == 1 and second.seq == 2
    with store._sf() as s:  # both rows present — append-only, never an overwrite (AD-7)
        assert s.scalar(select(func.count()).select_from(LinePlacement)) == 2
    assert store.read_current_line(  # the current line is the max-seq row
        tenant="t", matter="m", scopes={"w"}).seq == 2


# ── scope — non-disclosing ──────────────────────────────────────────────────────────────────────
def test_place_line_is_scope_gated() -> None:
    import pytest

    from apx.adapters.store_postgres.store import ScopeDenied
    store = _store_with_ranking()
    with pytest.raises(ScopeDenied):
        store.place_line(tenant="t", matter="m", actor="claire", scopes={"other"})


def test_read_current_line_out_of_scope_is_non_disclosing() -> None:
    store = _store_with_ranking()
    store.place_line(tenant="t", matter="m", actor="claire", scopes={"w"})
    assert store.read_current_line(tenant="t", matter="m", scopes={"other"}) is None
