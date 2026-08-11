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

from dataclasses import dataclass

from apx.core.domain.freshness import trigger
from apx.core.domain.sampling import (
    STATE_INVALIDATED,
    STATUS_COMPLETED,
    STATUS_OPEN,
    Estimate,
    SamplingRunView,
    census_statement_fr,
    derive_run_state,
)
from apx.core.ports.sampling import SamplingRunStore


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
    """

    run: SamplingRunView
    stamped: bool
    changed: tuple[str, ...]

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
    def census_fr(self) -> str | None:
        """The categorically stronger statement a **census** makes, or ``None`` when the run was a
        sample (FR-22). A census estimates nothing, so it never carries a percentage — the surface
        must not render it beside a bound as though it were one."""
        estimate = self.run.estimate
        if estimate is None or not estimate.is_census:
            return None
        return census_statement_fr(
            relevant_units=estimate.relevant_families,
            relevant_pieces=estimate.relevant_pieces,
            unit_fr="familles de quasi-doublons écartées",
            piece_count=estimate.population_pieces)

    @property
    def estimate(self) -> Estimate | None:
        """What the run supports, or ``None`` while it supports nothing — the object Story 5.4 will
        render as a sentence. Read straight off the run: one owning derivation (AD-37)."""
        return self.run.estimate

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
    run_id: str | None = None,
) -> SamplingRunReading | None:
    """The *matter*'s current run (or a named one) with the verdict on its frozen population.

    ``None`` when out of scope, absent, or when no run exists — the surface renders "no draw yet" as
    its own state, never as an empty run pretending to be a result (the Story 4.10 lesson: a failed
    read is not a verified absence)."""
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
    return SamplingRunReading(run=run, stamped=stamped, changed=changed)


def read_sampling_runs(
    *, tenant: str, matter: str, scopes: set[str], store: SamplingRunStore,
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
    readings: list[SamplingRunReading] = []
    for run in runs:
        freshness = store.read_run_freshness(
            tenant=tenant, matter=matter, scopes=scopes, run_id=run.run_id)
        if freshness is None:
            return None  # unreadable mid-read — never assess a run against nothing
        stamped, changed = freshness
        readings.append(SamplingRunReading(run=run, stamped=stamped, changed=changed))
    return tuple(readings)
