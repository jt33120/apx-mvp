"""price_line_move (the projection preview) + move_line (the serialised, audited human move)
(Story 4.9, FR-19). The priced figure is a projection from the ranking; the move is serialised (a
superseded position is refused) and audited with the priced statement shown. On SQLite."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import AuditRecord, Base, LinePlacement
from apx.adapters.store_postgres.store import ScopeDenied, SqlStore, StaleLine
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


def _store():  # noqa: ANN202
    """A store with matter 'm' (scope 'w') ranked: a,b confident-relevant; c,d confident-discard."""
    store = SqlStore(_sf())
    store.save(IngestionResult(), scope="w", actor="s", matter="m", tenant="t", audit=False)
    store.record_ranking(
        tenant="t", matter="m", actor="a", identity=_identity(),
        order=_order([("a", Band.CONFIDENT_RELEVANT, 0.9), ("b", Band.CONFIDENT_RELEVANT, 0.7),
                      ("c", Band.CONFIDENT_DISCARD, 0.2), ("d", Band.CONFIDENT_DISCARD, 0.1)]))
    return store


# ── price_line_move — the projection preview (AC-1/4/5) ─────────────────────────────────────────
def test_price_move_reports_delta_pieces_and_projected_prevalence() -> None:
    store = _store()
    store.place_line(tenant="t", matter="m", actor="a", scopes={"w"})  # system line at 'b'
    move = store.price_line_move(
        tenant="t", matter="m", scopes={"w"}, candidate_last_retained_piece_id="c")
    assert move is not None
    assert move.pieces_to_read_delta == 1               # retained b→c grows the read pile by one
    assert move.candidate_prevalence is not None        # a projection is available
    assert 0.0 <= move.candidate_prevalence <= 1.0


def test_retain_everything_says_no_bound_never_zero() -> None:
    store = _store()
    move = store.price_line_move(
        tenant="t", matter="m", scopes={"w"}, candidate_last_retained_piece_id="d")  # retains all
    assert move is not None and move.discarded_empty is True
    assert move.candidate_prevalence is None and move.prevalence_available is False


def test_price_move_is_scope_gated_and_non_disclosing() -> None:
    store = _store()
    assert store.price_line_move(
        tenant="t", matter="m", scopes={"other"}, candidate_last_retained_piece_id="b") is None


# ── move_line — the serialised, audited human move (AC-6) ────────────────────────────────────────
def test_a_fresh_move_appends_a_placement_and_audits_the_priced_statement() -> None:
    store = _store()
    placed = store.place_line(tenant="t", matter="m", actor="a", scopes={"w"})  # seq 1, line at 'b'
    view = store.move_line(
        tenant="t", matter="m", actor="claire", scopes={"w"}, last_retained_piece_id="c",
        expected_seq=placed.seq, priced_statement="1 pièce de plus à lire ; prévalence ~0.15")
    assert view.last_retained_piece_id == "c" and view.seq == placed.seq + 1
    cur = store.read_current_line(tenant="t", matter="m", scopes={"w"})
    assert cur.last_retained_piece_id == "c"  # the move is now the current line
    with store._sf() as s:
        detail = s.scalar(
            select(AuditRecord.detail).where(AuditRecord.action == "line_moved"))
        assert "old=" in detail and "new=" in detail and "priced=" in detail  # FR-19 recording


def test_a_move_against_a_superseded_position_is_refused_with_the_current_shown() -> None:
    store = _store()
    store.place_line(tenant="t", matter="m", actor="a", scopes={"w"})  # seq 1
    # a caller who thinks the line is still unplaced (expected_seq=0) is refused (StaleLine)
    with pytest.raises(StaleLine) as exc:
        store.move_line(
            tenant="t", matter="m", actor="claire", scopes={"w"}, last_retained_piece_id="c",
            expected_seq=0, priced_statement="stale")
    assert exc.value.current_seq == 1 and exc.value.current_last_retained_piece_id == "b"
    with store._sf() as s:  # nothing written beyond the original placement
        assert s.scalar(select(func.count()).select_from(LinePlacement)) == 1


def test_move_line_never_reorders_the_ranked_order() -> None:
    store = _store()
    before = [(r.piece_id, r.rank) for r in store.read_ranked_order(
        tenant="t", matter="m", scopes={"w"})]
    store.move_line(
        tenant="t", matter="m", actor="claire", scopes={"w"}, last_retained_piece_id="c",
        expected_seq=0, priced_statement="p")
    after = [(r.piece_id, r.rank) for r in store.read_ranked_order(
        tenant="t", matter="m", scopes={"w"})]
    assert before == after


def test_move_line_rejects_a_piece_not_in_the_order() -> None:
    store = _store()
    with pytest.raises(ValueError, match="not in the ranked order"):
        store.move_line(
            tenant="t", matter="m", actor="claire", scopes={"w"}, last_retained_piece_id="zzz",
            expected_seq=0, priced_statement="p")


def test_move_line_is_scope_gated() -> None:
    store = _store()
    with pytest.raises(ScopeDenied):
        store.move_line(
            tenant="t", matter="m", actor="claire", scopes={"other"}, last_retained_piece_id="c",
            expected_seq=0, priced_statement="p")
