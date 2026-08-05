"""SM-17 — the confidence calibration harness (Story 4.4, FR-42/AD-34).

Exercises the calibration MATH now (the full gold-corpus run defers like recall_at_the_line): among
the pièces in a band, compare the derivation's CLAIMED mean confidence to the OBSERVED relevant
share,
and flag a systematically overconfident derivation so the build gate can fire."""

from __future__ import annotations

import pytest

from eval.harness import confidence_calibration


def test_a_well_calibrated_derivation_is_not_flagged() -> None:
    # the claim is a P(relevant) — a DIRECTIONAL confidence is converted upstream (p_relevant = c
    # for a relevant band, 1 - c for a discard band), so all three bands are compared like-for-like.
    result = confidence_calibration({
        "confident-relevant": (0.80, 90, 100),   # claims P(rel)=0.80, 0.90 observed → under
        "uncertain": (0.35, 40, 100),            # claims P(rel)=0.35, 0.40 observed → under
        # a deep confident-DISCARD pièce is HIGH confidence (~0.9) it is IRRELEVANT → P(rel) ≈ 0.10;
        # against a 0.05 observed relevant share that is +0.05, within tolerance — NOT
        # overconfident.
        "confident-discard": (0.10, 5, 100),
    })
    assert not result.systematically_overconfident
    shares = {b.band: b.observed_share for b in result.bands}
    assert shares["confident-relevant"] == pytest.approx(0.9)


def test_a_directional_confidence_must_be_converted_to_p_relevant() -> None:
    # the contract guards the trap the review surfaced: passing a RAW discard confidence (0.9) as if
    # it were a P(relevant) would spuriously read as overconfident — the caller must convert first.
    # A P(relevant) outside [0, 1] is refused, so a raw directional confidence cannot slip through
    # unconverted when it lies out of range; and the CONVERTED value (1 - 0.9 = 0.10) is
    # well-behaved.
    ok = confidence_calibration({"confident-discard": (1.0 - 0.9, 5, 100)})
    assert not ok.systematically_overconfident
    with pytest.raises(ValueError, match="convert a directional confidence"):
        confidence_calibration({"confident-discard": (1.5, 5, 100)})


def test_a_systematically_overconfident_derivation_is_flagged() -> None:
    # claims 0.95 confidence in a band where only 40% were actually relevant → the gate fires
    result = confidence_calibration({"confident-relevant": (0.95, 40, 100)}, tolerance=0.1)
    assert result.systematically_overconfident
    (band,) = result.bands
    assert band.overconfidence_gap == pytest.approx(0.55)


def test_a_degenerate_observation_is_rejected() -> None:
    with pytest.raises(ValueError, match="total must be positive"):
        confidence_calibration({"b": (0.5, 0, 0)})
    with pytest.raises(ValueError, match="out of"):
        confidence_calibration({"b": (0.5, 10, 5)})
