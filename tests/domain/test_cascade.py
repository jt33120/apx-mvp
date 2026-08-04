"""The cascade domain — the AD-36/AD-19 tagged outcome is exhaustive and mutually exclusive."""

from __future__ import annotations

import pytest

from apx.core.domain.cascade import (
    Band,
    CascadeResult,
    Outcome,
    PieceJudgement,
    RejectionClass,
    Stage,
)


def test_a_judged_piece_needs_a_band_and_carries_no_rejection_or_failure() -> None:
    j = PieceJudgement.judged(
        piece_id="p", family_id="f", is_representative=True, stage_reached=Stage.STAGE_2,
        band=Band.CONFIDENT_RELEVANT, score=0.9)
    assert j.outcome is Outcome.JUDGED and j.rejection_class is None and j.failure_reason is None
    with pytest.raises(ValueError, match="must carry a band"):
        PieceJudgement(piece_id="p", family_id="f", is_representative=True,
                       stage_reached=Stage.STAGE_2, outcome=Outcome.JUDGED)


def test_a_rejected_piece_needs_a_class_and_is_never_scored() -> None:
    j = PieceJudgement.rejected(
        piece_id="p", family_id="f", is_representative=False, stage_reached=Stage.STAGE_1,
        rejection_class=RejectionClass.EXACT_DUPLICATE_MEMBER)
    assert j.outcome is Outcome.REJECTED and j.score is None and j.band is None
    with pytest.raises(ValueError, match="rejection_class"):
        PieceJudgement(piece_id="p", family_id="f", is_representative=False,
                       stage_reached=Stage.STAGE_1, outcome=Outcome.REJECTED)


def test_an_unscored_piece_is_never_imputed_a_score_or_label() -> None:
    j = PieceJudgement.unscored(
        piece_id="p", family_id="f", is_representative=True, failure_reason="RuntimeError")
    assert j.outcome is Outcome.UNSCORED and j.score is None and j.band is None and j.label is None
    # an unscored pièce carrying a score is a contradiction (AD-19: never imputed)
    with pytest.raises(ValueError, match="never imputed"):
        PieceJudgement(piece_id="p", family_id="f", is_representative=True,
                       stage_reached=Stage.STAGE_3, outcome=Outcome.UNSCORED,
                       failure_reason="x", score=0.0)


def test_result_consistency_ties_the_unscored_set_to_the_unscored_outcomes() -> None:
    judged = PieceJudgement.judged(
        piece_id="a", family_id="fa", is_representative=True, stage_reached=Stage.STAGE_3,
        band=Band.UNCERTAIN, label="relevant")
    failed = PieceJudgement.unscored(
        piece_id="b", family_id="fb", is_representative=True, failure_reason="err")
    ok = CascadeResult(judgements=(judged, failed), families={"fa": ("a",), "fb": ("b",)},
                       unscored=("b",), stage3_share=1.0, over_stage3_floor=True, basis="ct")
    assert ok.is_consistent() and [p.piece_id for p in ok.in_order] == ["a"]  # unscored is out
    bad = CascadeResult(judgements=(judged, failed), families={}, unscored=(),  # forgot 'b'
                        stage3_share=1.0, over_stage3_floor=True, basis="case-theory")
    assert not bad.is_consistent()


def test_rejection_and_intrinsic_enums_are_string_valued_and_stable() -> None:
    assert RejectionClass.EXACT_DUPLICATE_MEMBER == "exact-duplicate-member"
    assert Band.UNCERTAIN == "uncertain"
