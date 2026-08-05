"""The ranked order + the reproducible ranking version — pure domain (Story 4.3, FR-39/AD-23).

Deterministic, no DB, no network: the identity fingerprint is stable and input-sensitive; the order
is a pure function of the cascade outputs + pièce identity hashes; ties break by the pièce id in
byte
order (locale-independent); near-duplicate families stay contiguous (representative first); a
REJECTED
member stays in the order (AD-36); an UNSCORED pièce is out of the order, never ranked (AD-19)."""

from __future__ import annotations

import locale

import pytest

from apx.core.domain.cascade import Band, CascadeResult, Outcome, PieceJudgement, Stage
from apx.core.domain.cascade import RejectionClass as RC
from apx.core.domain.config import CascadeConfig
from apx.core.domain.piece_confidence import CONFIDENCE_METHOD, ConfidenceSignal
from apx.core.domain.ranking import (
    GROUPING_IDENTITY,
    TIE_BREAK,
    RankedOrder,
    RankedRow,
    RankingIdentity,
    RankingIdentityInputs,
    RankingVersion,
    assemble_identity,
    rank_cascade,
)

_CFG = CascadeConfig(uncertain_low=0.35, uncertain_high=0.65, calibration_sample=20,
                     stage3_max_share=0.5)


# ── identity fixtures ───────────────────────────────────────────────────────────────────────────
def _inputs(**over: object) -> RankingIdentityInputs:
    base = dict(
        case_theory_version_id="ct-v1", model_provider="mistral",
        model_endpoint="https://api.mistral.ai/v1", model_name="mistral-small-latest",
        prompt_version="cascade-question-v1", temperature=0.0, sampling={"top_p": 1.0, "seed": 7},
        embedder_model_id="bge-m3", embedder_model_version="1.5",
        chunking_config_version="chunk-v1", schema_version="slice-a")
    base.update(over)
    return RankingIdentityInputs(**base)  # type: ignore[arg-type]


def _identity(basis: str = "case-theory", **over: object) -> RankingIdentity:
    return assemble_identity(
        inputs=_inputs(**over), basis=basis,
        uncertain_low=0.35, uncertain_high=0.65, calibration_sample=20, stage3_max_share=0.5)


def test_identity_fingerprint_is_deterministic_and_input_sensitive() -> None:
    a, b = _identity(), _identity()
    assert a.fingerprint == b.fingerprint  # same inputs → same fingerprint
    assert a.grouping_identity == GROUPING_IDENTITY and a.tie_break == TIE_BREAK
    assert _identity(model_name="mistral-large").fingerprint != a.fingerprint  # a change → new id
    assert _identity(temperature=0.7).fingerprint != a.fingerprint
    # insertion order of the sampling map does not change the canonical fingerprint (sorted keys)
    assert _identity(sampling={"seed": 7, "top_p": 1.0}).fingerprint == a.fingerprint


def test_version_id_is_referenceable_and_binds_matter_and_version_no() -> None:
    v1 = RankingVersion.build(tenant="t", matter="m", version_no=1, identity=_identity())
    again = RankingVersion.build(tenant="t", matter="m", version_no=1, identity=_identity())
    assert v1.version_id == again.version_id and len(v1.version_id) == 64  # deterministic sha256
    # same identity, different matter/version → distinct referenceable rows
    assert RankingVersion.build(
        tenant="t", matter="other", version_no=1, identity=_identity()).version_id != v1.version_id
    assert RankingVersion.build(
        tenant="t", matter="m", version_no=2, identity=_identity()).version_id != v1.version_id


def test_a_blank_identity_input_is_rejected_and_case_theory_needs_its_id() -> None:
    with pytest.raises(ValueError, match="model_name"):
        _identity(model_name="  ")
    with pytest.raises(ValueError, match="case_theory_version_id"):
        # a case-theory basis with no case theory version id is dishonest (AD-23)
        assemble_identity(
            inputs=_inputs(case_theory_version_id=None), basis="case-theory",
            uncertain_low=0.35, uncertain_high=0.65, calibration_sample=20, stage3_max_share=0.5)
    # the intrinsic path legitimately carries no case theory version id
    assert _identity(basis="intrinsic", case_theory_version_id=None).case_theory_version_id is None


# ── ranking fixtures ────────────────────────────────────────────────────────────────────────────
def _judged(pid: str, fid: str, band: Band, *, score: float | None, label: str | None = None,
            rep: bool = True, stage: Stage = Stage.STAGE_2) -> PieceJudgement:
    return PieceJudgement.judged(piece_id=pid, family_id=fid, is_representative=rep,
                                 stage_reached=stage, band=band, score=score, label=label)


def _rejected(pid: str, fid: str) -> PieceJudgement:
    return PieceJudgement.rejected(piece_id=pid, family_id=fid, is_representative=False,
                                   stage_reached=Stage.STAGE_1,
                                   rejection_class=RC.EXACT_DUPLICATE_MEMBER)


def _unscored(pid: str, fid: str) -> PieceJudgement:
    return PieceJudgement.unscored(piece_id=pid, family_id=fid, is_representative=True,
                                   failure_reason="RuntimeError")


def _result(judgements: list[PieceJudgement], *, unscored: tuple[str, ...] = (),
            basis: str = "case-theory") -> CascadeResult:
    families: dict[str, list[str]] = {}
    for j in judgements:
        families.setdefault(j.family_id, []).append(j.piece_id)
    return CascadeResult(
        judgements=tuple(judgements), families={k: tuple(v) for k, v in families.items()},
        unscored=unscored, stage3_share=0.25, over_stage3_floor=False, basis=basis)


def _rank(judgements: list[PieceJudgement], **kw: object) -> RankedOrder:
    return rank_cascade(_result(judgements, **kw), _CFG)  # type: ignore[arg-type]


def test_the_relevance_ladder_orders_bands_then_the_uncertain_label() -> None:
    # one pièce per family, one per tier — the honest ladder: CR > uncertain-relevant >
    # uncertain-uncertain > uncertain-discard > CD (band first, the label refines the uncertain
    # band).
    js = [
        _judged("cd", "f-cd", Band.CONFIDENT_DISCARD, score=0.1),
        _judged("ud", "f-ud", Band.UNCERTAIN, score=0.5, label="discard", stage=Stage.STAGE_3),
        _judged("cr", "f-cr", Band.CONFIDENT_RELEVANT, score=0.9),
        _judged("uu", "f-uu", Band.UNCERTAIN, score=0.5, label="uncertain", stage=Stage.STAGE_3),
        _judged("ur", "f-ur", Band.UNCERTAIN, score=0.5, label="relevant", stage=Stage.STAGE_3),
    ]
    order = _rank(js)
    assert [r.piece_id for r in order.rows] == ["cr", "ur", "uu", "ud", "cd"]
    assert order.is_consistent() and [r.rank for r in order.rows] == [1, 2, 3, 4, 5]


def test_within_a_tier_score_descends_then_the_piece_id_breaks_the_tie() -> None:
    js = [  # three confident-relevant families: 0.9 and 0.9 (tie → piece id) then 0.8
        _judged("bbb", "f-b", Band.CONFIDENT_RELEVANT, score=0.9),
        _judged("aaa", "f-a", Band.CONFIDENT_RELEVANT, score=0.9),
        _judged("ccc", "f-c", Band.CONFIDENT_RELEVANT, score=0.8),
    ]
    order = _rank(js)
    assert [r.piece_id for r in order.rows] == ["aaa", "bbb", "ccc"]  # 0.9 tie → id asc, then 0.8


def test_a_near_duplicate_family_is_contiguous_representative_first() -> None:
    js = [
        _judged("rep1", "fam1", Band.CONFIDENT_RELEVANT, score=0.9),
        _rejected("dup_b", "fam1"), _rejected("dup_a", "fam1"),
        _judged("rep2", "fam2", Band.CONFIDENT_DISCARD, score=0.1),
    ]
    order = _rank(js)
    ids = [r.piece_id for r in order.rows]
    assert ids == ["rep1", "dup_a", "dup_b", "rep2"]  # family1 contiguous, rep first, members asc
    dup = next(r for r in order.rows if r.piece_id == "dup_a")
    assert dup.outcome is Outcome.REJECTED and dup.rejection_class is RC.EXACT_DUPLICATE_MEMBER
    assert dup.rank is not None and not dup.is_representative  # a rejected member IS in the order
    assert order.is_consistent()


def test_an_unscored_piece_is_out_of_the_order_and_collected_never_ranked() -> None:
    js = [_judged("ok", "f-ok", Band.UNCERTAIN, score=0.5, label="relevant", stage=Stage.STAGE_3),
          _unscored("bad", "f-bad")]
    order = _rank(js, unscored=("bad",))
    assert [r.piece_id for r in order.rows] == ["ok"]           # the unscored pièce is NOT ranked
    assert order.unscored == ("bad",)
    (u,) = order.unscored_rows
    assert u.rank is None and u.outcome is Outcome.UNSCORED and u.score is None  # never imputed


def test_an_unscored_representative_keeps_its_duplicates_in_the_order() -> None:
    # the rep's only judge failed (unscored, out of the order) but its exact-duplicate members are
    # REJECTED and stay IN the order (AD-36) — recall-first never buries them.
    js = [_unscored("rep", "fam"), _rejected("dup", "fam"),
          _judged("cr", "f-cr", Band.CONFIDENT_RELEVANT, score=0.9)]
    order = _rank(js, unscored=("rep",))
    assert "rep" in order.unscored and "rep" not in [r.piece_id for r in order.rows]
    dup = next(r for r in order.rows if r.piece_id == "dup")
    assert dup.rank is not None  # the duplicate of an un-judgeable document is still in the order
    assert order.is_consistent()


def test_the_order_is_identical_under_two_lc_collate_settings() -> None:
    # AC-3: the tie-break is byte-ordered over the pièce id, never collated text — so a different
    # LC_COLLATE cannot reshuffle the order. rank_cascade sorts in Python by the ASCII-hex id
    # (codepoint == byte order), touching no locale; assert the identical sequence under two
    # locales.
    js = [_judged("aaa", "f-a", Band.CONFIDENT_RELEVANT, score=0.9),
          _judged("bbb", "f-b", Band.CONFIDENT_RELEVANT, score=0.9)]
    baseline = [r.piece_id for r in _rank(js).rows]
    for loc in ("C", "en_US.UTF-8"):
        try:
            locale.setlocale(locale.LC_COLLATE, loc)
        except locale.Error:
            continue  # the locale is not installed on this box — skip, never fail the build
        assert [r.piece_id for r in _rank(js).rows] == baseline
    locale.setlocale(locale.LC_COLLATE, "C")


def _jrow(pid: str, rank: int, fid: str) -> RankedRow:
    return RankedRow(pid, rank, fid, True, Outcome.JUDGED, score=0.9, band=Band.CONFIDENT_RELEVANT)


def _rrow(pid: str, rank: int, fid: str) -> RankedRow:
    return RankedRow(pid, rank, fid, False, Outcome.REJECTED,
                     rejection_class=RC.EXACT_DUPLICATE_MEMBER)


def test_is_consistent_rejects_a_non_contiguous_or_double_membership_order() -> None:
    assert RankedOrder(rows=(_jrow("a", 1, "f"),), unscored_rows=()).is_consistent()
    assert not RankedOrder(  # ranks must be 1..N
        rows=(_jrow("a", 2, "f"),), unscored_rows=()).is_consistent()
    split = RankedOrder(  # family f re-entered after leaving it — not contiguous
        rows=(_jrow("a", 1, "f"), _jrow("b", 2, "g"), _rrow("c", 3, "f")), unscored_rows=())
    assert not split.is_consistent()


def test_a_non_finite_score_stays_deterministic_over_the_identity_hash() -> None:
    # defence in depth: a NaN score must NOT short-circuit the tie-break (NaN != NaN) and make the
    # order input-order-dependent — it is neutralised to no-score so the piece-id hash decides. The
    # order must be identical regardless of the input order (the production scorer cannot emit a
    # NaN, but rank_cascade is a pure function and must be robust to its inputs).
    nan = float("nan")
    fwd = [_judged("aaa", "f-a", Band.UNCERTAIN, score=nan, label="uncertain", stage=Stage.STAGE_3),
           _judged("bbb", "f-b", Band.UNCERTAIN, score=nan, label="uncertain", stage=Stage.STAGE_3),
           _judged("ccc", "f-c", Band.UNCERTAIN, score=nan, label="uncertain", stage=Stage.STAGE_3)]
    rev = list(reversed(fwd))
    order_fwd = [r.piece_id for r in _rank(fwd).rows]
    order_rev = [r.piece_id for r in _rank(rev).rows]
    assert order_fwd == order_rev == ["aaa", "bbb", "ccc"]  # id-ascending, input-order-independent


def test_the_intrinsic_path_has_no_scores_and_orders_by_the_identity_hash() -> None:
    # no case theory → every rep has score None; the order falls through purely to the id tie-break.
    js = [_judged("z", "f-z", Band.UNCERTAIN, score=None, label="uncertain", stage=Stage.STAGE_3),
          _judged("a", "f-a", Band.UNCERTAIN, score=None, label="uncertain", stage=Stage.STAGE_3)]
    order = _rank(js, basis="intrinsic")
    assert [r.piece_id for r in order.rows] == ["a", "z"]  # id ascending, no score to separate
    assert all(r.score is None for r in order.rows)


# ── Story 4.4: the derived confidence rides on the row + the identity records the method ──────────
def test_the_identity_records_the_confidence_method_and_a_change_flips_the_fingerprint() -> None:
    ident = _identity()
    assert ident.confidence_method == CONFIDENCE_METHOD
    import dataclasses
    moved = dataclasses.replace(ident, confidence_method="margin-agreement-v2")
    assert moved.fingerprint != ident.fingerprint  # a derivation-method change is a new version


def test_rank_cascade_attaches_a_derived_confidence_never_for_unscored_or_rejected() -> None:
    js = [_judged("cr", "f-cr", Band.CONFIDENT_RELEVANT, score=0.9),
          _judged("rep", "fam", Band.CONFIDENT_RELEVANT, score=0.9),
          _rejected("dup", "fam"), _unscored("bad", "f-bad")]
    order = _rank(js, unscored=("bad",))
    by = {r.piece_id: r for r in order.all_rows}
    assert by["cr"].confidence is not None and 0.0 <= by["cr"].confidence <= 1.0
    assert ConfidenceSignal.SCORE_MARGIN in by["cr"].confidence_signals
    assert by["dup"].confidence is None and by["dup"].confidence_signals == ()  # duplicate (AD-19)
    assert by["bad"].confidence is None and by["bad"].confidence_signals == ()  # unscored (AD-19)
    # confidence never reorders — the order is 4.3's relevance ladder, unchanged
    assert [r.rank for r in order.rows] == [1, 2, 3]
