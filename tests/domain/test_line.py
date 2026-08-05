"""The recall-first line-placement policy (Story 4.8, FR-17): a pure function over the ranked order
that names the last retained *pièce* — never a bare integer, never a fabricated cut."""

from __future__ import annotations

from apx.core.domain.cascade import Band
from apx.core.domain.line import RankedBand, recommend_line

_RETAIN = frozenset({Band.CONFIDENT_RELEVANT.value, Band.UNCERTAIN.value})


def _order(*bands: str | None) -> list[RankedBand]:
    return [RankedBand(f"p{i}", b) for i, b in enumerate(bands, start=1)]


def test_the_line_falls_after_the_deepest_retain_band_piece() -> None:
    # ranks 1..5: relevant, uncertain, uncertain, discard, discard → last retained is p3
    order = _order("confident-relevant", "uncertain", "uncertain", "confident-discard",
                   "confident-discard")
    line = recommend_line(order, retain_bands=_RETAIN)
    assert line is not None and line.last_retained_piece_id == "p3"


def test_recall_first_keeps_the_uncertain_piece_retained() -> None:
    # an uncertain pièce deeper than the last confident-relevant one still moves the line down
    order = _order("confident-relevant", "confident-discard", "uncertain")
    line = recommend_line(order, retain_bands=_RETAIN)
    assert line is not None and line.last_retained_piece_id == "p3"  # the uncertain p3 is retained


def test_all_retain_band_retains_the_whole_order() -> None:
    order = _order("confident-relevant", "uncertain", "confident-relevant")
    line = recommend_line(order, retain_bands=_RETAIN)
    assert line is not None and line.last_retained_piece_id == "p3"  # last ranked pièce


def test_no_qualifying_piece_is_an_honest_non_commitment() -> None:
    # everything confidently discardable → the tool commits to NO line (never fabricates)
    order = _order("confident-discard", "confident-discard")
    assert recommend_line(order, retain_bands=_RETAIN) is None


def test_an_empty_order_yields_no_line() -> None:
    assert recommend_line([], retain_bands=_RETAIN) is None


def test_a_rejected_piece_with_no_band_never_sets_the_line() -> None:
    # a REJECTED pièce carries a rejection class, not a band (None) — it cannot be the last retained
    order = _order("confident-relevant", None, None)
    line = recommend_line(order, retain_bands=_RETAIN)
    assert line is not None and line.last_retained_piece_id == "p1"


def test_the_retain_band_set_is_honoured() -> None:
    # a narrower policy (confident-relevant only) discards the uncertain pièce
    order = _order("confident-relevant", "uncertain")
    line = recommend_line(order, retain_bands=frozenset({Band.CONFIDENT_RELEVANT.value}))
    assert line is not None and line.last_retained_piece_id == "p1"
