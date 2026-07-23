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

from dataclasses import dataclass
from math import comb


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
