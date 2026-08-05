"""**The line** the tool draws and commits to (Story 4.8, FR-17).

Triage refuses to be an undifferentiated ranking: the tool **takes a position** — it recommends a
cut and commits to it, "in my view, everything above this". This module owns **choosing where the
cut falls** as a pure, recall-first policy; the :class:`~apx.core.domain.triage_sets.Line` value
object it returns (the cut modelled by the **identity of the last retained *pièce***, never a bare
integer — Story 4.7 / FR-17) is the operand :func:`~apx.core.domain.triage_sets.derive_triage_sets`
consumes.

**Recall over precision** (the product's triage rule): the line is placed after the **deepest**
(last, highest-rank) *pièce* whose stage-2 band is a configured *retain-band* — by default the
``confident-relevant`` and ``uncertain`` bands, so an uncertain *pièce* is **retained**, not
discarded. Everything below the last retained *pièce* is the discarded set; the cut is **ordinal**
(a position between two rows), so it never depends on a score.

When **no** *pièce* qualifies (every scored *pièce* is confidently discardable, or there is no
ranked *pièce*), the tool commits to **no line** rather than fabricate a retained set — an honest
non-commitment (AD-19: nothing imputed). The *basis* of the placement (the *case theory* where one
exists, else the named intrinsic signals — FR-17) is **inherited from the ranking version** the line
cuts; it is composed by the owning store use case, not invented here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from apx.core.domain.triage_sets import Line


@dataclass(frozen=True)
class LinePlacementView:
    """The CURRENT line over a *ranking version* (FR-17) — a VIEW the store derives (the max-``seq``
    placement), returned by the recorder port so the core seam never names the adapter (AD-4). Names
    its ``version_id``/``version_no`` (AD-23 — no unqualified reference); the line is identified by
    ``last_retained_piece_id`` (never a bare integer); ``basis`` is its stated basis inherited from
    the ranking version (``case-theory:<version>`` or ``intrinsic:<named signals>``); ``seq``/``at``
    make the placement attributable and reversible. The actor (PII) is not carried on this view."""

    version_id: str
    version_no: int
    last_retained_piece_id: str
    basis: str
    seq: int
    at: datetime


@dataclass(frozen=True)
class RankedBand:
    """One *pièce*'s position in the ranked order for the purpose of placing the line: its identity
    and its stage-2 :class:`~apx.core.domain.cascade.Band` value (``None`` for a REJECTED *pièce*
    that carries a rejection class instead of a band). The caller supplies these in rank order (rank
    1..N), ranked *pièces* only — the unscored tail is excluded (it is its own set, never below the
    line)."""

    piece_id: str
    band: str | None


def recommend_line(
    order: Sequence[RankedBand], *, retain_bands: frozenset[str]
) -> Line | None:
    """Recommend **the line** over a ranked order (FR-17), recall-first. ``order`` is the ranked
    *pièces* in rank order (rank 1..N); ``retain_bands`` the stage-2 band values the tool retains.

    The line is placed after the **deepest** *pièce* whose band is a retain-band — that *pièce* is
    the *last retained pièce* the line is named by. Returns ``Line(last_retained_piece_id)``;
    returns ``None`` — an honest non-commitment — when no *pièce* qualifies or ``order`` is empty
    (the tool never fabricates a retained set; AD-19)."""
    last_retained: str | None = None
    for row in order:
        if row.band is not None and row.band in retain_bands:
            last_retained = row.piece_id  # the deepest retain-band pièce so far, in rank order
    if last_retained is None:
        return None
    return Line(last_retained_piece_id=last_retained)
