"""The *sampling run* — a random draw from the **discarded set**, frozen (Story 5.1, FR-22).

Epic 5's north-star sentence quantifies *the discarded set*. This module owns the pure vocabulary of
the draw that produces it: what the population **is**, what a single draw **is**, how big the draw
must be to reach a stated bound, and when a run has stopped answering the question it was started
to answer.

**The population is the derived view, never the label pile** (planning decision A1,
``_bmad-output/implementation-artifacts/epic-5-planning-2026-08-07.md``). The discarded set is
:func:`~apx.core.domain.triage_sets.derive_triage_sets`'s ``discarded`` — one ranked order, cut by
**the line**, overridden by *pins* (AD-39). It is not
``label_record WHERE label = 'discard'``: that pile has no *ranking version* and no line, so FR-22's
freeze contract (*"records the ranking version, the position of the line, the RBAC scope and the
explicit identifier list"*) cannot even be stated over it — and a *pièce* the lawyer deliberately
pinned back across the line would still be handed to her to review.

**The unit of the draw is the near-duplicate family, not the *pièce*.** Forty copies of one email
are not forty independent draws (FR-38, and epics.md 5.2: *"the near-duplicate grouping of FR-38
feeds the unit of the draw, so a family counts as it should rather than as its member count"*).
A :class:`SamplingUnit` is one family **restricted to the discarded set**, and the *pièce* the
lawyer actually reads is its **proxy**. What a family then *counts as* in the estimator is Story
5.2's decision, not this module's: here a family is one draw and the frozen record keeps every
member identity so 5.2 can decide without a re-draw.

Pure: no clock, no I/O, no store, Domain imports only (AD-4). The seed is an argument, so the draw
is reproducible in a test — but a seed is **never** the record of what was drawn (FR-22: *"a seed
alone is insufficient"*), which is why :func:`draw_families` returns the units themselves and the
store freezes their identifiers.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from apx.core.domain.confidence import (
    PrevalenceBound,
    estimator_is_proven,
    pieces_upper_bound,
    prevalence_upper_bound,
)
from apx.core.domain.freshness import trigger

# The run's **stored** status: what a person did to it. Append-only string values (a persisted
# status must always decode).
STATUS_OPEN = "open"            # drawn, verdicts being recorded
STATUS_COMPLETED = "completed"  # verdicts closed, bound computed
STATUS_ABANDONED = "abandoned"  # explicitly given up — its verdicts stay readable forever (AD-7)

# The run's **derived** state, which is what the surface renders. ``invalidated`` is NOT a stored
# status: it is the verdict of comparing the run's freshness stamp against the current one
# (Story 4.13). A stored flag would have to be SET by every writer, and a writer that forgets leaves
# the run *falsely valid* — the failure AD-23 names for staleness, and the recurring defect the
# Epic 4 retrospective identified. A comparison cannot forget.
STATE_INVALIDATED = "invalidated"

STATUSES: tuple[str, ...] = (STATUS_OPEN, STATUS_COMPLETED, STATUS_ABANDONED)

# The two registers a completed run can speak in, and the third thing that is neither (Story 5.2,
# OQ-4 input 2). They are DISJOINT: a census states an exact count and carries no bound, a sample
# states a bound and carries no exact count. The crossover is ``n == N`` exactly and there is no
# third register near it — an "almost a census" would be a sample heard as a census, which is the
# one reading FR-22 forbids in as many words.
KIND_CENSUS = "census"
KIND_BOUND = "bound"
KIND_NO_POPULATION = "no_population"
# Story 5.3 — the fourth register, and the one that can say no. FR-23: an estimator that has not
# been proven sound by simulation *"never emits a bound it cannot defend"*; it emits the counts it
# actually observed, and nothing derived from them. Disjoint in the TYPE like the other three, so a
# surface cannot render a bound the product has not earned by forgetting to consult a flag.
KIND_COUNTS_ONLY = "counts_only"
ESTIMATE_KINDS: tuple[str, ...] = (
    KIND_CENSUS, KIND_BOUND, KIND_NO_POPULATION, KIND_COUNTS_ONLY)


@dataclass(frozen=True)
class SamplingUnit:
    """One near-duplicate family, **restricted to the discarded set** — the unit of the draw.

    ``member_piece_ids`` holds the family's discarded members **only**, in rank order. A member of
    the same family that sits above **the line** is retained, is therefore not in the discarded set,
    and must not be counted into a population it does not belong to. Because ``ranking.py`` keeps a
    family contiguous in rank order, at most one family can straddle the line at all — but the rule
    is written here so the straddling case is *total*, never an exclusion and never an imputation
    (AD-19).

    ``proxy_piece_id`` is the *pièce* the lawyer actually reads: the family's **lowest-rank
    discarded member**, which is the near-duplicate representative whenever the representative is
    itself discarded. A verdict on the proxy is a verdict on the whole family — that is what a
    near-duplicate family *is*. A reader who does not know this will mistake the resulting bound for
    a per-*pièce* one.
    """

    family_id: str
    proxy_piece_id: str
    member_piece_ids: tuple[str, ...]

    @property
    def member_count(self) -> int:
        """How many discarded *pièces* this one draw stands for."""
        return len(self.member_piece_ids)


def group_discarded_families(
    discarded_in_rank_order: Sequence[tuple[str, str]],
) -> tuple[SamplingUnit, ...]:
    """Group the discarded set into :class:`SamplingUnit` families.

    ``discarded_in_rank_order`` is ``(piece_id, family_id)`` for every *pièce* in the discarded set,
    **in rank order** — the caller (the store) restricts the ranked order to
    ``derive_triage_sets(...).discarded`` before calling. Families come back in the rank order of
    their proxy, so the first member seen for a family is its lowest-ranked one.

    A *pièce* appearing twice raises rather than being deduplicated: it would mean the ranked order
    and the derived view disagree, and a population assembled from a disagreement is not a
    population (AD-19 — nothing imputed).
    """
    order: list[str] = []
    members: dict[str, list[str]] = {}
    seen: set[str] = set()
    for piece_id, family_id in discarded_in_rank_order:
        if piece_id in seen:
            raise ValueError(f"sampling: pièce appears twice in the discarded set: {piece_id}")
        seen.add(piece_id)
        if family_id not in members:
            members[family_id] = []
            order.append(family_id)
        members[family_id].append(piece_id)
    return tuple(
        SamplingUnit(
            family_id=fid, proxy_piece_id=members[fid][0], member_piece_ids=tuple(members[fid]))
        for fid in order)


def draw_families(
    units: Sequence[SamplingUnit], size: int, *, seed: int
) -> tuple[SamplingUnit, ...]:
    """Draw ``size`` families uniformly **without replacement**, in **draw order**.

    Without replacement because the population is finite and the estimator behind the bound is
    hypergeometric (``confidence.prevalence_upper_bound``) — drawing with replacement would make the
    bound wrong in the direction that flatters the product.

    Draw order, not rank order: presenting the sample sorted by rank would tell the lawyer which
    *pièces* sit nearest **the line** before she has judged them, which is exactly the information
    that would bias the verdicts the bound is computed from.

    ``size`` is clamped to the population — asking for more than exists is a census, not an error.
    A ``size`` below 1 raises: a run that drew nothing has no verdicts to give and would produce the
    honest-but-useless bound "the whole pile could be relevant" while looking like a review.
    """
    if size < 1:
        raise ValueError(f"sampling: a draw must take at least one family: {size}")
    if not units:
        raise ValueError("sampling: the discarded set is empty — there is nothing to draw")
    return tuple(random.Random(seed).sample(list(units), min(size, len(units))))


@dataclass(frozen=True)
class Sizing:
    """How big a draw must be to reach a target *confidence bound* — the answer to *"I want to be
    able to say at most 1%"* (FR-22).

    ``size`` is ``None`` when the target cannot be reached at any size the caller is willing to
    offer; ``achievable_prevalence_upper`` is then the **best** bound available, so the tool always
    answers with something true rather than refusing (FR-22: *"the tool says so and offers the best
    achievable"*).

    Every field is computed under the **best case** ``relevant_found = 0``. A sizing is a plan, not
    a result: if the lawyer finds relevant material in the sample the achieved bound is looser than
    the planned one, and the run reports what it achieved, never what it planned.
    """

    population: int
    target_prevalence: float
    confidence: float
    size: int | None
    is_census: bool
    achievable_prevalence_upper: float
    reason_fr: str


# The two ways a *matter* can have nothing to draw over. They are DIFFERENT facts and must read
# differently: "le jeu écarté est vide" told to a lawyer whose dossier was never ranked is a false
# statement about her file — it says the tool looked and found nothing, when the tool never looked.
NO_POPULATION_FR = "le jeu écarté est vide : aucune borne ne s'applique"
NO_CUT_FR = ("aucun classement ou aucune ligne posée : le jeu écarté n'existe pas encore, "
             "il n'y a donc rien à auditer")


def no_population_sizing(
    *, target_prevalence: float, confidence: float, reason_fr: str,
) -> Sizing:
    """A :class:`Sizing` for a *matter* with nothing to draw over — an honest answer, never a
    refusal and never a flattering 0%. The caller supplies WHICH of the two facts it is."""
    return Sizing(
        population=0, target_prevalence=target_prevalence, confidence=confidence, size=None,
        is_census=False, achievable_prevalence_upper=0.0, reason_fr=reason_fr)


def size_for_target(
    *, population: int, target_prevalence: float, confidence: float = 0.95,
    max_size: int | None = None,
) -> Sizing:
    """The **smallest** draw reaching ``target_prevalence`` at ``confidence``, or the best there is.

    The bound at ``relevant_found = 0`` is non-increasing in the draw size, so the smallest
    sufficient size is found by binary search — about ``log2(population)`` evaluations.

    Three outcomes, each named in French on :attr:`Sizing.reason_fr`:

    - **a sample** — some size strictly below the population reaches the target;
    - **a census** — only reviewing the whole discarded set reaches it. A census is not a tighter
      bound, it is a **categorically stronger statement**: nothing is estimated, everything was
      read (FR-22). The caller must label it as one and must not present it as a sample estimate;
    - **unreachable** — either the discarded set is empty (there is no claim to make: *no bound
      applies*, never a flattering 0%), or ``max_size`` caps the draw below what the target needs.

    ``max_size`` is what the caller is willing to ask a human to read. Without it, a census always
    reaches any target in ``[0, 1)`` — the census bound at zero found is exactly 0.0 — so the
    unreachable branch would be reachable only on an empty population.
    """
    if not 0 < confidence < 1:
        raise ValueError(f"confidence must be in (0, 1): {confidence}")
    if not 0.0 <= target_prevalence < 1.0:
        raise ValueError(f"target prevalence must be in [0, 1): {target_prevalence}")
    if population < 0:
        raise ValueError(f"population must be non-negative: {population}")

    if population == 0:
        # Mirrors the Story 4.9 rule for an empty discarded set: no bound applies. Reporting 0%
        # would be a flattering claim about a set that does not exist.
        return no_population_sizing(
            target_prevalence=target_prevalence, confidence=confidence,
            reason_fr=NO_POPULATION_FR)

    cap = population if max_size is None else max(0, min(max_size, population))

    def reached(n: int) -> bool:
        return prevalence_upper_bound(
            population, n, 0, confidence=confidence).prevalence_upper <= target_prevalence

    if cap < 1 or not reached(cap):
        best = prevalence_upper_bound(
            population, cap, 0, confidence=confidence).prevalence_upper if cap >= 1 else 1.0
        return Sizing(
            population=population, target_prevalence=target_prevalence, confidence=confidence,
            size=None, is_census=False, achievable_prevalence_upper=best,
            reason_fr=(
                f"cible inatteignable : au mieux {best:.1%} en examinant {cap} familles"))

    lo, hi = 1, cap
    while lo < hi:
        mid = (lo + hi) // 2
        if reached(mid):
            hi = mid
        else:
            lo = mid + 1
    achieved = prevalence_upper_bound(population, lo, 0, confidence=confidence)
    is_census = lo == population
    return Sizing(
        population=population, target_prevalence=target_prevalence, confidence=confidence,
        size=lo, is_census=is_census,
        achievable_prevalence_upper=achieved.prevalence_upper,
        reason_fr=(
            "recensement : la cible n'est atteinte qu'en examinant tout le jeu écarté"
            if is_census else
            f"{lo} familles sur {population} suffisent pour {target_prevalence:.1%}"))


def bound_for_run(
    *, population: int, sample_size: int, relevant_found: int, confidence: float,
) -> PrevalenceBound:
    """The bound a completed run achieved, over **the unit it drew** (families, not *pièces*).

    Story 5.1 deliberately reuses ``confidence.prevalence_upper_bound`` unchanged: it is already the
    finite-population hypergeometric statistic and is already exact at a census. Story 5.2 answers
    the estimator's five hard inputs (OQ-4) and Story 5.3 gates it by simulation; until then this
    story ships the number the product already ships, over a population that is finally the right
    one. Nothing here makes it newly trustworthy, and nothing here pretends it does.
    """
    return prevalence_upper_bound(
        population, sample_size, relevant_found, confidence=confidence)


def is_census(*, population: int, sample_size: int) -> bool:
    """True when the draw covered the whole discarded set. A census produces *"every discarded
    pièce was reviewed"* — a statement of fact, not an estimate (FR-22)."""
    return population > 0 and sample_size >= population


# ── the WORDS live one module over (Story 5.4) ───────────────────────────────────────────────────
#
# ``census_statement_fr`` and ``counts_only_statement_fr`` used to live here, while the bound
# sentence was composed inline in the app-layer read seam and ``no_population`` had no sentence at
# all. Three homes for four registers, across two layers.
#
# FR-23 makes the banned-phrasing list a STRUCTURAL property (FR-56), and a check over the words is
# only as good as its knowledge of where the words are. They are now all in
# ``apx.core.domain.statement``, which imports from this module and never the other way round: the
# register constants and the arithmetic are here, the sentences are there.


@dataclass(frozen=True)
class Estimate:
    """What a completed *sampling run* supports, in one object (Story 5.2, FR-23/OQ-4).

    The five hard inputs are answered *in this shape*, not only in prose:

    - **the unit** is the near-duplicate family, so ``population_families`` / ``sample_families`` /
      ``relevant_families`` are family counts throughout and the hypergeometric is applied to a
      population whose members are actually exchangeable (input 1);
    - **the two registers are disjoint fields.** ``kind == KIND_CENSUS`` carries ``relevant_pieces``
      (exact) and leaves ``prevalence_upper`` / ``count_upper_families`` / ``count_upper_pieces``
      ``None``; ``kind == KIND_BOUND`` carries the bound and leaves ``relevant_pieces`` ``None``. A
      renderer cannot read one as the other by accident (input 2);
    - **``count_upper_pieces`` is a WORST CASE**, the sum of the ``count_upper_families`` largest
      frozen family sizes — never ``prevalence_upper × population_pieces`` (input 1). ``None`` means
      *not computable* (a run frozen before the size list existed), never *zero* (AD-19);
    - **``run_ordinal``** is how many runs over this same frozen population came first, counting the
      abandoned ones. ``1`` is the first draw (input 3);
    - **``method``** names the statistic, so a later change of method produces a new bound rather
      than silently restating this one (input 4, FR-23).

    ``kind == KIND_NO_POPULATION`` is the empty discarded set: no claim applies, and it is
    emphatically not a flattering 0 %.
    """

    kind: str
    method: str
    confidence: float
    population_families: int
    population_pieces: int
    sample_families: int
    relevant_families: int
    run_ordinal: int
    # ── the bound register only ──────────────────────────────────────────────────────────────────
    count_upper_families: int | None = None
    prevalence_upper: float | None = None
    count_upper_pieces: int | None = None     # a WORST CASE; None = not computable
    # ── the census register only ─────────────────────────────────────────────────────────────────
    relevant_pieces: int | None = None        # EXACT; every pièce was read

    @property
    def is_census(self) -> bool:
        return self.kind == KIND_CENSUS

    @property
    def repeated(self) -> bool:
        """True when this is not the first draw over its frozen population — the multiple-
        comparisons fact FR-22 requires to travel with the number, because the sentence travels
        alone."""
        return self.run_ordinal > 1


def estimate_for_run(
    *, population_families: int, population_pieces: int, sample_families: int,
    relevant_families: int, relevant_pieces_drawn: int, confidence: float,
    family_sizes: Sequence[int] | None, recorded_count_upper: int | None,
    recorded_prevalence_upper: float | None, recorded_method: str | None, run_ordinal: int = 1,
) -> Estimate:
    """The **one** function that turns a completed run into an :class:`Estimate` (AD-37).

    One owning derivation is the structural answer to OQ-4's third input: a bound rests on exactly
    one run, so there is exactly one place a bound can be born and no second path that could pool
    two draws over one population. ``relevant_pieces_drawn`` is how many *pièces* the
    found-relevant DRAWN families hold; it is the exact answer only at a census, where the drawn
    families are the population, and it is ignored in the bound register for that reason.

    **The numbers are READ, never recomputed.** ``recorded_count_upper`` /
    ``recorded_prevalence_upper`` / ``recorded_method`` come off the run's own row: a completed
    bound is a recorded artefact with a lifetime (FR-58), and recomputing it here with today's
    statistic would mean the screen and the export could disagree the day the method changes —
    which is exactly the mechanism FR-23 asks for and would silently defeat. A run that recorded no
    method carries ``None``, never today's name (AD-19).
    """
    if not 0 < confidence < 1:
        raise ValueError(f"confidence must be in (0, 1): {confidence}")
    if population_families < 0 or population_pieces < 0:
        raise ValueError("counts must be non-negative")
    if not 0 <= relevant_families <= sample_families <= population_families:
        raise ValueError(
            f"impossible counts: {relevant_families} relevant of {sample_families} drawn "
            f"from {population_families}")
    if run_ordinal < 1:
        raise ValueError(f"the first run over a population is ordinal 1: {run_ordinal}")

    common = {
        "method": recorded_method, "confidence": confidence,
        "population_families": population_families, "population_pieces": population_pieces,
        "sample_families": sample_families, "relevant_families": relevant_families,
        "run_ordinal": run_ordinal,
    }
    if population_families == 0:
        return Estimate(kind=KIND_NO_POPULATION, **common)
    if is_census(population=population_families, sample_size=sample_families):
        # Nothing is estimated. No bound, no percentage, no worst case — an exact count.
        #
        # Story 5.3: a census survives an UNPROVEN estimator, and deliberately so. It makes no
        # statistical claim at all — every unit was read, and the count is a fact about what the
        # lawyer saw. Suppressing it because the *estimator* is unproven would withhold a true
        # statement on the grounds that a different, absent statement is untrustworthy.
        return Estimate(kind=KIND_CENSUS, relevant_pieces=relevant_pieces_drawn, **common)
    if not estimator_is_proven():
        # FR-23's failure path (Story 5.3): the simulation gate has not passed, so the product
        # states what it counted and nothing derived from it — no percentage, no projection, no
        # worst case. Emitting a bound here is the §0.2 failure exactly: a number said out loud
        # that nobody has shown to be right.
        return Estimate(kind=KIND_COUNTS_ONLY, **common)
    if recorded_count_upper is None or recorded_prevalence_upper is None:
        raise ValueError(
            "a completed run in the bound register recorded no bound — there is nothing to state, "
            "and inventing one here would be a number with no provenance (AD-19)")
    return Estimate(
        kind=KIND_BOUND,
        count_upper_families=recorded_count_upper,
        prevalence_upper=recorded_prevalence_upper,
        count_upper_pieces=pieces_upper_bound(
            count_upper_families=recorded_count_upper, family_sizes=family_sizes),
        **common)


@dataclass(frozen=True)
class VerdictEntry:
    """One recorded verdict on one drawn family — **append-only** (FR-24: a correction is a new
    entry, never an edit). ``seq`` is monotonic per run, so the current verdict on a family is the
    max-``seq`` row and the earlier ones stay readable as the record of a mind changed."""

    family_id: str
    relevant: bool
    actor: str
    at: datetime
    seq: int


@dataclass(frozen=True)
class DrawnFamily:
    """One family that was drawn, with its **current** verdict (the max-``seq`` view) or ``None``
    when it has not been judged yet. ``draw_index`` is its position in the draw — the order the
    lawyer is offered them, which is deliberately not rank order."""

    unit: SamplingUnit
    draw_index: int
    verdict: VerdictEntry | None


@dataclass(frozen=True)
class SamplingRunView:
    """A *sampling run* read back — the frozen population, the draw, the verdicts, and the numbers
    if it completed (FR-22).

    The freeze is these five fields together: ``version_id``/``version_no``,
    ``last_retained_piece_id`` (the position of **the line**, by identity and never by a bare
    integer), ``pin_ledger_seq``, ``scope``, and the explicit identifiers carried on ``drawn``. A
    ``seed`` is recorded too, but only as a convenience for reproducing a draw in a test: FR-22 is
    explicit that *a seed alone is insufficient*, and ``sampling_run_item`` is what makes the
    population re-readable without re-deriving anything.

    ``population_families`` is the unit the bound is computed over; ``population_pieces`` is how
    many *pièces* those families hold. They differ whenever near-duplicates exist, and a surface
    that showed one while saying the other would be stating a bound over a population nobody drew.
    """

    run_id: str
    matter: str
    version_id: str
    version_no: int
    last_retained_piece_id: str
    pin_ledger_seq: int
    scope: str
    confidence: float
    population_families: int
    population_pieces: int
    sample_size: int
    seed: int
    status: str
    started_by: str
    started_at: datetime
    completed_at: datetime | None
    relevant_found: int | None
    count_upper: int | None
    prevalence_upper: float | None
    drawn: tuple[DrawnFamily, ...]
    # ── Story 5.2 ────────────────────────────────────────────────────────────────────────────────
    # The size of EVERY family in the frozen population, sorted descending — including the ones
    # nobody drew, as they were at draw time. It is what makes the *pièce* worst case computable
    # without re-deriving a set that may since have moved (OQ-4 inputs 1 and 4). ``None`` is a run
    # frozen before this list existed: the worst case is then *not computable* and is never guessed.
    population_family_sizes: tuple[int, ...] | None = None
    # How many runs over this same frozen population came first, counting the ABANDONED ones —
    # abandon-and-redraw is the cheapest route to a favourable number, so a count that ignored it
    # would flatter exactly the behaviour it exists to make visible (OQ-4 input 3). Derived, never
    # stored: a stored counter has to be incremented by every writer, and one that forgets leaves a
    # third draw reading as the first.
    run_ordinal: int = 1
    # The method that produced ``count_upper`` / ``prevalence_upper``, by name — ``None`` on a run
    # that has not completed, or one closed before the method was recorded (FR-23).
    estimator_method: str | None = None

    @property
    def is_census(self) -> bool:
        """Whether the draw covered the whole discarded set — **derived here**, from the same two
        numbers :func:`estimate_for_run` uses (Story 5.2).

        ``sampling_run.is_census`` is still written at the draw as the record of what was decided,
        but nothing READS it: a stored boolean and a derived one are two referents for one fact, and
        the surface would eventually render one while the sentence spoke the other. That is the
        defect this epic exists to prevent, in miniature."""
        return is_census(population=self.population_families, sample_size=self.sample_size)

    @property
    def verdicts_recorded(self) -> int:
        """How many drawn families carry a verdict — what the surface counts down from."""
        return sum(1 for d in self.drawn if d.verdict is not None)

    @property
    def fully_judged(self) -> bool:
        return bool(self.drawn) and self.verdicts_recorded == len(self.drawn)

    @property
    def relevant_so_far(self) -> int:
        return sum(1 for d in self.drawn if d.verdict is not None and d.verdict.relevant)

    @property
    def frozen_piece_ids(self) -> tuple[str, ...]:
        """Every *pièce* identity the run froze, across all drawn families, in draw order — FR-22's
        *"explicit identifier list"*, readable without consulting the current discarded set."""
        return tuple(pid for d in self.drawn for pid in d.unit.member_piece_ids)

    @property
    def relevant_pieces_drawn(self) -> int:
        """How many *pièces* the families judged relevant hold — **exact**, by frozen identity.

        It is the population's answer only at a census, where the drawn families ARE the
        population. At a sample it is a fact about the sample and nothing more, which is why
        :func:`estimate_for_run` uses it in one register only."""
        return sum(
            len(d.unit.member_piece_ids)
            for d in self.drawn if d.verdict is not None and d.verdict.relevant)

    @property
    def estimate(self) -> Estimate | None:
        """What this run supports, or ``None`` while it supports nothing (Story 5.2).

        Only a **completed** run has an estimate. An open run's running tally is provisional and
        FR-22 is explicit that the surface must never imply that stopping now preserves a better
        number; an abandoned run produces no bound at all, by its own definition."""
        if self.status != STATUS_COMPLETED:
            return None
        return estimate_for_run(
            population_families=self.population_families,
            population_pieces=self.population_pieces,
            sample_families=self.sample_size,
            relevant_families=self.relevant_found or 0,
            relevant_pieces_drawn=self.relevant_pieces_drawn,
            confidence=self.confidence,
            family_sizes=self.population_family_sizes,
            recorded_count_upper=self.count_upper,
            recorded_prevalence_upper=self.prevalence_upper,
            recorded_method=self.estimator_method,
            run_ordinal=self.run_ordinal)


class RerankCountMismatch(ValueError):
    """The confirmation did not name the set the re-rank is about to destroy. Refused, for the
    reason FR-45(a) refuses a bulk validation whose count moved: a confirmation of a different act
    is not a confirmation of this one."""


def check_confirmed_runs(open_runs: int, confirmed: int) -> int:
    """The re-rank's confirmation names the number of open *sampling runs* it will invalidate.

    The **shape** of :func:`~apx.core.domain.validation.check_confirmed_count`, not the function:
    that one's message says *"the confirmation named N pièce(s)"*, and a run count passed through it
    would print a sentence about *pièces* on a dialog about *runs*. Reuse the shape, name the
    referent."""
    if open_runs != confirmed:
        raise RerankCountMismatch(
            f"la confirmation porte sur {confirmed} tirage(s) et l'acte en invalide {open_runs} — "
            "le nombre a changé depuis l'affichage")
    return open_runs


@dataclass(frozen=True)
class RerankCost:
    """What a re-rank will destroy, stated **before** it is paid for (FR-22 / FR-45(a), story 7.6).

    A new *ranking version* moves ``ranking_version_no``, and ``INPUTS_BY_KIND[KIND_SAMPLING_RUN]``
    is every observable — so **every** open run in the *matter* is invalidated. Until this object
    existed nothing said so: ``_guard_open_run`` is a *write* guard with two callers, both writes,
    so the lawyer met the consequence on her next verdict as a 409, after which
    ``abandon_sampling_run`` audited ``verdicts_kept=`` the count of the hour she had just lost.

    ``verdicts_at_risk`` counts **judged families**, which is what
    :meth:`SamplingRunView.verdicts_recorded` counts and what ``_current_verdicts`` — max-seq per
    family — later audits as ``verdicts_kept``. A row count would be a different number: a lawyer
    who corrected one family wrote two rows and contributes one. Promising fourteen and auditing
    eleven is the nearly-right referent, in the one sentence about what her work cost.
    """

    open_runs: int
    verdicts_at_risk: int

    @property
    def is_free(self) -> bool:
        """True when nothing open stands to be invalidated — the ordinary first ranking."""
        return self.open_runs == 0

    def sentence_fr(self) -> str:
        """The consequence, in the lawyer's language, before anything is written.

        The cause is named through the trigger's own French — *« un nouveau classement »* — never
        the raw stamp key. The 409 a lawyer meets today ends in ``ranking_version_no`` because it
        interpolates the exception's comma-joined keys; the French for it has existed since FR-58.
        """
        if self.is_free:
            return "Aucun tirage en cours : ce classement n'invalide aucun échantillonnage."
        runs = f"{self.open_runs} tirage(s) en cours"
        cause = trigger("ranking_version_no").fr
        if self.verdicts_at_risk == 0:
            return (
                f"{runs} seront invalidés par {cause}. Aucun verdict n'y a encore été porté.")
        return (
            f"{runs} seront invalidés par {cause}, avec {self.verdicts_at_risk} verdict(s) déjà "
            "portés. Les tirages invalidés doivent être abandonnés et refaits.")


def derive_run_state(*, status: str, stamped: bool, changed: Sequence[str]) -> str:
    """The state the surface renders, derived — never stored.

    An **open** run whose inputs moved is ``invalidated``: the population it froze is no longer the
    *matter*'s discarded set, so its verdicts have stopped answering the question they were given
    (FR-22). An open run with **no stamp at all** is invalidated too, and for the same reason 4.13's
    :class:`~apx.core.app.read.freshness.BoundReading` refuses an unstamped bound: an absence of
    evidence is not evidence of validity.

    A **completed** or **abandoned** run keeps its stored status. A completed run can still go
    stale — that is its *bound*'s freshness, judged by 4.13 and refused at export — but it is not
    "invalidated in flight", because it is not in flight.
    """
    if status not in STATUSES:
        raise ValueError(f"unknown sampling run status: {status!r}")
    if status == STATUS_OPEN and (not stamped or changed):
        return STATE_INVALIDATED
    return status
