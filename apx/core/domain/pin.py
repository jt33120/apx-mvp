"""**The pin** — moving a single *pièce* across **the line** (Story 4.11, FR-43 / FR-25).

A *pin* is a per-*pièce*, per-*matter* **override of the line**: this *pièce* is retained (or
discarded) regardless of its rank, and it is the only way to move **one** *pièce* across the line
without moving the line past everything above it. The pin is an **append-only** ledger keyed by the
*pièce* (not a *ranking version*), so a pin **survives re-ranking** and carries to new *ranking
versions* until explicitly removed (FR-43) — survival is a shape, not a copy step.

This module owns the ledger vocabulary and the derived **in-force** view; the :class:`Pin` /
:class:`PinSide` a pin resolves to (the operand ``derive_triage_sets`` applies **after** the line,
moving exactly one *pièce*) live in ``triage_sets.py`` (Story 4.7). A pin **requires a one-line
reason** and is recorded as an *override* (FR-25); this module refuses a blank one
(:func:`validate_pin_reason`). The *override* record itself (an audit act) and the ledger are the
store's (Story 4.11's owning use case).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from apx.core.domain.triage_sets import Pin, PinSide


class PinAction(StrEnum):
    """One entry in a *pièce*'s pin ledger — an append-only action (a persisted value must always
    decode). RETAIN / DISCARD pin the *pièce* to a side of **the line**; REMOVED lifts the pin (a
    removal is a NEW entry, never a delete — AD-7)."""

    RETAIN = "retain"
    DISCARD = "discard"
    REMOVED = "removed"


@dataclass(frozen=True)
class PinLogEntry:
    """One append-only entry in a *pièce*'s pin ledger: its per-*pièce* monotonic ``seq`` and the
    ``action`` (AD-49). The store carries the encrypted reason + actor; the in-force VIEW needs only
    these fields."""

    piece_id: str
    seq: int
    action: PinAction


class MissingPinReason(ValueError):
    """A pin was attempted without a one-line reason (FR-25): an *override* contradicts a machine
    assertion and cannot be committed without a reason. Nothing is written."""


def validate_pin_reason(reason: str) -> None:
    """Reject a blank/whitespace-only pin reason (FR-25 — a pin requires a one-line reason)."""
    if not reason or not reason.strip():
        raise MissingPinReason("a pin requires a one-line reason (FR-25)")


def current_pins(entries: Iterable[PinLogEntry]) -> tuple[Pin, ...]:
    """The **in-force** pins — a VIEW over the append-only ledger. For each *pièce* the latest
    (max-``seq``) entry decides: a RETAIN/DISCARD action is an active pin (mapped to
    :class:`Pin`), a REMOVED action lifts it (excluded). Deterministic order (by ``piece_id``) so a
    derivation over the same ledger is reproducible."""
    latest: dict[str, PinLogEntry] = {}
    for entry in entries:
        held = latest.get(entry.piece_id)
        if held is None or entry.seq > held.seq:
            latest[entry.piece_id] = entry
    pins: list[Pin] = []
    for piece_id in sorted(latest):
        action = latest[piece_id].action
        if action is PinAction.RETAIN:
            pins.append(Pin(piece_id=piece_id, side=PinSide.RETAIN))
        elif action is PinAction.DISCARD:
            pins.append(Pin(piece_id=piece_id, side=PinSide.DISCARD))
        # REMOVED → no pin in force for this pièce
    return tuple(pins)
