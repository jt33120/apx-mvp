"""The recall guarantee behind triage: a finite-population upper confidence bound on
what a discard decision may have missed.

Triage discards a pile. To stand behind that — recall over precision, no silent loss
— we do NOT trust the judge to grade itself (a model's own confidence is not a recall
guarantee). We sample the discarded pile, review the sample (a human, or the gold
standard), and from what the sample showed we bound the prevalence of truly-relevant
pieces in the WHOLE pile.

The sample is drawn WITHOUT replacement from a finite pile, so the count of missed-
relevant in the sample is hypergeometric, not binomial. Two consequences matter:
having inspected a real fraction of the pile, the bound is TIGHTER than the binomial
"rule of three" (3/n); and at a full census (sample == pile) it is EXACT — the bound
equals the count actually found. An earlier version of this used the binomial rule of
three and was wrong here; this is the finite-population statistic.

Read the result as: "with confidence c, at most `count_upper` of the `population`
discarded pieces were actually relevant (a prevalence of `prevalence_upper`)."
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from math import comb

# The statistical method, by name (Story 5.2, FR-23: *"the statistical method producing X is
# stated… changing it produces a NEW confidence bound rather than silently restating the old
# one"*). Recorded on every bound this build writes, so a bound computed by a different method
# reads as one instead of inheriting the authority of this one. Exactly one method exists and
# selecting among methods is deliberately NOT offered as a tenant configuration key — see the
# stated deviation in the Story 5.2 file: a knob choosing the estimator is a knob choosing how
# favourable the number is.
ESTIMATOR_METHOD = "hypergeometric-upper-bound.v1"


@dataclass(frozen=True)
class PrevalenceBound:
    population: int          # the discarded pile
    sample_size: int         # how many of it were reviewed
    relevant_in_sample: int  # how many reviewed were actually relevant (wrongly discarded)
    confidence: float
    count_upper: int         # at most this many relevant in the whole pile, at `confidence`
    prevalence_upper: float  # count_upper / population (0.0 when the pile is empty)


def _cdf_leq(population: int, defects: int, sample_size: int, k: int, denom: int) -> float:
    """P(X <= k) for X ~ Hypergeometric(N=population, D=defects, n=sample_size).

    ``denom`` is comb(population, sample_size), passed in because it does not depend
    on ``defects`` and the caller reuses it across the search. Exact big-integer
    arithmetic; the final ratio (<= 1) is a correctly-rounded float."""
    numer = 0
    for x in range(min(k, sample_size, defects) + 1):
        numer += comb(defects, x) * comb(population - defects, sample_size - x)
    return numer / denom


def prevalence_upper_bound(
    population: int,
    sample_size: int,
    relevant_in_sample: int,
    *,
    confidence: float = 0.95,
) -> PrevalenceBound:
    """The upper confidence bound on the prevalence of relevant pieces in a discarded
    pile, from a without-replacement review of a sample of it.

    ``count_upper`` is the largest defect count D for which observing this few (or
    fewer) relevant in the sample is not yet too unlikely — i.e. the largest D with
    P(X <= relevant_in_sample | D) >= 1 - confidence. P(X <= k | D) is non-increasing
    in D, so the search is a clean binary search."""
    if not 0 < confidence < 1:
        raise ValueError(f"confidence must be in (0, 1): {confidence}")
    if population < 0 or sample_size < 0 or relevant_in_sample < 0:
        raise ValueError("counts must be non-negative")
    if sample_size > population:
        raise ValueError(f"sample_size {sample_size} exceeds population {population}")
    if relevant_in_sample > sample_size:
        raise ValueError(
            f"relevant_in_sample {relevant_in_sample} exceeds sample_size {sample_size}"
        )

    if population == 0:
        return PrevalenceBound(0, 0, 0, confidence, 0, 0.0)  # nothing discarded, nothing to miss
    if sample_size == 0:
        # Reviewed nothing: the whole pile could be relevant. Honest, not a fake zero.
        return PrevalenceBound(population, 0, 0, confidence, population, 1.0)

    alpha = 1.0 - confidence
    denom = comb(population, sample_size)
    # Largest D in [relevant_in_sample, population] with P(X <= relevant_in_sample | D) >= alpha.
    lo, hi = relevant_in_sample, population
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _cdf_leq(population, mid, sample_size, relevant_in_sample, denom) >= alpha:
            lo = mid
        else:
            hi = mid - 1
    return PrevalenceBound(
        population=population,
        sample_size=sample_size,
        relevant_in_sample=relevant_in_sample,
        confidence=confidence,
        count_upper=lo,
        prevalence_upper=lo / population,
    )


def pieces_upper_bound(
    *, count_upper_families: int, family_sizes: Sequence[int] | None
) -> int | None:
    """How many *pièces* at most, given that at most ``count_upper_families`` FAMILIES are relevant.

    OQ-4's first hard input, second half (Story 5.2). The bound is computed over the unit that was
    drawn — near-duplicate families — but the lawyer counts her discarded pile in *pièces*, and
    FR-23's sentence contains *"about Y pièces"*. The conversion must not be
    ``prevalence_upper × population_pieces``: that product assumes the relevant families are of
    AVERAGE size, and where the few large thread-families are the relevant ones it understates —
    **in the flattering direction**, which is the one direction a number said to a judge may never
    be biased in.

    The honest conversion is the worst case the same confidence already covers: if at most ``D``
    families are relevant, then at most the ``D`` **largest** families are, so at most the sum of
    the ``D`` largest frozen family sizes is relevant in *pièces*. It is loose by construction and
    says so; a loose true statement is admissible and a tight false one is not.

    ``family_sizes`` is the run's FROZEN size list — every family in the population as it was at
    draw time, not only the drawn ones and not the set as it is now. ``None`` when the run predates
    that freeze (Story 5.1 runs): the answer is then *not computable*, and comes back as ``None``
    rather than estimated, because an absent input is never imputed (AD-19).
    """
    if family_sizes is None:
        return None
    if count_upper_families < 0:
        raise ValueError(f"count_upper_families must be non-negative: {count_upper_families}")
    if any(s < 1 for s in family_sizes):
        raise ValueError("a family holds at least one pièce")
    return sum(sorted(family_sizes, reverse=True)[:count_upper_families])


@dataclass(frozen=True)
class RecordedBound:
    """A *confidence bound* that was **recorded** and can be read back later — the derived artefact
    FR-58 governs (Story 4.13).

    :class:`PrevalenceBound` is the number; this is the number as an *artefact with a lifetime*: it
    names the identity its freshness stamp is keyed by (``artefact_id``) and when it was reviewed.
    A bound displayed later is the one thing in this product that can be false while looking fresh
    — 300 *pièces* arrive and the sentence still speaks about the old population — so it is stamped
    like the ranking and the line, and a stale one cannot be exported as current.

    ``reviewed_at`` is a **record** of when the review happened. It is never an input to the
    freshness decision: staleness is not resolved by the passage of time (FR-58), and no observable
    on :class:`~apx.core.domain.freshness.FreshnessStamp` is a clock.

    ``unit_fr`` names **what was counted** (Story 5.1). A *sampling run* draws near-duplicate
    FAMILIES, not *pièces* — forty copies of one email are one draw (FR-38) — so
    ``bound.population`` is a family count. Rendering it as *"des 5 pièces écartées"* would make
    the one sentence a firm says to a judge false about its own denominator, which is precisely the
    failure this epic exists to prevent. A legacy ``recall_review`` counted *pièces* and keeps the
    default. ``piece_count`` is how many *pièces* those units hold, or ``None`` when the two are the
    same thing; it is stated beside the bound and **never substituted into it** — a bound quoted
    over a denominator nobody sampled is the same failure with the numbers swapped.

    ``method`` is the statistical method that produced the number, by name (Story 5.2, FR-23).
    ``None`` means *no method was recorded* — true of every legacy ``recall_review`` row, which
    predates the requirement — and it is left as ``None`` rather than back-filled with today's
    method, because claiming a provenance a row does not have is the same failure as claiming a
    freshness it does not have (AD-19).

    ``count_upper_pieces`` is the worst-case *pièce* figure derived from the frozen family sizes
    (:func:`pieces_upper_bound`), or ``None`` when it is not computable. It is never substituted for
    ``bound.count_upper`` and never rendered as the bound's own denominator.

    ``relevant_pieces`` is the **exact** *pièce* count of the relevant units, and is meaningful only
    at a census, where every unit was read. The two *pièce* fields are deliberately separate: a
    worst case and an exact count are different kinds of statement and must not share a slot, since
    a slot shared is a slot a renderer can mistake (Story 5.2, OQ-4 input 2).
    """

    artefact_id: str
    bound: PrevalenceBound
    reviewed_at: datetime
    unit_fr: str = "pièces écartées"
    piece_count: int | None = None
    method: str | None = None
    count_upper_pieces: int | None = None
    relevant_pieces: int | None = None
    # How many runs over this same frozen population came first, counting the abandoned ones. FR-22
    # requires a bound resting on a later draw to say so, and the sentence travels alone.
    run_ordinal: int = 1
