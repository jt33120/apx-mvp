"""Per-pièce confidence derivation — pure, from observable cascade quantities (Story 4.4, FR-42).

Deterministic, no DB/net: derived from score margin + cross-stage agreement, never a model-reported
figure; None (not derived) for unscored/rejected/no-observable (AD-19); monotone in the margin;
conflict < agreement; a boundary pièce is low (the not-overconfident property SM-17's gate rests
on)."""

from __future__ import annotations

import pytest

from apx.core.domain.cascade import Band, PieceJudgement, RejectionClass, Stage
from apx.core.domain.config import CascadeConfig
from apx.core.domain.piece_confidence import (
    Confidence,
    ConfidenceSignal,
    derive_confidence,
)

_CFG = CascadeConfig(uncertain_low=0.35, uncertain_high=0.65, calibration_sample=0,
                     stage3_max_share=0.5)


def _judged(band: Band, *, score: float | None, label: str | None = None) -> PieceJudgement:
    return PieceJudgement.judged(piece_id="p", family_id="f", is_representative=True,
                                 stage_reached=Stage.STAGE_3 if label else Stage.STAGE_2,
                                 band=band, score=score, label=label)


def _conf(band: Band, *, score: float | None, label: str | None = None) -> float | None:
    c = derive_confidence(_judged(band, score=score, label=label), _CFG)
    return c.value if c is not None else None


def test_unscored_and_rejected_are_not_derived() -> None:
    unscored = PieceJudgement.unscored(piece_id="p", family_id="f", is_representative=True,
                                       failure_reason="RuntimeError")
    rejected = PieceJudgement.rejected(piece_id="p", family_id="f", is_representative=False,
                                       stage_reached=Stage.STAGE_1,
                                       rejection_class=RejectionClass.EXACT_DUPLICATE_MEMBER)
    assert derive_confidence(unscored, _CFG) is None  # judgement failed — never imputed (AD-19)
    assert derive_confidence(rejected, _CFG) is None   # a duplicate has no judgement of its own


def test_a_confident_band_derives_from_the_score_margin() -> None:
    c = derive_confidence(_judged(Band.CONFIDENT_RELEVANT, score=0.9), _CFG)
    assert c is not None and 0.0 <= c.value <= 1.0
    assert ConfidenceSignal.SCORE_MARGIN in c.signals
    # (0.9 - 0.65) / (1 - 0.65) = 0.714…
    assert c.value == pytest.approx((0.9 - 0.65) / (1.0 - 0.65))


def test_a_boundary_piece_is_low_confidence() -> None:
    # a score exactly at the band boundary is barely confident → ~0 (the not-overconfident property)
    assert _conf(Band.CONFIDENT_RELEVANT, score=0.65) == pytest.approx(0.0)
    assert _conf(Band.CONFIDENT_DISCARD, score=0.35) == pytest.approx(0.0)


def test_confidence_is_monotone_non_decreasing_in_the_margin() -> None:
    lo = _conf(Band.CONFIDENT_RELEVANT, score=0.70)
    mid = _conf(Band.CONFIDENT_RELEVANT, score=0.85)
    hi = _conf(Band.CONFIDENT_RELEVANT, score=1.0)
    assert lo is not None and mid is not None and hi is not None
    assert lo <= mid <= hi and hi == pytest.approx(1.0)  # score at the extreme → full margin


def test_a_cross_stage_conflict_yields_lower_confidence_than_agreement() -> None:
    agree = _conf(Band.CONFIDENT_RELEVANT, score=0.9, label="relevant")
    conflict = _conf(Band.CONFIDENT_RELEVANT, score=0.9, label="discard")
    assert agree is not None and conflict is not None
    assert conflict < agree  # a stage-2/stage-3 conflict deflates the confidence
    c = derive_confidence(_judged(Band.CONFIDENT_RELEVANT, score=0.9, label="discard"), _CFG)
    assert c is not None and ConfidenceSignal.CROSS_STAGE_AGREEMENT in c.signals


def test_the_uncertain_band_derives_from_the_llm_label_decisiveness() -> None:
    decisive = _conf(Band.UNCERTAIN, score=0.5, label="relevant")
    indecisive = _conf(Band.UNCERTAIN, score=0.5, label="uncertain")
    assert decisive is not None and indecisive is not None and indecisive < decisive
    # an intrinsic pièce (no score) with a decisive label still derives from the agreement signal
    intrinsic = derive_confidence(_judged(Band.UNCERTAIN, score=None, label="relevant"), _CFG)
    assert intrinsic is not None and ConfidenceSignal.CROSS_STAGE_AGREEMENT in intrinsic.signals


def test_a_judged_piece_with_no_score_and_no_label_is_not_derived() -> None:
    assert derive_confidence(_judged(Band.UNCERTAIN, score=None, label=None), _CFG) is None


def test_confidence_value_object_rejects_out_of_range_or_empty_signals() -> None:
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        Confidence(value=1.5, signals=(ConfidenceSignal.SCORE_MARGIN,))
    with pytest.raises(ValueError, match="at least one observable signal"):
        Confidence(value=0.5, signals=())
