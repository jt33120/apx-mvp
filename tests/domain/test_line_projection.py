"""The priced move — a projection from the ranking, never a bound (Story 4.9, FR-19/§0.2). Pure:
Δ pièces-to-read + the projected discarded-set prevalence; retain-everything says no bound applies
(never 0%); no projectable pièce says unavailable (never invented)."""

from __future__ import annotations

import pytest

from apx.core.domain.line_projection import (
    PROJECTION_METHOD,
    piece_relevance_projection,
    price_line_move,
    project_discarded_prevalence,
)
from apx.core.domain.triage_sets import Line

_REL = "confident-relevant"
_DIS = "confident-discard"
_UNC = "uncertain"


def test_directional_conversion_matches_the_confidence_calibration() -> None:
    assert piece_relevance_projection(_REL, 0.8) == pytest.approx(0.8)   # relevant → c
    assert piece_relevance_projection(_DIS, 0.9) == pytest.approx(0.1)   # discard → 1 - c
    assert piece_relevance_projection(_UNC, 0.4) == 0.5                  # uncertain → 0.5
    assert piece_relevance_projection(None, 0.5) is None                 # no band → None
    assert piece_relevance_projection(_REL, None) is None                # no confidence → None


def test_prevalence_is_the_mean_none_when_empty() -> None:
    assert project_discarded_prevalence([0.1, 0.3]) == pytest.approx(0.2)
    assert project_discarded_prevalence([]) is None


def _order():  # noqa: ANN202
    # rank 1..4: two relevant, then two confident-discard (deep discards → low P(relevant))
    return [("a", _REL, 0.9), ("b", _REL, 0.7), ("c", _DIS, 0.8), ("d", _DIS, 0.95)]


def test_moving_the_line_down_costs_more_reading_and_lowers_discarded_prevalence() -> None:
    move = price_line_move(_order(), Line("b"), Line("d"))
    assert move.pieces_to_read_delta == 2  # retained grows from 2 (a,b) to 4 (a..d)
    # current discarded = {c,d}: P = (0.2 + 0.05)/2 = 0.125 ; candidate discarded empty
    assert move.current_prevalence == pytest.approx(0.125)
    assert move.discarded_empty is True and move.candidate_prevalence is None  # AC-4


def test_moving_the_line_up_reads_less_and_the_discarded_prevalence_is_projected() -> None:
    move = price_line_move(_order(), Line("c"), Line("a"))
    assert move.pieces_to_read_delta == -2  # retained shrinks from 3 (a,b,c) to 1 (a)
    # candidate discarded = {b,c,d}: P = (0.7 + 0.2 + 0.05)/3
    assert move.candidate_prevalence == pytest.approx((0.7 + 0.2 + 0.05) / 3)
    assert move.prevalence_available is True


def test_retain_everything_says_no_bound_applies_never_zero() -> None:
    move = price_line_move(_order(), Line("b"), Line("d"))  # candidate retains all
    assert move.discarded_empty is True
    assert move.candidate_prevalence is None  # NOT 0.0 (AC-4)
    assert move.prevalence_available is False


def test_no_projectable_discarded_piece_is_unavailable_not_invented() -> None:
    # a discarded set whose only pièce carries no band/confidence → prevalence unavailable (AC-5)
    order = [("a", _REL, 0.9), ("x", None, None)]
    move = price_line_move(order, Line("a"), Line("a"))  # discarded = {x}, not projectable
    assert move.pieces_to_read_delta == 0
    assert move.candidate_prevalence is None and move.prevalence_available is False
    assert move.discarded_empty is False  # the set is non-empty, just not projectable


def test_a_line_naming_a_piece_not_in_the_order_fails_loudly() -> None:
    with pytest.raises(ValueError, match="not in the ranked order"):
        price_line_move(_order(), Line("a"), Line("zzz"))


def test_the_projection_method_is_named() -> None:
    assert PROJECTION_METHOD == "ranking-prevalence-projection-v1"
