"""Read a *sampling run* and its validity (Story 5.1, FR-22) — through the ONE read entry point
(AD-14).

Two thin seams over :class:`~apx.core.ports.sampling.SamplingRunStore`: the current (or a named)
run with the verdict on its frozen population, and the *matter*'s run history.

**The rule lives here, in the core.** The port reports observables — *is it stamped, and which
inputs moved* — and :func:`~apx.core.domain.sampling.derive_run_state` decides what that means. A
store that could answer *"is this run still valid?"* would hold the rule adapter-side, where no
structural check reaches it (AD-4); it is the same argument as Story 4.13's freshness port.

Every seam is a pure read: nothing here writes, nothing here abandons a run, and nothing here
resolves an invalidation — FR-22 resolves it only by an explicit human act that produces a **new**
draw. Fail-closed like every other read: an empty scope set reads nothing (AD-12), and out-of-scope
is indistinguishable from absent (FR-14).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from apx.core.domain.config import coerce
from apx.core.domain.freshness import trigger
from apx.core.domain.sampling import (
    STATE_INVALIDATED,
    STATUS_COMPLETED,
    STATUS_OPEN,
    Estimate,
    RerankCost,
    SamplingRunView,
    derive_run_state,
)
from apx.core.domain.statement import (
    UNFIT_SHARE_KEY,
    StatementInputs,
    Unfitness,
    statement_fr,
    unfitness,
    unfitness_statement_fr,
)
from apx.core.ports.sampling import SamplingRunStore

# What a *sampling run* counts. A run draws near-duplicate FAMILIES (FR-38): forty copies of one
# email are one draw, not forty. Naming the unit once, here, is why the sentence cannot end up
# calling a family count "pièces" — the Story 5.1 denominator defect.
_RUN_UNIT_FR = "familles de quasi-doublons écartées"


@dataclass(frozen=True)
class SamplingRunReading:
    """A *sampling run* and the verdict on the population it froze (FR-22).

    ``changed`` names the inputs that moved since the draw, so the surface can say *which* — a bare
    "invalidated" would leave the lawyer unable to tell an import from a line move, and the two call
    for different judgements about whether she has just lost an hour.

    ``stamped`` is False only for a run that carries no freshness stamp at all, which this story
    makes impossible (the stamp is written inside the starting transaction). It is still modelled,
    and still counts as invalidated, because an absence of evidence is not evidence of validity —
    the same rule 4.13 applies to an unstamped bound.

    ``unfit_relevant_share`` is the *tenant*'s configured FR-23 threshold (Story 5.4), carried so
    the finding is derived once and read identically by every surface. No default: a reading that
    answered "fit" because nobody supplied a threshold would be a verdict nobody computed.
    """

    run: SamplingRunView
    stamped: bool
    changed: tuple[str, ...]
    unfit_relevant_share: float

    @property
    def state(self) -> str:
        """``open`` | ``invalidated`` | ``completed`` | ``abandoned`` — derived, never stored."""
        return derive_run_state(
            status=self.run.status, stamped=self.stamped, changed=self.changed)

    @property
    def invalidated_in_flight(self) -> bool:
        """FR-22's failure path: the population moved while the run was open. The surface must say
        this the moment it is true, not when the run is completed — the whole point is that the
        lawyer stops before spending another hour."""
        return self.state == STATE_INVALIDATED

    @property
    def changed_fr(self) -> tuple[str, ...]:
        """The French phrases for the inputs that moved, in the trigger list's order."""
        return tuple(trigger(k).fr for k in self.changed)

    @property
    def state_fr(self) -> str:
        """One French line for the run's state — never absent, never optimistic."""
        if self.invalidated_in_flight:
            if not self.changed:
                return "tirage invalidé : ses entrées ne peuvent pas être vérifiées"
            return "tirage invalidé : " + ", ".join(self.changed_fr)
        if self.run.status == STATUS_COMPLETED:
            return "tirage terminé"
        if self.run.status != STATUS_OPEN:
            return "tirage abandonné ; ses verdicts restent consultables"
        return (
            f"tirage en cours : {self.run.verdicts_recorded} verdicts sur "
            f"{self.run.sample_size} familles")

    @property
    def statement_fr(self) -> str | None:
        """This run's own reading of what it found, in whichever of the four registers applies —
        or ``None`` while the run supports nothing (Story 5.4, FR-23).

        Composed by the **same** Domain function as the *matter*'s constat
        (:func:`~apx.core.domain.statement.statement_fr`), so the two surfaces can never word one
        draw two ways. It replaced a census-only string: one arm for one register left the other
        three to be assembled by whichever renderer got there first, which is how the Story 5.2
        review found three readers each with its own opinion.

        **This sentence is not the copyable constat**, and the surface must not offer it as one.
        The *matter*'s current bound is what a lawyer quotes, and only that reading holds FR-58's
        freshness verdict; a run screen offering a second copyable string would put the same number
        on a clipboard twice with two different sets of qualifications. What travels here instead
        is :attr:`run_qualification_fr` — the run's own measured observables, never a freshness
        claim it did not compute.
        """
        estimate = self.run.estimate
        if estimate is None:
            return None
        return statement_fr(StatementInputs(
            kind=estimate.kind,
            unit_fr=_RUN_UNIT_FR,
            population_units=estimate.population_families,
            sample_units=estimate.sample_families,
            relevant_units=estimate.relevant_families,
            confidence=estimate.confidence,
            piece_count=estimate.population_pieces,
            count_upper_units=estimate.count_upper_families,
            prevalence_upper=estimate.prevalence_upper,
            count_upper_pieces=estimate.count_upper_pieces,
            relevant_pieces=estimate.relevant_pieces,
            scope=self.run.scope,
            run_ordinal=estimate.run_ordinal,
            freshness_fr=self.run_qualification_fr))

    @property
    def run_qualification_fr(self) -> str:
        """What qualifies **this run's own** reading — a report of measured observables, never a
        freshness verdict.

        Story 4.13 owns the verdict (fresh / stale / superseded) and it is computed over the
        *matter*'s artefacts, including ``superseded``, which a run reading cannot see. Restating
        that verdict here would be a second staleness rule for one fact, and the two would
        eventually disagree — the defect this epic exists to prevent. So this reports what the port
        actually measured: whether the run carries a stamp at all, and which of its inputs moved.
        """
        if not self.stamped:
            return "fraîcheur invérifiable : ce tirage n'a pas enregistré ses entrées"
        if self.changed:
            return ("les entrées de ce tirage ont changé depuis : " + ", ".join(self.changed_fr))
        return "entrées inchangées depuis le tirage"

    @property
    def estimate(self) -> Estimate | None:
        """What the run supports, or ``None`` while it supports nothing — the object Story 5.4 will
        render as a sentence. Read straight off the run: one owning derivation (AD-37)."""
        return self.run.estimate

    @property
    def unfitness(self) -> Unfitness | None:
        """FR-23's seventh consequence: where K approaches N the finding is that the *ranking
        version* carries no signal on this *matter*, not that the line is misplaced.

        **The denominator is the SAMPLE, and only a completed run has one.** CONFIRMED by five
        independent lenses, and reproduced before the review: this divided by
        ``verdicts_recorded`` — the tally so far — so a 200-family draw whose first verdict came
        back relevant declared the whole *ranking version* unfit at 1/1, and the declaration then
        said *"sur les 1 familles tirées au hasard"* about a draw of two hundred. Two defects in
        one expression: a threshold applied to a number that is not the sample, and a sentence
        stating a false fact about the draw it names.

        Worse, it disagreed with the *matter*'s own constat, which divides by
        ``bound.sample_size``: the same run read **unfit** on one surface and **fit** on the other,
        mid-flight. One rule needs one denominator — this project's recurring defect, in the code
        this story added to state a finding about it.

        Register-INDEPENDENT still, and deliberately: a census reaches the finding (there K/N is
        the exact share of the discarded set that is relevant) and so does a counts-only run (the
        verdicts were observed whether or not a bound may be stated). Gating it on the bound
        register would let an unproven estimator hide a ranking that is not ranking anything.
        """
        if self.run.status != STATUS_COMPLETED:
            return None  # an in-flight tally is not the sample; FR-23 speaks about the sample
        return unfitness(
            relevant_units=self.run.relevant_found or 0, sample_units=self.run.sample_size,
            threshold=self.unfit_relevant_share)

    @property
    def unfitness_fr(self) -> str | None:
        """The declaration in words, or ``None`` when there is none to make. The run always knows
        its own *ranking version* (the freeze records it, NOT NULL), so unlike the matter-level
        constat there is no version-less case here."""
        finding = self.unfitness
        estimate = self.estimate
        if finding is None or estimate is None:
            return None
        return unfitness_statement_fr(
            finding, version_no=self.run.version_no, unit_fr=_RUN_UNIT_FR, kind=estimate.kind)

    @property
    def repeated_draw_fr(self) -> str | None:
        """The multiple-comparisons fact, in French, or ``None`` for a first draw (OQ-4 input 3).

        FR-22: a second run over the same population *"is presented alongside the first rather than
        replacing it"*, and the sentence travels alone — so the ordinal travels with it. The count
        includes abandoned runs, because abandon-and-redraw is the route this is defending."""
        estimate = self.estimate
        if estimate is None or not estimate.repeated:
            return None
        return (
            f"tirage n° {estimate.run_ordinal} sur cette même population : les tirages ne sont "
            "jamais fusionnés, et celui-ci ne remplace pas les précédents")


def read_sampling_run(
    *, tenant: str, matter: str, scopes: set[str], store: SamplingRunStore,
    config_get: Callable[[str], object], run_id: str | None = None,
) -> SamplingRunReading | None:
    """The *matter*'s current run (or a named one) with the verdict on its frozen population.

    ``None`` when out of scope, absent, or when no run exists — the surface renders "no draw yet" as
    its own state, never as an empty run pretending to be a result (the Story 4.10 lesson: a failed
    read is not a verified absence).

    ``config_get`` resolves FR-23's unfitness threshold as *configuration-as-data* (AD-24), the same
    shape the semantic read seam uses for its similarity floor."""
    if not scopes:
        return None  # fail closed — no scope reads nothing (AD-12)
    run = store.read_sampling_run(tenant=tenant, matter=matter, scopes=scopes, run_id=run_id)
    if run is None:
        return None
    freshness = store.read_run_freshness(
        tenant=tenant, matter=matter, scopes=scopes, run_id=run.run_id)
    if freshness is None:
        return None  # unreadable mid-read — never assess a run against nothing
    stamped, changed = freshness
    return SamplingRunReading(
        run=run, stamped=stamped, changed=changed,
        unfit_relevant_share=_unfit_share(config_get))


def _unfit_share(config_get: Callable[[str], object]) -> float:
    """The *tenant*'s FR-23 threshold, ``coerce``d — so a stray type or an out-of-range share fails
    loudly rather than silently disabling the declaration."""
    return float(coerce(UNFIT_SHARE_KEY, config_get(UNFIT_SHARE_KEY)))


def read_sampling_runs(
    *, tenant: str, matter: str, scopes: set[str], store: SamplingRunStore,
    config_get: Callable[[str], object],
) -> tuple[SamplingRunReading, ...] | None:
    """The *matter*'s runs, newest first — the history a *bâtonnier* reads, each with the verdict on
    the population it froze. ``()`` means readable with no run yet; ``None`` means not read.

    The freshness of **every** run is read, including the closed ones. It would be cheaper to skip
    them — :func:`~apx.core.domain.sampling.derive_run_state` ignores the observables unless the run
    is open — but then the reading would carry ``stamped``/``changed`` values that were never
    measured, and a later reader of this dataclass would have no way to tell a measured () from an
    unmeasured one. That is the nearly-right referent this epic exists to stop making."""
    if not scopes:
        return None
    runs = store.list_sampling_runs(tenant=tenant, matter=matter, scopes=scopes)
    if runs is None:
        return None
    share = _unfit_share(config_get)
    readings: list[SamplingRunReading] = []
    for run in runs:
        freshness = store.read_run_freshness(
            tenant=tenant, matter=matter, scopes=scopes, run_id=run.run_id)
        if freshness is None:
            return None  # unreadable mid-read — never assess a run against nothing
        stamped, changed = freshness
        readings.append(SamplingRunReading(
            run=run, stamped=stamped, changed=changed, unfit_relevant_share=share))
    return tuple(readings)


def rerank_cost(
    *, tenant: str, matter: str, scopes: set[str], store: SamplingRunStore,
    config_get: Callable[[str], object],
) -> RerankCost | None:
    """What a re-rank of this *matter* would destroy — read **before** the act, so the lawyer can
    refuse it (FR-22 / FR-45(a), story 7.6).

    Three things this deliberately does not do, each of which falls to the flattering side.

    It does not count the **stored** status. A run stored ``open`` may already be invalidated by an
    earlier act, and :func:`~apx.core.domain.sampling.derive_run_state` turns that pair into
    ``invalidated``. Counting stored status would promise *"you will invalidate three runs"* when
    two were already dead — and that count is the load-bearing number in a confirmation the server
    then re-checks.

    It does not gate on ``invalidated_in_flight``. Before the re-rank the run is genuinely **fresh**
    — that is the whole point — so a warning gated on the existing invalidation flag would never
    fire, and would pass every test written in the one configuration where it can be observed:
    afterwards. This is a *prediction*, a different computation from the retrospective comparison
    the rest of this module performs.

    And it does not turn ``None`` into a zero cost. ``None`` means **not read** — empty scopes, a
    walled or absent *matter*, a freshness read that failed mid-sweep. Every one of those is
    "nothing at risk, proceed silently" if it is coerced to zero. Only ``()`` means read-and-none.
    """
    readings = read_sampling_runs(
        tenant=tenant, matter=matter, scopes=scopes, store=store, config_get=config_get)
    if readings is None:
        return None
    at_risk = [r for r in readings if r.state == STATUS_OPEN]
    return RerankCost(
        open_runs=len(at_risk),
        # judged FAMILIES — the same arithmetic ``abandon_sampling_run`` later audits as
        # ``verdicts_kept`` (max-seq per family), never the row count
        verdicts_at_risk=sum(r.run.verdicts_recorded for r in at_risk))
