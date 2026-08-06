"""The pin ledger vocabulary + the in-force view + the mandatory reason (Story 4.11, FR-43/FR-25).
Pure: current pins are the latest action per pièce (REMOVED lifts it); a blank reason is refused."""

from __future__ import annotations

import pytest

from apx.core.domain.pin import (
    MissingPinReason,
    PinAction,
    PinLogEntry,
    current_pins,
    validate_pin_reason,
)
from apx.core.domain.triage_sets import PinSide


def test_the_latest_action_per_piece_decides_the_in_force_pin() -> None:
    entries = [
        PinLogEntry("a", 1, PinAction.RETAIN),
        PinLogEntry("a", 2, PinAction.DISCARD),   # a later pin overrides the earlier one
        PinLogEntry("b", 1, PinAction.RETAIN),
    ]
    pins = current_pins(entries)
    sides = {p.piece_id: p.side for p in pins}
    assert sides == {"a": PinSide.DISCARD, "b": PinSide.RETAIN}


def test_a_removed_pin_is_not_in_force() -> None:
    entries = [PinLogEntry("a", 1, PinAction.RETAIN), PinLogEntry("a", 2, PinAction.REMOVED)]
    assert current_pins(entries) == ()


def test_a_re_pin_after_removal_is_in_force_again() -> None:
    entries = [
        PinLogEntry("a", 1, PinAction.RETAIN),
        PinLogEntry("a", 2, PinAction.REMOVED),
        PinLogEntry("a", 3, PinAction.RETAIN),  # pinned again — the latest wins
    ]
    (pin,) = current_pins(entries)
    assert pin.piece_id == "a" and pin.side is PinSide.RETAIN


def test_the_in_force_pins_are_ordered_by_piece_id() -> None:
    entries = [PinLogEntry("c", 1, PinAction.RETAIN), PinLogEntry("a", 1, PinAction.DISCARD)]
    assert [p.piece_id for p in current_pins(entries)] == ["a", "c"]


def test_no_entries_means_no_pins() -> None:
    assert current_pins([]) == ()


def test_a_blank_reason_is_refused() -> None:
    for bad in ("", "   ", "\t\n"):
        with pytest.raises(MissingPinReason):
            validate_pin_reason(bad)


def test_a_real_reason_passes() -> None:
    validate_pin_reason("aveu implicite au §4 — décisif malgré le rang")  # no raise
