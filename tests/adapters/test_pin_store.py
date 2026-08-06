"""pin_piece / remove_pin / read_current_pins (Story 4.11, FR-43/FR-25): the pin moves exactly one
pièce across the line, requires a one-line reason recorded as an override, and survives re-ranking.
Composed with read_triage_sets to prove exactly-one-moves. On SQLite."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import AuditRecord, Base, PinEntry
from apx.adapters.store_postgres.store import ScopeDenied, SqlStore, StalePin
from apx.core.app.ingest import IngestionResult
from apx.core.domain.cascade import Band, CascadeResult, PieceJudgement, Stage
from apx.core.domain.config import CascadeConfig
from apx.core.domain.pin import MissingPinReason
from apx.core.domain.ranking import RankingIdentityInputs, assemble_identity, rank_cascade
from apx.core.domain.triage_sets import Line, PinSide

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


_PAIRS = [("a", Band.CONFIDENT_RELEVANT, 0.9), ("b", Band.CONFIDENT_RELEVANT, 0.7),
          ("c", Band.CONFIDENT_DISCARD, 0.2), ("d", Band.CONFIDENT_DISCARD, 0.1)]


def _store():  # noqa: ANN202
    store = SqlStore(_sf())
    store.save(IngestionResult(), scope="w", actor="s", matter="m", tenant="t", audit=False)
    store.record_ranking(
        tenant="t", matter="m", actor="a", identity=_identity(), order=_order(_PAIRS))
    return store


# ── AC-1 — exactly one moves; the line + order do not change ─────────────────────────────────────
def test_pinning_moves_exactly_one_piece_and_nothing_else_changes() -> None:
    store = _store()
    store.place_line(tenant="t", matter="m", actor="a", scopes={"w"})  # line at 'b'
    line = Line("b")
    before = store.read_triage_sets(tenant="t", matter="m", scopes={"w"}, line=line)
    assert before.retained == ("a", "b") and before.discarded == ("c", "d")
    order_before = [(r.piece_id, r.rank) for r in store.read_ranked_order(
        tenant="t", matter="m", scopes={"w"})]
    line_before = store.read_current_line(tenant="t", matter="m", scopes={"w"})

    store.pin_piece(tenant="t", matter="m", actor="claire", scopes={"w"}, piece_id="c",
                    side=PinSide.RETAIN, reason="aveu au §4 — décisif")
    pins = store.read_current_pins(tenant="t", matter="m", scopes={"w"})
    after = store.read_triage_sets(tenant="t", matter="m", scopes={"w"}, line=line, pins=pins)

    assert after.retained == ("a", "b", "c")  # grew by EXACTLY one (c crossed)
    assert after.discarded == ("d",)          # every other membership identical
    assert after.pins_in_force == 1
    # the ranked order and the line did not move (pinning writes only pin_entry)
    assert [(r.piece_id, r.rank) for r in store.read_ranked_order(
        tenant="t", matter="m", scopes={"w"})] == order_before
    assert store.read_current_line(
        tenant="t", matter="m", scopes={"w"}).last_retained_piece_id == \
        line_before.last_retained_piece_id


# ── AC-2 — a pin requires a reason and is recorded as an override ────────────────────────────────
def test_a_blank_reason_is_refused_and_nothing_is_written() -> None:
    store = _store()
    with pytest.raises(MissingPinReason):
        store.pin_piece(tenant="t", matter="m", actor="c", scopes={"w"}, piece_id="c",
                        side=PinSide.RETAIN, reason="   ")
    with store._sf() as s:
        assert s.scalar(select(func.count()).select_from(PinEntry)) == 0


def test_a_pin_is_recorded_as_an_override_with_its_reason() -> None:
    store = _store()
    store.pin_piece(tenant="t", matter="m", actor="claire", scopes={"w"}, piece_id="c",
                    side=PinSide.RETAIN, reason="motif décisif")
    with store._sf() as s:
        detail = s.scalar(select(AuditRecord.detail).where(AuditRecord.action == "pin_override"))
        assert detail is not None and "reason=motif décisif" in detail and "action=retain" in detail


# ── AC-3 — survives re-ranking; removal is a recorded reversible act ─────────────────────────────
def test_a_pin_survives_re_ranking_because_the_ledger_is_version_independent() -> None:
    store = _store()
    store.pin_piece(tenant="t", matter="m", actor="claire", scopes={"w"}, piece_id="c",
                    side=PinSide.RETAIN, reason="décisif")
    store.record_ranking(  # a re-rank → a new ranking version 2
        tenant="t", matter="m", actor="a", identity=_identity(), order=_order(_PAIRS))
    pins = store.read_current_pins(tenant="t", matter="m", scopes={"w"})  # still in force
    assert tuple((p.piece_id, p.side) for p in pins) == (("c", PinSide.RETAIN),)
    v2 = store.read_triage_sets(
        tenant="t", matter="m", scopes={"w"}, line=Line("b"), pins=pins, version_no=2)
    assert "c" in v2.retained  # the pin applies to the NEW version too


def _order_c_unscored():  # noqa: ANN202
    # a re-rank where the cascade could NOT score 'c' (UNSCORED — a first-class outcome, AD-19)
    judgements = [_judged("a", Band.CONFIDENT_RELEVANT, 0.9),
                  _judged("b", Band.CONFIDENT_RELEVANT, 0.7),
                  _judged("d", Band.CONFIDENT_DISCARD, 0.1),
                  PieceJudgement.unscored(piece_id="c", family_id="fam-c", is_representative=True,
                                          failure_reason="judge-failed")]
    families = {j.family_id: (j.piece_id,) for j in judgements}
    result = CascadeResult(
        judgements=tuple(judgements), families=families, unscored=("c",), stage3_share=0.5,
        over_stage3_floor=False, basis="intrinsic")
    return rank_cascade(result, _CFG)


def test_a_surviving_pin_on_an_unscored_piece_is_dormant_not_a_crash() -> None:
    # AC-3 hardening (the review's confirmed finding): a pin survives re-ranking, but if the re-rank
    # marks the pinned pièce UNSCORED it has no line position to override in that version — it is
    # DORMANT for that view, never a crash. The pin stays in force for when the pièce is re-scored.
    store = _store()
    store.pin_piece(tenant="t", matter="m", actor="claire", scopes={"w"}, piece_id="c",
                    side=PinSide.RETAIN, reason="décisif")
    store.record_ranking(  # re-rank v2: 'c' is UNSCORED (its judgement failed)
        tenant="t", matter="m", actor="a", identity=_identity(), order=_order_c_unscored())
    pins = store.read_current_pins(tenant="t", matter="m", scopes={"w"})
    assert any(p.piece_id == "c" for p in pins)  # the pin still survives (version-independent)
    # the primary triage read over v2 must NOT crash — the dormant pin is filtered out
    v2 = store.read_triage_sets(
        tenant="t", matter="m", scopes={"w"}, line=Line("b"), pins=pins, version_no=2)
    assert v2 is not None
    assert "c" in v2.unscored       # 'c' is honestly in the unscored tail (its judgement failed)
    assert "c" not in v2.retained   # the pin is dormant — never imputed into retained (AD-19)


def test_removing_a_pin_is_an_appended_reversible_audited_act() -> None:
    store = _store()
    store.pin_piece(tenant="t", matter="m", actor="claire", scopes={"w"}, piece_id="c",
                    side=PinSide.RETAIN, reason="décisif")
    store.remove_pin(tenant="t", matter="m", actor="claire", scopes={"w"}, piece_id="c")
    assert store.read_current_pins(tenant="t", matter="m", scopes={"w"}) == ()  # no longer in force
    with store._sf() as s:  # BOTH rows remain — append-only (the removal did not delete the pin)
        assert s.scalar(select(func.count()).select_from(PinEntry).where(
            PinEntry.piece_id == "c")) == 2
        assert s.scalar(select(func.count()).select_from(AuditRecord).where(
            AuditRecord.action == "pin_removed")) == 1


def test_removing_a_piece_with_no_active_pin_fails_loudly() -> None:
    store = _store()
    with pytest.raises(ValueError, match="no active pin"):
        store.remove_pin(tenant="t", matter="m", actor="c", scopes={"w"}, piece_id="c")


def test_a_stale_expected_seq_is_refused() -> None:
    store = _store()
    store.pin_piece(tenant="t", matter="m", actor="c", scopes={"w"}, piece_id="c",
                    side=PinSide.RETAIN, reason="r")  # seq 1
    with pytest.raises(StalePin):  # a caller who still thinks seq is 0 is refused
        store.pin_piece(tenant="t", matter="m", actor="c", scopes={"w"}, piece_id="c",
                        side=PinSide.DISCARD, reason="r2", expected_seq=0)


def test_the_pin_reads_are_scope_gated_and_non_disclosing() -> None:
    store = _store()
    assert store.read_current_pins(tenant="t", matter="m", scopes={"other"}) is None
    with pytest.raises(ScopeDenied):
        store.pin_piece(tenant="t", matter="m", actor="c", scopes={"other"}, piece_id="c",
                        side=PinSide.RETAIN, reason="r")
