"""The estimator's five answers, as behaviour (Story 5.2, OQ-4 / FR-22 / FR-23 / FR-38).

Each block tests one of the five hard inputs OQ-4 names. The statistic itself is tested in
``test_confidence.py`` and is deliberately unchanged by this story: what is tested here is the
design around it — the unit, the crossover, the multiplicity, the freeze, and what the number is
NOT allowed to become on the way to a sentence.
"""

from __future__ import annotations

import pytest

from apx.core.domain.confidence import (
    ESTIMATOR_METHOD,
    pieces_upper_bound,
    prevalence_upper_bound,
)
from apx.core.domain.sampling import (
    KIND_BOUND,
    KIND_CENSUS,
    KIND_NO_POPULATION,
    bound_for_run,
    census_statement_fr,
    estimate_for_run,
)

_FAMILIES_FR = "familles de quasi-doublons écartées"


def _estimate(**over: object):
    """An :class:`Estimate` as the read path builds one.

    ``estimate_for_run`` READS the recorded numbers off the run's row rather than recomputing them
    (a completed bound is an artefact with a lifetime, FR-58), so this helper writes them the way
    ``complete_sampling_run`` would have — unless a test overrides them to say what a run with no
    recorded bound, or one closed under an older method, does."""
    base: dict[str, object] = dict(
        population_families=120, population_pieces=1400, sample_families=30,
        relevant_families=0, relevant_pieces_drawn=0, confidence=0.95,
        family_sizes=None, run_ordinal=1)
    base.update(over)
    if "recorded_count_upper" not in base:
        population = int(base["population_families"])  # type: ignore[call-overload]
        drawn = int(base["sample_families"])           # type: ignore[call-overload]
        if population > 0 and drawn < population:
            recorded = bound_for_run(
                population=population, sample_size=drawn,
                relevant_found=int(base["relevant_families"]),  # type: ignore[call-overload]
                confidence=float(base["confidence"]))           # type: ignore[arg-type]
            base["recorded_count_upper"] = recorded.count_upper
            base["recorded_prevalence_upper"] = recorded.prevalence_upper
        else:
            # a census and an empty population record no bound: there is nothing to bound
            base["recorded_count_upper"] = None
            base["recorded_prevalence_upper"] = None
    base.setdefault("recorded_prevalence_upper", None)
    base.setdefault("recorded_method", ESTIMATOR_METHOD)
    return estimate_for_run(**base)  # type: ignore[arg-type]


# ── input 1: the unit is the family, and the pièce figure is a WORST CASE ────────────────────────

def test_the_piece_worst_case_is_the_largest_families_not_an_average_rescale() -> None:
    """The whole point. 40 families holding 400 pièces; at most 3 are relevant. The tempting
    arithmetic is 3/40 × 400 = 30 pièces. The truth is that the three largest families hold 120,
    and the flattering answer is the wrong one."""
    sizes = [60, 40, 20] + [1] * 37
    assert sum(sizes) == 157
    assert pieces_upper_bound(count_upper_families=3, family_sizes=sizes) == 120
    rescale = round(3 / 40 * sum(sizes))
    assert rescale < 120, "the rescale understates — which is why it is forbidden"


def test_the_worst_case_ignores_the_order_the_sizes_arrive_in() -> None:
    ascending = [1, 1, 5, 90]
    descending = [90, 5, 1, 1]
    assert pieces_upper_bound(count_upper_families=2, family_sizes=ascending) == 95
    assert pieces_upper_bound(count_upper_families=2, family_sizes=descending) == 95


def test_a_worst_case_over_every_family_is_the_whole_pile() -> None:
    sizes = [3, 2, 1]
    assert pieces_upper_bound(count_upper_families=3, family_sizes=sizes) == 6
    assert pieces_upper_bound(count_upper_families=99, family_sizes=sizes) == 6
    assert pieces_upper_bound(count_upper_families=0, family_sizes=sizes) == 0


def test_an_absent_size_list_is_not_computable_and_is_never_zero() -> None:
    """AC-7 / AD-19. A Story-5.1 run genuinely froze no sizes. Answering 0 would be a claim that no
    pièce is at risk, which is the flattering direction and a lie."""
    assert pieces_upper_bound(count_upper_families=5, family_sizes=None) is None
    estimate = _estimate(family_sizes=None, sample_families=30)
    assert estimate.kind == KIND_BOUND
    assert estimate.count_upper_families is not None
    assert estimate.count_upper_pieces is None


def test_a_family_holds_at_least_one_piece() -> None:
    with pytest.raises(ValueError):
        pieces_upper_bound(count_upper_families=1, family_sizes=[3, 0])
    with pytest.raises(ValueError):
        pieces_upper_bound(count_upper_families=-1, family_sizes=[3])


def test_the_estimate_carries_the_bound_over_families_and_the_worst_case_over_pieces() -> None:
    sizes = [50] * 4 + [1] * 116          # 120 families, 400 pièces
    estimate = _estimate(
        population_families=120, population_pieces=sum(sizes), sample_families=30,
        family_sizes=sizes)
    direct = prevalence_upper_bound(120, 30, 0, confidence=0.95)
    assert estimate.count_upper_families == direct.count_upper
    assert estimate.prevalence_upper == direct.prevalence_upper
    expected = sum(sorted(sizes, reverse=True)[:direct.count_upper])
    assert estimate.count_upper_pieces == expected


# ── input 2: the census crossover — two registers, one boundary, no gradient ─────────────────────

def test_a_census_carries_an_exact_count_and_no_bound_at_all() -> None:
    estimate = _estimate(
        population_families=40, sample_families=40, relevant_families=3,
        relevant_pieces_drawn=47, family_sizes=[10] * 40)
    assert estimate.kind == KIND_CENSUS and estimate.is_census
    assert estimate.relevant_pieces == 47
    assert estimate.prevalence_upper is None
    assert estimate.count_upper_families is None
    assert estimate.count_upper_pieces is None


def test_one_family_short_of_a_census_is_a_sample_and_says_a_sample_s_sentence() -> None:
    """The crossover is n == N exactly. An 'almost a census' register would be a sample heard as a
    census, which is the one reading FR-22 forbids."""
    estimate = _estimate(
        population_families=40, sample_families=39, relevant_families=0, family_sizes=[10] * 40)
    assert estimate.kind == KIND_BOUND
    assert estimate.prevalence_upper is not None
    assert estimate.count_upper_families is not None
    assert estimate.relevant_pieces is None, "nothing is exact until everything was read"


def test_a_sample_whose_bound_reaches_zero_is_still_a_sample_not_a_census() -> None:
    """The interesting boundary, found while building this. 39 of 40 families read and none
    relevant: the hypergeometric rejects even D = 1 at 95 % (the one unread family would have been
    missed with probability 1/40 = 2.5 %, under alpha), so the bound is exactly zero.

    That is a true statement and it stays in the BOUND register. The two registers are told apart by
    their SHAPE — a census says *"all 40 were read"*, a sample says *"39 of 40 were drawn; at most
    0"* — never by whether the number happens to be zero. Collapsing them here would let a sample
    borrow a census's authority for free."""
    estimate = _estimate(
        population_families=40, sample_families=39, relevant_families=0, family_sizes=[10] * 40)
    assert estimate.count_upper_families == 0 and estimate.prevalence_upper == 0.0
    assert estimate.kind == KIND_BOUND and not estimate.is_census
    assert estimate.relevant_pieces is None
    assert estimate.sample_families < estimate.population_families


def test_a_census_that_found_nothing_still_states_a_fact_not_a_zero_percent() -> None:
    estimate = _estimate(
        population_families=40, sample_families=40, relevant_families=0, relevant_pieces_drawn=0,
        family_sizes=[10] * 40)
    assert estimate.kind == KIND_CENSUS
    assert estimate.prevalence_upper is None
    sentence = census_statement_fr(
        relevant_units=0, relevant_pieces=0, unit_fr=_FAMILIES_FR,
        piece_count=estimate.population_pieces)
    assert "%" not in sentence


def test_the_census_sentence_singularises_one_family_and_one_piece() -> None:
    sentence = census_statement_fr(
        relevant_units=1, relevant_pieces=1, unit_fr=_FAMILIES_FR, piece_count=9)
    assert "1 famille de quasi-doublon écartée — 1 pièce —" in sentence
    assert "familles" not in sentence


def test_the_census_sentence_states_a_legacy_bound_in_ITS_unit_not_in_families() -> None:
    """CONFIRMED [MEDIUM]. A legacy ``recall_review`` counted *pièces*; rendering its census as
    *"3 familles"* is the Story-5.1 denominator defect with the units swapped, in the one sentence
    a firm reads out loud."""
    sentence = census_statement_fr(
        relevant_units=3, relevant_pieces=None, unit_fr="pièces écartées", piece_count=40)
    assert "3 pièces écartées se sont révélées pertinentes" in sentence
    assert "famille" not in sentence
    assert "%" not in sentence


def test_an_empty_discarded_set_is_no_population_never_a_flattering_zero() -> None:
    estimate = _estimate(
        population_families=0, population_pieces=0, sample_families=0, relevant_families=0)
    assert estimate.kind == KIND_NO_POPULATION
    assert estimate.prevalence_upper is None and estimate.relevant_pieces is None


# ── input 3: repeated sampling — the ordinal travels with the number ─────────────────────────────

def test_a_first_draw_is_ordinal_one_and_is_not_repeated() -> None:
    assert _estimate(run_ordinal=1).repeated is False


def test_a_later_draw_over_the_same_population_says_so() -> None:
    estimate = _estimate(run_ordinal=3)
    assert estimate.repeated is True and estimate.run_ordinal == 3


def test_an_ordinal_below_one_is_refused() -> None:
    with pytest.raises(ValueError):
        _estimate(run_ordinal=0)


def test_the_ordinal_changes_nothing_about_the_number_itself() -> None:
    """It is a DECLARATION, not an adjustment. Pooling or discounting a repeated run would be a
    different estimator, and a different estimator ships only through Story 5.3's gate."""
    first = _estimate(run_ordinal=1, family_sizes=[2] * 120)
    third = _estimate(run_ordinal=3, family_sizes=[2] * 120)
    assert first.prevalence_upper == third.prevalence_upper
    assert first.count_upper_pieces == third.count_upper_pieces


# ── input 4: the method travels with the number ──────────────────────────────────────────────────

def test_every_estimate_names_the_method_that_produced_it() -> None:
    assert _estimate().method == ESTIMATOR_METHOD
    assert _estimate(population_families=0, sample_families=0).method == ESTIMATOR_METHOD
    assert _estimate(
        population_families=4, sample_families=4, family_sizes=[1] * 4).method == ESTIMATOR_METHOD


def test_the_method_is_the_one_the_run_recorded_never_today_s() -> None:
    """FR-23's actual mechanism. Stamping today's name onto a bound computed by an older statistic
    is how *"changing the method produces a new bound"* becomes *"changing the method silently
    restates the old one"* — the requirement inverted, with the same characters on screen."""
    older = _estimate(recorded_method="hypergeometric-upper-bound.v0")
    assert older.method == "hypergeometric-upper-bound.v0" != ESTIMATOR_METHOD


def test_a_run_that_recorded_no_method_carries_none_not_a_borrowed_provenance() -> None:
    """AD-19. A Story-5.1 run closed before the method was recorded. ``None`` says *unknown*; the
    current constant would say *"computed by today's statistic"*, which is a claim about the past
    nobody can check."""
    assert _estimate(recorded_method=None).method is None


def test_a_bound_register_with_no_recorded_bound_is_refused_not_invented() -> None:
    """The completion path always writes both numbers, so this is unreachable by any current
    writer — which is exactly when a silent default becomes permanent. Refusing means a future
    writer that forgets is found at the seam instead of shipping a bound with no provenance."""
    with pytest.raises(ValueError):
        _estimate(recorded_count_upper=None, recorded_prevalence_upper=None)


def test_the_method_name_is_versioned_so_a_change_is_visible() -> None:
    """Versioned, and spelled so the secret scanner does not read it as a token: a 24-plus
    character high-entropy literal in source is exactly what FR-51's check exists to catch, and
    weakening that check to accommodate a constant would be the wrong trade."""
    assert ESTIMATOR_METHOD.startswith("hypergeometric")
    assert ESTIMATOR_METHOD.endswith(".v1")


# ── refusals: impossible counts are refused where the estimate is born ───────────────────────────

def test_more_relevant_than_drawn_is_refused() -> None:
    with pytest.raises(ValueError):
        _estimate(sample_families=10, relevant_families=11)


def test_a_draw_larger_than_its_population_is_refused() -> None:
    with pytest.raises(ValueError):
        _estimate(population_families=10, sample_families=11)


def test_a_confidence_outside_the_open_unit_interval_is_refused() -> None:
    with pytest.raises(ValueError):
        _estimate(confidence=1.0)
    with pytest.raises(ValueError):
        _estimate(confidence=0.0)
