"""The recall bound: a finite-population (hypergeometric) upper confidence bound.

These pin the maths that an earlier binomial "rule of three" got wrong: exactness at
a full census, the right small-sample value by hand, tightening with more review, and
convergence to the binomial only as the population grows large.
"""

from __future__ import annotations

import pytest

from apx.core.domain.confidence import prevalence_upper_bound


def test_zero_found_small_case_by_hand() -> None:
    # N=10, n=5, k=0, 95%: comb(10-D,5)/comb(10,5) >= .05 at D=3 (0.083), fails at D=4 (0.024).
    b = prevalence_upper_bound(population=10, sample_size=5, relevant_in_sample=0)
    assert b.count_upper == 3
    assert b.prevalence_upper == 0.3


def test_full_census_is_exact() -> None:
    # Reviewed the whole pile: the bound is the count actually found, no slack.
    b = prevalence_upper_bound(population=20, sample_size=20, relevant_in_sample=3)
    assert b.count_upper == 3 and b.prevalence_upper == pytest.approx(0.15)
    zero = prevalence_upper_bound(population=20, sample_size=20, relevant_in_sample=0)
    assert zero.count_upper == 0 and zero.prevalence_upper == 0.0


def test_reviewing_nothing_is_total_uncertainty() -> None:
    b = prevalence_upper_bound(population=500, sample_size=0, relevant_in_sample=0)
    assert b.prevalence_upper == 1.0 and b.count_upper == 500  # honest, not a fake zero


def test_empty_pile_bounds_to_zero() -> None:
    b = prevalence_upper_bound(population=0, sample_size=0, relevant_in_sample=0)
    assert b.count_upper == 0 and b.prevalence_upper == 0.0  # nothing discarded, nothing to miss


def test_more_review_tightens_the_bound() -> None:
    bounds = [
        prevalence_upper_bound(2000, sample_size=n, relevant_in_sample=0).prevalence_upper
        for n in (50, 100, 200, 400, 800)
    ]
    assert bounds == sorted(bounds, reverse=True)      # non-increasing
    assert bounds[0] > bounds[-1]                       # and it genuinely tightens


def test_finite_bound_is_tighter_than_the_binomial_rule() -> None:
    # For 0 found, the binomial 95% bound is 1 - 0.05**(1/n); the finite-population
    # correction can only tighten it.
    n = 100
    binomial = 1 - 0.05 ** (1 / n)
    b = prevalence_upper_bound(population=1000, sample_size=n, relevant_in_sample=0)
    assert b.prevalence_upper < binomial


def test_large_population_approaches_the_binomial() -> None:
    # As N grows, without-replacement -> with-replacement: the bound meets the binomial.
    n = 59
    binomial = 1 - 0.05 ** (1 / n)
    b = prevalence_upper_bound(population=10_000_000, sample_size=n, relevant_in_sample=0)
    assert abs(b.prevalence_upper - binomial) < 1e-3


def test_higher_confidence_widens_the_bound() -> None:
    at95 = prevalence_upper_bound(1000, 100, 0, confidence=0.95).count_upper
    at99 = prevalence_upper_bound(1000, 100, 0, confidence=0.99).count_upper
    assert at99 >= at95  # more confidence demanded -> a looser (larger) upper bound


def test_structural_bounds_hold_when_defects_found() -> None:
    b = prevalence_upper_bound(population=100, sample_size=20, relevant_in_sample=1)
    assert 1 <= b.count_upper <= 100
    assert b.relevant_in_sample / b.population <= b.prevalence_upper <= 1.0


def test_invalid_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        prevalence_upper_bound(population=10, sample_size=20, relevant_in_sample=0)  # sample > pop
    with pytest.raises(ValueError):
        prevalence_upper_bound(population=10, sample_size=5, relevant_in_sample=6)  # found > sample
    with pytest.raises(ValueError):
        prevalence_upper_bound(population=10, sample_size=5, relevant_in_sample=0, confidence=1.0)
