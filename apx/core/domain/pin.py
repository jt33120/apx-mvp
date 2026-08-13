"""**The pin** — moving a single *pièce* across **the line** (Story 4.11, FR-43 / FR-25).

A *pin* is a per-*pièce*, per-*matter* **override of the line**: this *pièce* is retained (or
discarded) regardless of its rank, and it is the only way to move **one** *pièce* across the line
without moving the line past everything above it. The pin is an **append-only** ledger keyed by the
*pièce* (not a *ranking version*), so a pin **survives re-ranking** and carries to new *ranking
versions* until explicitly removed (FR-43) — survival is a shape, not a copy step.

This module owns the ledger vocabulary and the derived **in-force** view; the :class:`Pin` /
:class:`PinSide` a pin resolves to (the operand ``derive_triage_sets`` applies **after** the line,
moving exactly one *pièce*) live in ``triage_sets.py`` (Story 4.7). A pin **requires a one-line
reason** and is recorded as an *override* (FR-25). The rule that a reason is mandatory used to be
implemented here; since Story 5.6 there is exactly one implementation of it, in ``override.py``
(:func:`~apx.core.domain.override.validate_override_reason`), because a rule stated in three places
is a rule that will hold in two. The *override* record itself (an audit act) and the ledger are the
store's (Story 4.11's owning use case).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
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


@dataclass(frozen=True)
class PinLogRecord:
    """One entry of a *pièce*'s pin ledger **as an export carries it** (FR-26, Story 5.7): the
    action, who took it, when, and — for a pin, which is an *override* (FR-25) — the mandatory
    reason verbatim.

    :class:`PinLogEntry` is the derivation's input and carries only what ``current_pins`` needs; it
    has no actor and no reason by design (the in-force view is computed on every triage read, and a
    view that carried PII would spread it across every one of them). FR-26 asks for **all** pins,
    with their reasons — the whole ledger, not the view over it — so the export gets its own shape.

    ``reason`` is the empty string for a ``REMOVED`` action: lifting a pin puts the *pièce* back
    where the tool had it and costs no sentence (Story 4.11's reading, kept)."""

    piece_id: str
    seq: int
    action: PinAction
    set_by: str
    at: datetime
    reason: str = ""


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
