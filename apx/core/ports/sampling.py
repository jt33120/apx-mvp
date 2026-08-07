"""The *sampling run* port (Story 5.1, FR-22 / AD-37 / AD-22 / AD-4 / AD-13).

The one boundary the sampling acts persist across. The store adapter implements it — it resolves
the *ranking version*, derives the discarded set from *(the order, **the line**, the pins)*, groups
it into near-duplicate families, draws, freezes the identifiers, writes the freshness stamp and
appends the audit entry, all inside one transaction (AD-22/AD-37). The ``core/app`` seams depend
only on this Protocol (AD-4).

**The store never answers "is this run still valid?"** as an opinion: it reports the run and the
observables, and :func:`~apx.core.domain.sampling.derive_run_state` decides. A store that held the
rule would put it adapter-side, where no structural check reaches it — the same argument as the
freshness port (Story 4.13).

No method takes an identifier without a *tenant* and ``scopes``, and ``scopes`` is carried into the
query as a **pre-filter**, never a post-filter over rows already fetched (AD-13). Out of scope and
absent return the same ``None``, so a caller cannot tell one from the other (FR-14).
"""

from __future__ import annotations

from typing import Protocol

from apx.core.domain.sampling import SamplingRunView, Sizing


class InvalidatedRun(Exception):
    """Raised when a verdict or a completion is attempted on a run whose frozen population has
    moved (FR-22). Refusing is the strongest form of *"tells the user immediately"*: a verdict
    recorded against a population that no longer exists is worse than no verdict, because it looks
    like evidence. The run must be abandoned and redrawn; its existing verdicts stay readable."""


class RunAlreadyClosed(Exception):
    """Raised when a verdict is attempted on a run that is completed or abandoned. A closed run's
    verdicts are the record of what was judged, and appending to them later would change the
    population a recorded bound was computed over."""


class SamplingRunStore(Protocol):
    def size_for_target_bound(
        self, *, tenant: str, matter: str, scopes: set[str], target_prevalence: float,
        confidence: float = 0.95, max_size: int | None = None, version_no: int | None = None,
    ) -> Sizing | None:
        """How many families must be drawn to reach ``target_prevalence`` at ``confidence`` over
        the *matter*'s **current** discarded set (FR-22), or the best achievable when the target is
        out of reach.

        ``None`` ONLY when the *matter* is out of scope or absent — the two are indistinguishable
        (FR-14). A *matter* the caller holds but which is not ranked, has no line, or has an empty
        discarded set answers with a :class:`~apx.core.domain.sampling.Sizing` saying *no bound
        applies*: that is a true statement about her own dossier, not a refusal, and it must never
        be rendered as a flattering 0%. A preview: writes nothing and is not audited."""
        ...

    def start_sampling_run(
        self, *, tenant: str, matter: str, actor: str, scopes: set[str],
        sample_size: int | None = None, target_prevalence: float | None = None,
        confidence: float = 0.95, max_size: int | None = None, version_no: int | None = None,
        seed: int | None = None,
    ) -> SamplingRunView | None:
        """Start a run: draw uniformly **without replacement** over the near-duplicate families of
        ``derive_triage_sets(order, line, pins).discarded`` for a named *ranking version*, freeze
        the population by explicit identifier list, stamp it and append one audit entry — one
        transaction (AD-22/AD-37).

        Exactly one of ``sample_size`` / ``target_prevalence`` is given. ``None`` when out of scope,
        absent, not yet ranked, no line placed, or the discarded set is empty (there is nothing to
        audit and no bound applies — never a flattering 0%)."""
        ...

    def record_sampling_verdict(
        self, *, tenant: str, matter: str, actor: str, scopes: set[str], run_id: str,
        family_id: str, relevant: bool,
    ) -> SamplingRunView | None:
        """Append one verdict on one drawn family, attributed and timestamped (FR-24 — append-only,
        a correction is a new entry). Raises :class:`InvalidatedRun` when the frozen population has
        moved and :class:`RunAlreadyClosed` when the run is completed or abandoned. ``None`` when
        out of scope, absent, or when ``family_id`` was not drawn by this run."""
        ...

    def complete_sampling_run(
        self, *, tenant: str, matter: str, actor: str, scopes: set[str], run_id: str,
    ) -> SamplingRunView | None:
        """Close the run: tally the verdicts, compute the bound **over the unit drawn** (families),
        and append one audit entry — one transaction (AD-22). Raises :class:`InvalidatedRun` when
        the frozen population has moved, and refuses a run that is not fully judged (an unjudged
        family is not a verdict of "not relevant" — AD-19, nothing imputed). ``None`` when out of
        scope or absent."""
        ...

    def abandon_sampling_run(
        self, *, tenant: str, matter: str, actor: str, scopes: set[str], run_id: str,
    ) -> SamplingRunView | None:
        """Give up an open run, audited. Its drawn identifiers and its verdicts stay readable
        forever (AD-7): *"an hour of my verdicts"* is never destroyed, only marked as no longer
        answering the question. ``None`` when out of scope or absent."""
        ...

    def read_sampling_run(
        self, *, tenant: str, matter: str, scopes: set[str], run_id: str | None = None,
    ) -> SamplingRunView | None:
        """One run with its frozen draw and current verdicts — the *matter*'s most recent when
        ``run_id`` is ``None``. ``None`` when out of scope, absent, or no run exists. Not audited
        (a read)."""
        ...

    def read_run_freshness(
        self, *, tenant: str, matter: str, scopes: set[str], run_id: str
    ) -> tuple[bool, tuple[str, ...]] | None:
        """``(stamped, the trigger keys whose observable moved)`` for one run — the **observables**
        FR-22's invalidated-in-flight verdict is derived from, never the verdict itself. The Domain
        decides (:func:`~apx.core.domain.sampling.derive_run_state`); a store that answered *"is it
        invalidated?"* would hold the rule adapter-side, where no structural check reaches it
        (AD-4). ``None`` when out of scope or absent."""
        ...

    def list_sampling_runs(
        self, *, tenant: str, matter: str, scopes: set[str]
    ) -> tuple[SamplingRunView, ...] | None:
        """Every run of the *matter*, newest first. ``()`` means readable with no run yet; ``None``
        means out of scope or absent — the surface must not render the two the same way."""
        ...
