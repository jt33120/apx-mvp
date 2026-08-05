"""SM-17 — the ranking-projection calibration harness (Story 4.9, FR-19). A systematically
OPTIMISTIC projection (it claims the discarded set is cleaner than it is) fails the build gate."""

from __future__ import annotations

import pytest

from eval.harness import projection_calibration


def test_a_well_calibrated_projection_is_not_flagged() -> None:
    result = projection_calibration({
        "confident-relevant": (0.80, 82, 100),   # projects P(rel)=0.80, 0.82 observed → within tol
        "uncertain": (0.50, 55, 100),            # projects 0.50, 0.55 observed → within tol
        "confident-discard": (0.10, 8, 100),     # projects 0.10, 0.08 observed → within tol
    })
    assert not result.systematically_optimistic
    shares = {b.band: b.observed_share for b in result.bands}
    assert shares["confident-discard"] == pytest.approx(0.08)


def test_a_systematically_optimistic_projection_is_flagged() -> None:
    # projects only 5% relevant in the discard band where 40% actually were relevant → gate fires
    result = projection_calibration({"confident-discard": (0.05, 40, 100)}, tolerance=0.1)
    assert result.systematically_optimistic
    (band,) = result.bands
    assert band.optimism_gap == pytest.approx(0.35)  # observed 0.40 − projected 0.05


def test_a_directional_confidence_must_be_converted_first() -> None:
    with pytest.raises(ValueError, match="convert a directional confidence"):
        projection_calibration({"confident-discard": (1.5, 5, 100)})


def test_a_degenerate_observation_is_rejected() -> None:
    with pytest.raises(ValueError, match="total must be positive"):
        projection_calibration({"b": (0.5, 0, 0)})
    with pytest.raises(ValueError, match="out of"):
        projection_calibration({"b": (0.5, 10, 5)})
