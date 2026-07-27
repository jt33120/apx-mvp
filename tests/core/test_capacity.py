"""Storage footprint and the pre-flight capacity check (story 1.11, AD-32): the footprint is
stated, and an import projected not to fit is refused — before it starts, not at 70 %. Pure core.
"""

from __future__ import annotations

from apx.core.domain.capacity import (
    BYTES_PER_PIECE,
    DESIGN_TARGET_PIECES,
    design_target_footprint,
    fits,
    footprint,
)


def test_footprint_is_count_times_the_stated_estimate() -> None:
    fp = footprint(1000)
    assert fp.piece_count == 1000 and fp.total_bytes == 1000 * BYTES_PER_PIECE
    assert "MB" in fp.human or "GB" in fp.human  # a human-readable figure is stated


def test_design_target_footprint_is_stated() -> None:
    fp = design_target_footprint()
    assert fp.piece_count == DESIGN_TARGET_PIECES
    assert fp.total_bytes == DESIGN_TARGET_PIECES * BYTES_PER_PIECE


def test_an_import_that_fits_is_accepted() -> None:
    verdict = fits(free_bytes=10 * 1024**3, projected_pieces=1000)  # 10 GB free, 1000 pièces
    assert verdict.fits and verdict.headroom_bytes > 0
    assert "free" in verdict.reason


def test_an_import_that_cannot_fit_is_refused_with_a_margin() -> None:
    # 1000 pièces need ~40 MB + margin; only 1 MB free → refused (AD-32: not discovered at 70 %)
    verdict = fits(free_bytes=1 * 1024**2, projected_pieces=1000)
    assert not verdict.fits and verdict.headroom_bytes < 0
    assert "import refused" in verdict.reason


def test_the_safety_margin_is_applied() -> None:
    # free space exactly equal to the raw projection is NOT enough — the margin must clear too
    raw = footprint(1000).total_bytes
    assert not fits(free_bytes=raw, projected_pieces=1000).fits
    assert fits(free_bytes=int(raw * 1.5), projected_pieces=1000).fits


def test_zero_pieces_fits_trivially() -> None:
    assert fits(free_bytes=0, projected_pieces=0).fits
