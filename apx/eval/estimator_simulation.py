"""The simulation gate — the estimator ships only if proven (Story 5.3, FR-23 / SM-1).

The failure this exists to prevent is recorded in the PRD's own §0.2. A figure was written into a
brief, a glossary, three FRs and a north-star metric as a statement about what triage had left
behind — **and the statement was the wrong estimand entirely**, and it survived every prior review
on editorial care alone. (The wording itself is not repeated here: it is a checked, banned phrasing,
and a comment is one copy-paste away from being a string.) SM-1 states the lesson in one line: *"a
test that recomputes a wrong number and gets the same wrong number passes."*

So this is not a harness that proves the estimator RUNS. It generates populations whose truth is
known by construction, draws from them many times through the product's own code, and asserts that
the stated C% bound covered the truth in at least C% of those draws.

**Two coverage claims, and the second is the one this build actually owns.**

1. Over **families** — ``P(D_true ≤ count_upper_families) ≥ C``. This validates the hypergeometric,
   which is textbook: passing it proves the *implementation*, not the mathematics.
2. Over ***pièces*** — ``P(relevant_pieces_true ≤ count_upper_pieces) ≥ C``, where the *pièce*
   figure is the sum of the ``D`` largest frozen family sizes (Story 5.2, OQ-4 input 1).

Claim 2 is where FR-23's *"varying duplicate structure"* bites. Duplicate structure is **wholly
irrelevant** to claim 1 — a hypergeometric over families does not know families have sizes — and
load-bearing for claim 2. A harness that varied duplicate structure and checked only claim 1 would
be an expensive no-op reporting a green build.

*(Claim 2 is provable on paper: on the event ``{D_true ≤ D_upper}`` the relevant pièces are at most
the sum of the ``D_true`` largest sizes, hence at most the sum of the ``D_upper`` largest, so it
inherits claim 1's coverage. It is simulated anyway, because the proof is about the estimator and
the test is about the implementation — a ``sorted()`` missing ``reverse=True`` satisfies the proof
and fails the test.)*

**Soundness is not the only requirement.** ``count_upper = N`` covers the truth 100 % of the time
and says nothing. Every scenario therefore also carries a **tightness ceiling**: the bound must be
materially below the population where the sampling fraction can support that. A gate satisfiable by
breaking the thing it guards is not a gate.

**What this does NOT validate**, stated here and carried on every verdict (AC-3): it validates the
estimator against **its assumed model** — a finite population of exchangeable units sampled without
replacement. It says nothing about whether a real *discarded set* resembles these populations. That
is what the *gold set* and calibration (SM-17) are for, and it is where the honest residual
uncertainty lives.

Deterministic: seeded per scenario, so a CI failure reproduces on a developer's machine rather than
arriving as a mood. *A strict rule on a noisy measure produces flaky builds, and flaky builds get
disabled — which is how a gold set stops running for the second time.*

**But determinism is not the same as evidence, and the first draft of this file confused the two.**
A seeded run gives the same number every time; it does not make that number a reliable estimate of
the underlying coverage. At 500 trials the tightest scenario observed 0.9580 against a target of
0.95 — eight tenths of a standard error, entirely consistent with a true coverage of 0.94. The gate
would have passed, deterministically, on evidence it did not have. So the assertion is made on a
one-sided lower confidence bound (:func:`coverage_lower_bound`) at a trial count large enough to
support it, and it now says what it means: *at 95 % confidence, the true coverage is at least C*.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from apx.core.domain.confidence import pieces_upper_bound
from apx.core.domain.sampling import SamplingUnit, bound_for_run, draw_families

# The confidence level every scenario is run at, and the coverage it must therefore reach.
COVERAGE_TARGET = 0.95

# The floor on trials per scenario, and what a scenario gets unless it says otherwise. Asserted by
# the gate check, so a future edit cannot quietly reduce the draws and keep the green tick — a gate
# whose sample size nobody asserts is a gate that can be turned off without being removed.
#
# The numbers are not arbitrary, and the first draft's were wrong. At 500 trials the tightest
# scenario cleared the target by **0.8 of a Monte-Carlo standard error** — an observed 0.9580 that
# is entirely consistent with a true coverage of 0.94. The gate was reporting a pass it had not
# earned, which is SM-1's own failure wearing the costume of a green build. See
# :func:`coverage_lower_bound`.
MIN_TRIALS = 2_000
DEFAULT_TRIALS = 8_000

# One-sided normal quantile for 95 % — the confidence the coverage claim is itself made at.
_Z_ONE_SIDED_95 = 1.6448536269514722


def coverage_lower_bound(covered: int, trials: int, z: float = _Z_ONE_SIDED_95) -> float:
    """A one-sided **Wilson score** lower confidence bound on the true coverage.

    Observing 0.958 in 500 draws is not evidence that coverage is at least 0.95 — the Monte-Carlo
    standard error at that size is 0.0097, so the observation sits inside the noise. Asserting the
    raw proportion against the target is the *"strict rule on a noisy measure"* the PRD warns about
    at SM-2, with the added sting that here it fails toward **passing**.

    So the assertion is on the lower bound, and it says what it means: *at 95 % confidence, the true
    coverage of this estimator is at least C*. Wilson rather than the normal approximation because
    most scenarios observe exactly 1.0, where the normal interval collapses to a point and claims
    infinite certainty from a finite sample."""
    if trials <= 0:
        raise ValueError("a coverage figure needs at least one trial")
    observed = covered / trials
    z2 = z * z
    denominator = 1.0 + z2 / trials
    centre = (observed + z2 / (2 * trials)) / denominator
    spread = z * ((observed * (1.0 - observed) / trials + z2 / (4 * trials * trials)) ** 0.5)
    return centre - spread / denominator


VALIDATES_FR = (
    "l'estimateur est vérifié contre son modèle : une population finie d'unités échangeables, "
    "tirée sans remise, dont la composition est connue par construction")
DOES_NOT_VALIDATE_FR = (
    "la simulation ne valide PAS l'hypothèse qu'un jeu écarté réel ressemble aux populations "
    "simulées : c'est le rôle du jeu gold et de la calibration (SM-17), et c'est là que "
    "l'incertitude résiduelle honnête se trouve")


@dataclass(frozen=True)
class SimulationVerdict:
    """What one scenario proved, and what it explicitly did not (AC-3).

    ``validates_fr`` / ``does_not_validate_fr`` carry FR-23's caveat as **data**, not as prose in a
    docstring nobody exports: a verdict that travels without its own limits is how a simulation
    result becomes a claim about the world."""

    scenario: str
    trials: int
    target: float
    family_coverage: float          # P(D_true <= count_upper_families), observed
    piece_coverage: float           # P(relevant pièces <= count_upper_pieces), observed
    # The bound this draw buys at zero found — DETERMINISTIC, and what the tightness ceiling is
    # asserted on. The loosest bound OBSERVED grows with the trial count (more draws reach a larger
    # k), so a ceiling on that would redden the build for the good change of running more trials.
    best_prevalence_upper: float
    # The pièce figure the SENTENCE states, at zero found. The family ceiling does not constrain it
    # — CONFIRMED by the review: a conversion returning the whole pile covers 100 % of the time and
    # passes every family-side leg. It is asserted EXACTLY, against an independent computation,
    # because with lumpy families the honest worst case is genuinely loose (0.65 of the pile in
    # `few-large-120`), so no ceiling can tell "loose but right" from "vacuous".
    best_count_upper_pieces: int
    worst_prevalence_upper: float   # the loosest bound seen — a diagnostic, not asserted
    # the one-sided 95 % LOWER bounds on the two coverages — what `sound` is actually judged on
    family_coverage_lower: float = 0.0
    piece_coverage_lower: float = 0.0
    validates_fr: str = VALIDATES_FR
    does_not_validate_fr: str = DOES_NOT_VALIDATE_FR

    @property
    def sound(self) -> bool:
        """Sound when the LOWER bound on each coverage clears the target — not the raw proportion.

        The difference is the whole point. An observed 0.958 in 500 draws does not establish
        coverage of 0.95; it is one standard error of noise away from 0.94. Judging on the
        observation would let the gate pass on evidence it does not have, and it would do so
        silently, which is the failure mode this entire story exists to close."""
        return (self.family_coverage_lower >= self.target
                and self.piece_coverage_lower >= self.target)

    @property
    def family_margin(self) -> float:
        """How much slack the observed coverage has over the target. Recorded rather than asserted:
        an exact hypergeometric bound is CONSERVATIVE by construction, so a healthy margin is
        expected — and a margin that collapses toward zero is worth a human noticing."""
        return self.family_coverage - self.target


@dataclass(frozen=True)
class Scenario:
    """One population shape and one way of drawing from it.

    ``sizes`` is the family-size multiset — the *duplicate structure*. ``relevant`` is how many
    families are truly relevant. ``adversarial`` assigns relevance to the **largest** families
    first, which is claim 2's worst case and would be sampled with vanishing probability by a
    uniform assignment at exactly the sizes where it matters."""

    name: str
    sizes: tuple[int, ...]
    relevant: int
    sample: int
    seed: int
    adversarial: bool = False
    trials: int = DEFAULT_TRIALS
    # The bound at ZERO FOUND must come in at or below this, or the estimator is sound and useless
    # — an estimator answering "at most all of them" covers every time and says nothing. ``None``
    # only where the sampling fraction genuinely cannot support a tight bound, and the scenario
    # exists to show that: drawing 1 of 4 buys almost nothing, and saying so is the honest answer.
    tightness_ceiling: float | None = None
    confidence: float = COVERAGE_TARGET


@dataclass
class _Population:
    """A population of families with known truth. ``units`` are what the draw sees; ``relevant_ids``
    is the truth it is never shown."""

    units: tuple[SamplingUnit, ...]
    relevant_ids: frozenset[str]
    sizes_by_id: dict[str, int] = field(default_factory=dict)

    @property
    def true_relevant_families(self) -> int:
        return len(self.relevant_ids)

    @property
    def true_relevant_pieces(self) -> int:
        return sum(self.sizes_by_id[fid] for fid in self.relevant_ids)

    @property
    def all_sizes(self) -> tuple[int, ...]:
        return tuple(self.sizes_by_id[u.family_id] for u in self.units)


def build_population(scenario: Scenario) -> _Population:
    """A population of families whose truth is known by construction.

    Family ``i`` holds ``sizes[i]`` *pièces* with synthetic identities. Relevance is assigned either
    uniformly at random (the ordinary case) or to the largest families first (``adversarial`` — the
    worst case for the *pièce* claim, since the worst-case conversion takes the D LARGEST sizes)."""
    if scenario.relevant > len(scenario.sizes):
        raise ValueError(
            f"{scenario.name}: {scenario.relevant} relevant families of {len(scenario.sizes)}")
    if scenario.sample > len(scenario.sizes):
        raise ValueError(
            f"{scenario.name}: a draw of {scenario.sample} from {len(scenario.sizes)} families")
    if scenario.trials < MIN_TRIALS:
        raise ValueError(
            f"{scenario.name}: {scenario.trials} trials is below the floor of {MIN_TRIALS} — a "
            "coverage figure from too few draws is a number nobody should act on")

    rng = random.Random(scenario.seed)
    units: list[SamplingUnit] = []
    sizes_by_id: dict[str, int] = {}
    for index, size in enumerate(scenario.sizes):
        family_id = f"fam-{index:05d}"
        members = tuple(f"{family_id}-p{m}" for m in range(size))
        units.append(SamplingUnit(
            family_id=family_id, proxy_piece_id=members[0], member_piece_ids=members))
        sizes_by_id[family_id] = size

    if scenario.adversarial:
        ordered = sorted(units, key=lambda u: (-sizes_by_id[u.family_id], u.family_id))
        relevant = {u.family_id for u in ordered[:scenario.relevant]}
    else:
        relevant = {u.family_id for u in rng.sample(units, scenario.relevant)}
    return _Population(
        units=tuple(units), relevant_ids=frozenset(relevant), sizes_by_id=sizes_by_id)


def _pieces_upper(count_upper: int, sizes: tuple[int, ...]) -> int:
    """The *pièce* worst case — through the **product's own** :func:`pieces_upper_bound`.

    An earlier draft re-implemented the rule here, on the theory that an independent restatement
    catches a divergence. It does the opposite: it validates the harness's arithmetic while the
    product's could be wrong, which is SM-1's named failure with the roles swapped. What is
    simulated must be what ships.

    It stays a named seam so a test can inject a wrong conversion and watch the gate refuse — see
    ``test_the_harness_catches_a_piece_conversion_that_takes_the_SMALLEST_families``."""
    return pieces_upper_bound(count_upper_families=count_upper, family_sizes=sizes) or 0


def run_scenario(scenario: Scenario) -> SimulationVerdict:
    """Draw ``trials`` times, and count how often each claim held.

    The estimator is memoised per ``(N, n, k, c)`` **here, in the harness** — never in the domain.
    The bound is a pure function of those four numbers, most trials repeat a handful of ``k``
    values, and a cache in the estimator itself would be state in a place that must not have any."""
    population = build_population(scenario)
    truth_families = population.true_relevant_families
    truth_pieces = population.true_relevant_pieces
    sizes = population.all_sizes
    total = len(population.units)

    cache: dict[int, int] = {}

    def count_upper_for(found: int) -> int:
        # Through `bound_for_run` — the function `complete_sampling_run` itself calls. Reaching
        # past it to `prevalence_upper_bound` would validate a path the product does not take,
        # which is a proof of the wrong thing.
        if found not in cache:
            cache[found] = bound_for_run(
                population=total, sample_size=scenario.sample, relevant_found=found,
                confidence=scenario.confidence).count_upper
        return cache[found]

    families_covered = pieces_covered = 0
    worst_prevalence = 0.0
    for trial in range(scenario.trials):
        # a distinct, reproducible seed per trial — the scenario seed alone would draw one sample
        drawn = draw_families(
            population.units, scenario.sample, seed=scenario.seed * 1_000_003 + trial)
        found = sum(1 for u in drawn if u.family_id in population.relevant_ids)
        count_upper = count_upper_for(found)
        if truth_families <= count_upper:
            families_covered += 1
        if truth_pieces <= _pieces_upper(count_upper, sizes):
            pieces_covered += 1
        worst_prevalence = max(worst_prevalence, count_upper / total)

    return SimulationVerdict(
        scenario=scenario.name, trials=scenario.trials, target=scenario.confidence,
        best_prevalence_upper=count_upper_for(0) / total,
        best_count_upper_pieces=_pieces_upper(count_upper_for(0), sizes),
        family_coverage=families_covered / scenario.trials,
        piece_coverage=pieces_covered / scenario.trials,
        family_coverage_lower=coverage_lower_bound(families_covered, scenario.trials),
        piece_coverage_lower=coverage_lower_bound(pieces_covered, scenario.trials),
        worst_prevalence_upper=worst_prevalence)


def _flat(n: int) -> tuple[int, ...]:
    return (1,) * n


def _few_large(n: int, large: int, size: int) -> tuple[int, ...]:
    return (size,) * large + (1,) * (n - large)


def _heavy_tail(n: int, biggest: int) -> tuple[int, ...]:
    """One enormous family, a few middling ones, the rest singletons — the shape FR-38 describes:
    forty variants of one email thread beside a pile of distinct documents."""
    return (biggest, biggest // 2, biggest // 4) + (1,) * (n - 3)


# The scenario set. Prevalence 0 / ~1 / ~5 / ~20 / 50 %, populations 40 / 120 / 1 400, duplicate
# structure flat / few-large / heavy-tailed, draws small / medium / near-census / census, and the
# adversarial relevance assignment that claim 2's worst case requires.
SCENARIOS: tuple[Scenario, ...] = (
    # ── the flat population: duplicate structure absent, so this isolates claim 1 ────────────────
    Scenario("flat-120-none-relevant", _flat(120), relevant=0, sample=40, seed=11,
             tightness_ceiling=0.08),
    Scenario("flat-120-one-relevant", _flat(120), relevant=1, sample=40, seed=12,
             tightness_ceiling=0.07),
    Scenario("flat-120-quarter-relevant", _flat(120), relevant=30, sample=40, seed=13,
             tightness_ceiling=0.07),
    Scenario("flat-120-half-relevant", _flat(120), relevant=60, sample=40, seed=14,
             tightness_ceiling=0.07),
    Scenario("flat-40-near-census", _flat(40), relevant=3, sample=39, seed=15,
             tightness_ceiling=0.01),
    Scenario("flat-40-census", _flat(40), relevant=3, sample=40, seed=16,
             tightness_ceiling=0.01),
    # ── duplicate structure: this is what claim 2 is for ─────────────────────────────────────────
    Scenario("few-large-120-uniform", _few_large(120, 8, 40), relevant=8, sample=40, seed=21,
             tightness_ceiling=0.07),
    Scenario("few-large-120-adv", _few_large(120, 8, 40), relevant=8, sample=40, seed=22,
             adversarial=True, tightness_ceiling=0.07),
    Scenario("heavy-tail-120-adv", _heavy_tail(120, 200), relevant=3, sample=30, seed=23,
             adversarial=True, tightness_ceiling=0.09),
    Scenario("heavy-tail-120-one-adv", _heavy_tail(120, 200), relevant=1,
             sample=30, seed=24, adversarial=True, tightness_ceiling=0.09),
    # ── the real scale FR-23 quotes: 200 of 1 400 ────────────────────────────────────────────────
    Scenario("realistic-1400-none-relevant", _few_large(1400, 8, 40), relevant=0, sample=200,
             seed=31, tightness_ceiling=0.02),
    Scenario("realistic-1400-rare-adv", _few_large(1400, 8, 40), relevant=14, sample=200,
             seed=32, adversarial=True, tightness_ceiling=0.02),
    # ── other confidence levels: `confidence` is a free parameter on POST /sampling/runs, so a
    # gate that certified 0.95 alone would license every level the product accepts (review) ──────
    Scenario("flat-120-at-90pc", _flat(120), relevant=12, sample=40, seed=51,
             confidence=0.90, tightness_ceiling=0.05),
    Scenario("flat-120-at-99pc", _flat(120), relevant=12, sample=40, seed=52,
             confidence=0.99, tightness_ceiling=0.10),
    Scenario("few-large-120-at-99pc-adv", _few_large(120, 8, 40), relevant=8, sample=40, seed=53,
             confidence=0.99, adversarial=True, tightness_ceiling=0.10),
    # ── the degenerate edges ─────────────────────────────────────────────────────────────────────
    Scenario("tiny-4-census", _flat(4), relevant=1, sample=4, seed=41, tightness_ceiling=0.01),
    # the one scenario with NO ceiling, deliberately: one draw from four buys a bound of 0.75, and
    # the honest report is that this draw is not worth making — not a tighter number.
    Scenario("tiny-4-one-drawn", _flat(4), relevant=1, sample=1, seed=42),
)


def run_all() -> tuple[SimulationVerdict, ...]:
    """Every scenario, in order. Deterministic: the same tuple on every machine, every run."""
    return tuple(run_scenario(s) for s in SCENARIOS)


def unsound(verdicts: tuple[SimulationVerdict, ...]) -> tuple[SimulationVerdict, ...]:
    """The verdicts that failed to cover. Empty is the only shippable answer (FR-23)."""
    return tuple(v for v in verdicts if not v.sound)
