"""The priced move — a **projection from the ranking**, never a sampling bound (Story 4.9, FR-19).

When a lawyer considers moving **the line**, the tool prices the move: how many more *pièces* she
would have to read, and how the **estimated prevalence of relevant material in the resulting
discarded set** changes. That prevalence is a **projection** — a model estimate at a position where
**nothing has been sampled**. It is deliberately a DIFFERENT kind of statement from a *confidence
bound* (the hypergeometric statement a **completed** sampling run produces, Epic 5): the two are
never computed by the same code and never shown in the same visual register (FR-19 / §0.2). This
module **never** touches :func:`~apx.core.domain.confidence.prevalence_upper_bound` — a structural
check enforces it.

It never produces the *risk-of-a-miss* statement §0.2 recorded as false — the quantity a reader
could take as an assurance about the whole discarded pile rather than a share of it. That quantity
is not estimable here and is simply not computed. (The phrasings that assert it are banned across
every locale by ``no-banned-confidence-phrasing``, which reads source string literals; this
paragraph therefore names the error rather than spelling it.) Moving the line to retain everything
leaves the discarded set **empty** and **no bound applies** — the projection reports that, never a
prevalence of 0% (§0.2).

The per-*pièce* projected probability of relevance reuses the directional conversion the SM-17
confidence calibration already fixed (``p_relevant = c`` for a relevant band, ``1 - c`` for a
discard band), so the projection and the confidence calibration agree; the uncertain band projects
to 0.5
(the tool could not decide — the honest, non-optimistic default), and a *pièce* with no observable
projects to ``None`` (excluded — AD-19, nothing imputed).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from apx.core.domain.cascade import Band
from apx.core.domain.triage_sets import Line

# The named projection method — recorded in the audit and named once in the interface (FR-19). A
# version suffix so a revised method is a new name, reconstructible from the audit record.
PROJECTION_METHOD = "ranking-prevalence-projection-v1"


def piece_relevance_projection(band: str | None, confidence: float | None) -> float | None:
    """The projected probability that a *pièce* is relevant, from the ranking's observables (FR-19).
    ``confident-relevant`` → the confidence itself; ``confident-discard`` → ``1 - confidence`` (a
    deep discard is confidently IRRELEVANT); ``uncertain`` → ``0.5`` (undecided — never derived from
    a direction the band lacks); no band or no confidence → ``None`` (no observable, AD-19). This is
    a PROJECTION, not a measurement."""
    if band is None or confidence is None:
        return None
    if band == Band.CONFIDENT_RELEVANT.value:
        return confidence
    if band == Band.CONFIDENT_DISCARD.value:
        return 1.0 - confidence
    if band == Band.UNCERTAIN.value:
        return 0.5
    return None  # an unknown band string carries no projection


def project_discarded_prevalence(probs: Sequence[float]) -> float | None:
    """The estimated prevalence of relevant material over a discarded set — the arithmetic mean of
    its *pièces*' projected relevance probabilities. ``None`` when there is nothing to project over
    (an empty discarded set, or none of its *pièces* is projectable) — the tool then says the
    projection is unavailable rather than reporting 0% (FR-19 / §0.2)."""
    probs = list(probs)
    if not probs:
        return None
    return sum(probs) / len(probs)


@dataclass(frozen=True)
class PricedMove:
    """The price of moving **the line** to a candidate position (FR-19) — a PROJECTION, never a
    bound. ``pieces_to_read_delta`` is the change in the retained (to-read) count (positive = more
    to read). ``current_prevalence`` / ``candidate_prevalence`` are the projected discarded-set
    prevalences (each ``None`` when unavailable). ``discarded_empty`` is True when the candidate
    retains everything (no bound applies — never a 0% prevalence). ``prevalence_available`` is True
    only when a candidate prevalence could be projected over a non-empty discarded set."""

    pieces_to_read_delta: int
    current_prevalence: float | None
    candidate_prevalence: float | None
    discarded_empty: bool
    prevalence_available: bool


def _split(order_ids: list[str], line: Line | None) -> tuple[list[str], list[str]]:
    """Retained (up to and including the last retained *pièce*) and discarded (below), by rank.
    ``line=None`` means no cut — nothing retained, everything discarded. A line naming a *pièce* not
    in the order fails loudly (AD-19)."""
    if line is None:
        return [], list(order_ids)
    if line.last_retained_piece_id not in order_ids:
        raise ValueError(
            f"priced move: the line names a pièce not in the ranked order: "
            f"{line.last_retained_piece_id}")
    cut = order_ids.index(line.last_retained_piece_id)  # inclusive — the last retained pièce
    return order_ids[: cut + 1], order_ids[cut + 1 :]


def price_line_move(
    order: Sequence[tuple[str, str | None, float | None]],
    current_line: Line | None,
    candidate_line: Line | None,
) -> PricedMove:
    """Price moving the line from ``current_line`` to ``candidate_line`` over the ranked ``order``
    (FR-19). ``order`` is ``(piece_id, band, confidence)`` in rank order (ranked *pièces* only). The
    result carries Δ pièces-to-read and the projected discarded-set prevalence at each position — a
    PROJECTION (never a sampling bound). Retain-everything → ``discarded_empty`` + no prevalence;
    a discarded set with no projectable *pièce* → prevalence unavailable (counts only)."""
    order = list(order)
    ids = [pid for pid, _, _ in order]
    signals = {pid: (band, conf) for pid, band, conf in order}
    current_retained, current_discarded = _split(ids, current_line)
    candidate_retained, candidate_discarded = _split(ids, candidate_line)

    def prevalence(discarded_ids: list[str]) -> float | None:
        probs = [
            p for pid in discarded_ids
            if (p := piece_relevance_projection(*signals[pid])) is not None]
        return project_discarded_prevalence(probs)

    candidate_prevalence = prevalence(candidate_discarded)
    return PricedMove(
        pieces_to_read_delta=len(candidate_retained) - len(current_retained),
        current_prevalence=prevalence(current_discarded),
        candidate_prevalence=candidate_prevalence,
        discarded_empty=len(candidate_discarded) == 0,
        prevalence_available=len(candidate_discarded) > 0 and candidate_prevalence is not None)
