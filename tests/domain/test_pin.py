"""The pin ledger vocabulary + the in-force view (Story 4.11, FR-43).
Pure: current pins are the latest action per pièce (REMOVED lifts it). The mandatory reason moved
to ``tests/domain/test_override.py`` with the rule itself (Story 5.6 — one validator, FR-25)."""

from __future__ import annotations

from apx.core.domain.pin import (
    PinAction,
    PinLogEntry,
    current_pins,
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
