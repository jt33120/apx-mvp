"""The *retained set* and the *discarded set* — **views** derived from one ranked order, never
stored memberships (Story 4.7, FR-16 / AD-39 / AD-7).

Triage is a ranking, not a filing system. The two sets are **not** persisted — they are
:func:`derive_triage_sets`, recomputed at read time from **one ranked order + the line cut + pins,
in that sequence** (AD-39). A *pièce* moves between them only because the order changed (a new
*ranking version*), **the line** moved (Story 4.8) or a *pin* was added/removed (Story 4.11) — each
an audited transition owned by its use case (AD-37). Because nothing is stored, no membership row
can drift from the order and the cut that define it: **reversibility is a shape, not a promise**.

The line and the pins are **operands** here, not machinery: this module takes a :class:`Line` (the
cut, modelled by the identity of the last retained *pièce* — Story 4.8/FR-17 owns choosing/storing
it) and a set of :class:`Pin` overrides (Story 4.11/FR-43 owns creating them). The ``unscored`` tail
stays its **own** set — never folded into the discarded set (AD-19/AD-36: absence is explicit, a
*pièce* the cascade could not score is not silently discarded).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum


class PinSide(StrEnum):
    """Which side a *pin* forces a *pièce* onto, overriding **the line** (Story 4.11/FR-43).
    Append-only string value (a persisted pin side must always decode)."""

    RETAIN = "retain"    # pull the *pièce* into the retained set
    DISCARD = "discard"  # push the *pièce* into the discarded set


@dataclass(frozen=True)
class Pin:
    """A per-*pièce* override of **the line** — moves exactly one *pièce* across it (FR-43). An
    INPUT to the derivation here; its creation, its mandatory one-line reason and its *override*
    record are Story 4.11."""

    piece_id: str
    side: PinSide


@dataclass(frozen=True)
class Line:
    """**The line** as an ordinal cut, modelled by the **identity of the last retained *pièce***
    (FR-17-ready — not a bare integer position, so an import that adds *pièces* cannot silently move
    what the line designates). Everything at or above this *pièce* in rank order is retained; below
    it, discarded. Choosing and storing the line is Story 4.8/FR-17; here it is an INPUT."""

    last_retained_piece_id: str


@dataclass(frozen=True)
class TriageSets:
    """The **derived** retained/discarded/unscored sets over one *ranking version* (a VIEW, never a
    stored membership — AD-39). Names the ``version_id`` it was computed against (FR-16's
    ambiguous-referent rule): an unqualified reference is structurally impossible. ``pins_in_force``
    is the number of pins actively overriding the line (FR-43 — stated wherever the sets are
    counted). ``line_placed`` is False when no line was supplied yet (the ranked *pièces* are
    pending the line, not a third category)."""

    version_id: str
    retained: tuple[str, ...]
    discarded: tuple[str, ...]
    unscored: tuple[str, ...]
    pins_in_force: int
    line_placed: bool

    @property
    def retained_count(self) -> int:
        return len(self.retained)

    @property
    def discarded_count(self) -> int:
        return len(self.discarded)

    @property
    def unscored_count(self) -> int:
        return len(self.unscored)


def derive_triage_sets(
    *, ranked: Sequence[str], unscored: Sequence[str], line: Line | None,
    pins: Iterable[Pin], version_id: str,
) -> TriageSets:
    """Derive the retained/discarded/unscored views from the ranked order (FR-16/AD-39). ``ranked``
    is the *pièce* ids in rank order (rank 1..N); ``unscored`` the unscored tail. Sequence: the
    fixed order -> split at the line's last-retained *pièce* -> apply pins. The order is **never
    reordered**; the ``unscored`` tail is its own set. A pin (or the line) naming a *pièce* not in
    the ranked set fails loudly. ``line=None`` means no split yet (retained/discarded empty,
    ``line_placed=False``).

    Invariants (with a line placed): ``retained`` and ``discarded`` partition the ranked set; a pin
    that disagrees with the line moves exactly one *pièce* and is counted in ``pins_in_force``."""
    ranked = list(ranked)
    unscored = list(unscored)
    # the ranked order and the unscored tail are the two DISJOINT parts of one population — a pièce
    # in both (or twice) would land in a triage set AND the tail. The store partitions RankedEntry
    # rows by rank-null so it cannot happen, but the pure function fails loudly rather than emit a
    # silently-wrong view (AD-19 — nothing imputed).
    population = ranked + unscored
    ranked_set = set(ranked)
    if len(set(population)) != len(population):
        raise ValueError(
            "triage sets: a pièce appears more than once across the ranked order and the "
            "unscored tail")

    # dedup pins by pièce (a later pin overrides an earlier one); validate membership loudly
    pin_side: dict[str, PinSide] = {}
    for pin in pins:
        if pin.piece_id not in ranked_set:
            raise ValueError(
                f"triage sets: pin names a pièce not in the ranked order: {pin.piece_id}")
        pin_side[pin.piece_id] = pin.side

    if line is None:
        return TriageSets(
            version_id=version_id, retained=(), discarded=(), unscored=tuple(unscored),
            pins_in_force=0, line_placed=False)

    if line.last_retained_piece_id not in ranked_set:
        raise ValueError(
            f"triage sets: the line names a pièce not in the ranked order: "
            f"{line.last_retained_piece_id}")

    cut = ranked.index(line.last_retained_piece_id)  # inclusive — the last retained pièce
    retained = set(ranked[: cut + 1])
    discarded = set(ranked[cut + 1 :])

    in_force = 0
    for piece_id, side in pin_side.items():
        line_side = PinSide.RETAIN if piece_id in retained else PinSide.DISCARD
        if side == line_side:
            continue  # a pin agreeing with the line changes nothing — not "in force"
        in_force += 1
        if side is PinSide.RETAIN:
            discarded.discard(piece_id)
            retained.add(piece_id)
        else:
            retained.discard(piece_id)
            discarded.add(piece_id)

    # emit in the fixed rank order (the order is never reordered by the line or a pin)
    return TriageSets(
        version_id=version_id,
        retained=tuple(p for p in ranked if p in retained),
        discarded=tuple(p for p in ranked if p in discarded),
        unscored=tuple(unscored),
        pins_in_force=in_force,
        line_placed=True)
