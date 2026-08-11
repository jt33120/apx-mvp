"""The simulation gate, and the proof that it can say no (Story 5.3, FR-23 / SM-1).

The first four tests are the gate itself: every scenario covers, every scenario is tight enough to
be worth stating, and the whole thing is deterministic.

The rest are the tests that matter more. **A gate nobody has watched refuse is a gate nobody knows
is connected** — and SM-1 names precisely this failure: *"a test that recomputes a wrong number and
gets the same wrong number passes."* So an unsound estimator, a broken pièce conversion and a
vacuous bound are each injected here, and the harness is required to catch each one.
"""

from __future__ import annotations

import pytest

from apx.eval import estimator_simulation as sim
from apx.eval.estimator_simulation import (
    COVERAGE_TARGET,
    MIN_TRIALS,
    Scenario,
    SimulationVerdict,
    build_population,
    run_all,
    run_scenario,
    unsound,
)

_VERDICTS = run_all()


# ── the gate ─────────────────────────────────────────────────────────────────────────────────────

def test_every_scenario_covers_the_truth_at_the_stated_confidence() -> None:
    """FR-23 / SM-1: a stated C% bound holds in at least C% of runs, over populations whose truth is
    known by construction. This is the assertion the product's right to state a number rests on."""
    failures = unsound(_VERDICTS)
    assert failures == (), (
        "the estimator is NOT proven sound — the correct response is the counts-only fallback, "
        f"never an adjustment to the statistic until it passes: {[v.scenario for v in failures]}")


@pytest.mark.parametrize("verdict", _VERDICTS, ids=lambda v: v.scenario)
def test_each_scenario_covers_both_claims(verdict: SimulationVerdict) -> None:
    """Both claims, named separately, so a failure says WHICH one broke. Claim 1 is the
    hypergeometric over families; claim 2 is the pièce worst case Story 5.2 invented, and it is the
    one duplicate structure actually bites."""
    assert verdict.family_coverage_lower >= verdict.target, "claim 1 (families) failed to cover"
    assert verdict.piece_coverage_lower >= verdict.target, "claim 2 (pièces) failed to cover"


def test_every_scenario_draws_enough_to_mean_anything() -> None:
    """A coverage figure from twenty draws is a number nobody should act on. Asserted so a future
    edit cannot turn the gate off without removing it."""
    for scenario in sim.SCENARIOS:
        assert scenario.trials >= MIN_TRIALS, scenario.name
    assert len(sim.SCENARIOS) >= 10, "too few scenarios to call this a gate"


def test_the_scenario_set_varies_prevalence_and_duplicate_structure() -> None:
    """FR-23 asks for both, and the second is the one that would be quietly dropped: a set of flat
    populations tests the textbook hypergeometric and nothing this build owns."""
    prevalences = {round(s.relevant / len(s.sizes), 3) for s in sim.SCENARIOS}
    assert len(prevalences) >= 5 and 0.0 in prevalences
    assert any(len(set(s.sizes)) > 1 for s in sim.SCENARIOS), "no duplicate structure anywhere"
    assert any(s.adversarial for s in sim.SCENARIOS), "the worst case for claim 2 is not exercised"
    assert {len(s.sizes) for s in sim.SCENARIOS} >= {40, 120, 1400}


def test_the_simulation_is_deterministic() -> None:
    """AD-2 and the SM-2 lesson: a CI failure must be a fact a developer can reproduce, not a mood.
    A strict rule on a noisy measure produces flaky builds, and flaky builds get disabled."""
    again = run_all()
    assert [(v.scenario, v.family_coverage, v.piece_coverage) for v in again] == [
        (v.scenario, v.family_coverage, v.piece_coverage) for v in _VERDICTS]


# ── the ceiling: sound is not enough ─────────────────────────────────────────────────────────────

def test_the_bound_is_tight_enough_to_be_worth_stating() -> None:
    """AC-2. ``count_upper = N`` covers the truth 100 % of the time and says nothing. Every scenario
    that declares a ceiling must come in under it, or the estimator is sound and useless."""
    by_name = {v.scenario: v for v in _VERDICTS}
    for scenario in sim.SCENARIOS:
        if scenario.tightness_ceiling is None:
            continue
        verdict = by_name[scenario.name]
        assert verdict.best_prevalence_upper <= scenario.tightness_ceiling, (
            f"{scenario.name}: the bound at zero found was {verdict.best_prevalence_upper:.3f}, "
            f"above the ceiling {scenario.tightness_ceiling}")


def test_a_vacuous_estimator_is_SOUND_and_still_fails_the_gate(monkeypatch) -> None:  # noqa: ANN001
    """The reason the ceiling exists. An estimator answering *"at most all of them"* passes every
    coverage assertion FR-23 asks for — 100 % coverage — and is worthless. A gate satisfiable by
    breaking the thing it guards is not a gate."""
    scenario = Scenario(
        "vacuous", (1,) * 120, relevant=2, sample=40, seed=99, tightness_ceiling=0.08)

    class _Vacuous:
        count_upper = 120

    monkeypatch.setattr(sim, "bound_for_run", lambda **k: _Vacuous())
    verdict = run_scenario(scenario)
    assert verdict.sound, "a vacuous bound covers everything — that is the whole problem"
    assert verdict.family_coverage == 1.0
    assert verdict.best_prevalence_upper > scenario.tightness_ceiling


# ── the gate can refuse: three injected defects, three catches ───────────────────────────────────

def test_the_harness_catches_an_estimator_that_under_covers(monkeypatch) -> None:  # noqa: ANN001
    """The defect the whole story exists for: a bound that is too tight is a number said to a judge
    that does not hold. Halving the count makes it under-cover, and the gate must refuse."""
    real = sim.bound_for_run

    def _too_tight(**kwargs: object):  # noqa: ANN202
        bound = real(**kwargs)  # type: ignore[arg-type]
        return type(bound)(**{**bound.__dict__, "count_upper": bound.count_upper // 2})

    monkeypatch.setattr(sim, "bound_for_run", _too_tight)
    verdict = run_scenario(
        Scenario("under-covering", (1,) * 120, relevant=30, sample=40, seed=77))
    assert not verdict.sound
    assert verdict.family_coverage < COVERAGE_TARGET


def test_the_harness_catches_a_piece_conversion_that_takes_the_SMALLEST_families(
    monkeypatch  # noqa: ANN001
) -> None:
    """Claim 2's own defect, and the one a proof cannot catch: ``sorted()`` without
    ``reverse=True``. The bound over families still covers, so claim 1 stays green — only the pièce
    claim moves, which is exactly why it is asserted separately."""
    monkeypatch.setattr(
        sim, "_pieces_upper", lambda count_upper, sizes: sum(sorted(sizes)[:count_upper]))
    verdict = run_scenario(
        Scenario("smallest-first", sim._few_large(120, 8, 40), relevant=8, sample=40, seed=22,
                 adversarial=True))
    assert verdict.family_coverage >= COVERAGE_TARGET, "claim 1 is untouched by this defect"
    assert verdict.piece_coverage < COVERAGE_TARGET, "claim 2 must catch it"
    assert not verdict.sound


def test_the_adversarial_assignment_is_what_makes_claim_two_bind() -> None:
    """The justification for Decision 2 in the story, as a measurement rather than an assertion.

    With relevance assigned uniformly, the pièce claim is trivially satisfied — the relevant
    families are average-sized, so the worst-case conversion has enormous slack. Assigned to the
    LARGEST families, the slack disappears and the claim binds at the family coverage. A harness
    without the adversarial scenario would report a comfortable pass on a claim it never tested."""
    shape = sim._few_large(120, 8, 40)
    uniform = run_scenario(Scenario("u", shape, relevant=8, sample=40, seed=22))
    adversarial = run_scenario(
        Scenario("a", shape, relevant=8, sample=40, seed=22, adversarial=True))
    assert uniform.piece_coverage > uniform.family_coverage, "slack under a uniform assignment"
    assert adversarial.piece_coverage == adversarial.family_coverage, "the adversarial case binds"


# ── the caveat travels with the verdict ──────────────────────────────────────────────────────────

def test_every_verdict_carries_what_it_does_NOT_validate() -> None:
    """AC-3. A verdict that travels without its own limits is how a simulation result becomes a
    claim about the world. The gold set and SM-17 are named, because that is where the residual
    uncertainty actually lives."""
    for verdict in _VERDICTS:
        assert "jeu gold" in verdict.does_not_validate_fr
        assert "SM-17" in verdict.does_not_validate_fr
        assert "échangeables" in verdict.validates_fr
        assert "%" not in verdict.does_not_validate_fr


# ── the population generator tells the truth ─────────────────────────────────────────────────────

def test_the_population_holds_the_truth_the_draw_is_never_shown() -> None:
    scenario = Scenario("t", sim._few_large(20, 3, 10), relevant=3, sample=5, seed=5,
                        adversarial=True)
    population = build_population(scenario)
    assert population.true_relevant_families == 3
    assert population.true_relevant_pieces == 30, "the adversarial pick takes the three of size 10"
    assert sum(population.all_sizes) == sum(scenario.sizes)
    assert len({u.family_id for u in population.units}) == 20


def test_a_scenario_below_the_trial_floor_is_refused() -> None:
    with pytest.raises(ValueError, match="below the floor"):
        build_population(Scenario("thin", (1,) * 10, relevant=1, sample=2, seed=1, trials=10))


def test_a_scenario_asking_for_more_than_exists_is_refused() -> None:
    with pytest.raises(ValueError, match="relevant families"):
        build_population(Scenario("x", (1,) * 4, relevant=5, sample=2, seed=1))
    with pytest.raises(ValueError, match="a draw of"):
        build_population(Scenario("y", (1,) * 4, relevant=1, sample=9, seed=1))


# ── the assertion is on EVIDENCE, not on a deterministic observation ─────────────────────────────

def test_the_coverage_lower_bound_is_below_the_observation_and_rises_with_trials() -> None:
    """The Wilson bound behaves: it never claims more than was seen, and more draws buy more."""
    assert sim.coverage_lower_bound(958, 1000) < 0.958
    assert sim.coverage_lower_bound(9580, 10_000) > sim.coverage_lower_bound(958, 1000)
    # a perfect run still does not claim certainty from a finite sample
    assert sim.coverage_lower_bound(100, 100) < 1.0
    with pytest.raises(ValueError):
        sim.coverage_lower_bound(0, 0)


def test_an_observation_inside_the_noise_is_NOT_treated_as_evidence() -> None:
    """The defect this file caught in itself. 0.958 observed in 500 draws is eight tenths of a
    standard error above 0.95 — consistent with a true coverage of 0.94 — and the first draft
    would have passed on it, deterministically, for ever."""
    assert 479 / 500 >= COVERAGE_TARGET, "the raw proportion clears the target"
    assert sim.coverage_lower_bound(479, 500) < COVERAGE_TARGET, "the evidence does not"


def test_every_scenario_has_the_trials_to_support_its_claim() -> None:
    """A scenario whose lower bound only clears the target because nothing went wrong is a scenario
    one unlucky draw from a red build — the flaky-gate pressure SM-2 warns about."""
    for verdict in _VERDICTS:
        assert verdict.trials >= MIN_TRIALS
        assert verdict.family_coverage_lower >= verdict.target, verdict.scenario
        assert verdict.piece_coverage_lower >= verdict.target, verdict.scenario


# ── the harness's own sampler is checked against exact arithmetic ────────────────────────────────

def _exact_coverage(population: int, defects: int, sample: int, confidence: float) -> float:
    """The coverage of the bound over (N, D, n), computed EXACTLY — no simulation.

    ``P(D <= count_upper(K))`` summed over the hypergeometric law of ``K``, in exact big-integer
    arithmetic. This is the number the Monte-Carlo estimate should converge to."""
    from math import comb
    denominator = comb(population, sample)
    total = 0.0
    lowest = max(0, sample - (population - defects))
    for found in range(lowest, min(sample, defects) + 1):
        weight = comb(defects, found) * comb(population - defects, sample - found) / denominator
        bound = sim.bound_for_run(
            population=population, sample_size=sample, relevant_found=found,
            confidence=confidence)
        if defects <= bound.count_upper:
            total += weight
    return total


def test_the_simulated_coverage_matches_the_exactly_computed_one() -> None:
    """The test the harness cannot pass by accident.

    Everything else here measures the ESTIMATOR through the harness's sampler. This measures the
    SAMPLER, against arithmetic that involves no drawing at all: a biased draw — correlated seeds,
    a degenerate shuffle, sampling with replacement by mistake — would move the simulated coverage
    away from the exact figure while every other assertion stayed green.

    ``flat-120-half-relevant`` is used because it is the tightest scenario in the set: its true
    coverage sits at ~0.956, close enough to the 0.95 target that a small bias would show."""
    exact = _exact_coverage(120, 60, 40, COVERAGE_TARGET)
    observed = {v.scenario: v for v in _VERDICTS}["flat-120-half-relevant"].family_coverage
    assert exact >= COVERAGE_TARGET, (
        f"the estimator does not cover even in exact arithmetic: {exact:.4f}")
    # 4 Monte-Carlo standard errors at this trial count — wide enough never to flake, narrow
    # enough that a real sampling bias cannot hide inside it.
    tolerance = 4.0 * (exact * (1.0 - exact) / 8_000) ** 0.5
    assert abs(observed - exact) <= tolerance, (
        f"the harness's draw disagrees with exact arithmetic: simulated {observed:.4f} vs exact "
        f"{exact:.4f} (tolerance {tolerance:.4f}) — the SAMPLER is suspect, not the estimator")


def test_the_exact_coverage_confirms_the_estimator_is_conservative() -> None:
    """Why the observed figures sit above the target rather than at it: an exact hypergeometric
    bound over-covers, because the distribution is discrete and the bound cannot land between two
    attainable values. Stated as a measurement, not as a docstring claim."""
    for population, defects, sample in ((120, 60, 40), (120, 30, 40), (40, 3, 20)):
        assert _exact_coverage(population, defects, sample, COVERAGE_TARGET) >= COVERAGE_TARGET


# ── the pièce conversion is checked EXACTLY, because no ceiling can judge it ─────────────────────

def test_the_piece_figure_at_zero_found_is_exactly_the_largest_families() -> None:
    """CONFIRMED [HIGH] by the review: the tightness ceiling watches the FAMILY bound, so a
    conversion returning the whole pile — maximally vacuous — covers 100 % of the time and passes
    every family-side leg while the sentence states "at most all of them, in pièces".

    A ceiling cannot fix it: with lumpy families the honest worst case really is 65 % of the pile
    (`few-large-120`), so "loose" and "vacuous" are not separable by magnitude. So the figure is
    asserted EXACTLY, against a computation this test does itself."""
    by_name = {v.scenario: v for v in _VERDICTS}
    for scenario in sim.SCENARIOS:
        verdict = by_name[scenario.name]
        d_zero = sim.bound_for_run(
            population=len(scenario.sizes), sample_size=scenario.sample, relevant_found=0,
            confidence=scenario.confidence).count_upper
        expected = sum(sorted(scenario.sizes, reverse=True)[:d_zero])
        assert verdict.best_count_upper_pieces == expected, scenario.name
        assert verdict.best_count_upper_pieces <= sum(scenario.sizes)


def test_a_conversion_that_returns_the_whole_pile_is_caught(monkeypatch) -> None:  # noqa: ANN001
    """The vacuous pièce conversion, injected. It covers perfectly and states nothing."""
    scenario = Scenario("vacuous-pieces", sim._few_large(120, 8, 40), relevant=8, sample=40,
                        seed=22, adversarial=True)
    monkeypatch.setattr(sim, "_pieces_upper", lambda count_upper, sizes: sum(sizes))
    verdict = run_scenario(scenario)
    assert verdict.piece_coverage == 1.0, "a vacuous conversion covers every time"
    assert verdict.sound, "and it is 'sound' — which is precisely why soundness is not enough"
    d_zero = sim.bound_for_run(
        population=120, sample_size=40, relevant_found=0, confidence=COVERAGE_TARGET).count_upper
    honest = sum(sorted(scenario.sizes, reverse=True)[:d_zero])
    assert verdict.best_count_upper_pieces > honest, "the exact assertion is what catches it"


def test_the_gate_covers_every_confidence_the_api_accepts() -> None:
    """CONFIRMED by the review: `confidence` is a free caller-supplied parameter on
    POST /sampling/runs, and ESTIMATOR_PROVEN licenses the bound at whatever level was asked for.
    A gate that certified 0.95 alone would be licensing levels it never tested."""
    levels = {s.confidence for s in sim.SCENARIOS}
    assert levels >= {0.90, 0.95, 0.99}, f"only certified at {sorted(levels)}"
    for verdict in _VERDICTS:
        assert verdict.family_coverage_lower >= verdict.target, verdict.scenario
