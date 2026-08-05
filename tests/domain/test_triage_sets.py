"""The retained/discarded/unscored VIEW derivation (Story 4.7, FR-16/FR-43/AD-39): pure functions
over one ranked order + the line cut + pins, in that sequence — never a stored membership."""

from __future__ import annotations

import pytest

from apx.core.domain.triage_sets import Line, Pin, PinSide, derive_triage_sets

_RANKED = ["a", "b", "c", "d"]  # rank 1..4


def _sets(line=None, pins=(), unscored=()):  # noqa: ANN001,ANN202
    return derive_triage_sets(
        ranked=_RANKED, unscored=unscored, line=line, pins=pins, version_id="v1")


def test_the_line_splits_at_the_last_retained_piece_inclusive() -> None:
    s = _sets(line=Line("b"))
    assert s.retained == ("a", "b") and s.discarded == ("c", "d")
    assert s.line_placed is True and s.version_id == "v1"
    # retained ∪ discarded partitions the ranked set; the order is preserved
    assert set(s.retained) | set(s.discarded) == set(_RANKED)
    assert set(s.retained) & set(s.discarded) == set()


def test_no_line_means_no_split_not_a_third_set() -> None:
    s = _sets(line=None)
    assert s.retained == () and s.discarded == () and s.line_placed is False
    assert s.pins_in_force == 0


def test_the_unscored_tail_is_its_own_set_never_folded_into_discarded() -> None:
    s = _sets(line=Line("b"), unscored=("u1", "u2"))
    assert s.unscored == ("u1", "u2")
    assert "u1" not in s.discarded and "u1" not in s.retained  # AD-19/AD-36 — its own set


def test_a_retain_pin_pulls_exactly_one_piece_across_order_unchanged() -> None:
    s = _sets(line=Line("b"), pins=(Pin("d", PinSide.RETAIN),))
    assert s.retained == ("a", "b", "d") and s.discarded == ("c",)  # emitted in rank order
    assert s.pins_in_force == 1


def test_a_discard_pin_pushes_exactly_one_piece_across() -> None:
    s = _sets(line=Line("b"), pins=(Pin("a", PinSide.DISCARD),))
    assert s.retained == ("b",) and s.discarded == ("a", "c", "d")
    assert s.pins_in_force == 1


def test_a_pin_agreeing_with_the_line_is_not_in_force() -> None:
    s = _sets(line=Line("b"), pins=(Pin("a", PinSide.RETAIN),))  # 'a' is already retained
    assert s.retained == ("a", "b") and s.discarded == ("c", "d")
    assert s.pins_in_force == 0


def test_the_line_never_reorders_the_ranked_order() -> None:
    # whatever the cut, retained then discarded are each in the original rank order
    s = _sets(line=Line("c"), pins=(Pin("a", PinSide.DISCARD), Pin("d", PinSide.RETAIN)))
    assert s.retained == ("b", "c", "d") and s.discarded == ("a",)
    assert s.pins_in_force == 2


def test_a_line_naming_a_piece_not_in_the_order_fails_loudly() -> None:
    with pytest.raises(ValueError, match="line names a pièce not in"):
        _sets(line=Line("zzz"))


def test_a_pin_naming_a_piece_not_in_the_order_fails_loudly() -> None:
    with pytest.raises(ValueError, match="pin names a pièce not in"):
        _sets(line=Line("b"), pins=(Pin("zzz", PinSide.RETAIN),))


def test_a_piece_in_both_the_order_and_the_unscored_tail_fails_loudly() -> None:
    # the ranked order and the unscored tail are disjoint; a pièce in both would land in a triage
    # set AND the tail — the pure function refuses it loudly (AD-19), never a silently-wrong view.
    with pytest.raises(ValueError, match="more than once"):
        _sets(line=Line("b"), unscored=("a",))  # 'a' is already in the ranked order
