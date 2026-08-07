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

from apx.core.domain.confidence import PrevalenceBound, prevalence_upper_bound

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


def census_statement_fr(*, relevant_found: int, piece_count: int) -> str:
    """What a census says, in French. Never a percentage: a census estimates nothing."""
    if relevant_found == 0:
        return (
            f"recensement : les {piece_count} pièces écartées ont toutes été examinées ; "
            "aucune n'était pertinente")
    return (
        f"recensement : les {piece_count} pièces écartées ont toutes été examinées ; "
        f"{relevant_found} famille(s) se sont révélées pertinentes")


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
    is_census: bool
    seed: int
    status: str
    started_by: str
    started_at: datetime
    completed_at: datetime | None
    relevant_found: int | None
    count_upper: int | None
    prevalence_upper: float | None
    drawn: tuple[DrawnFamily, ...]

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
