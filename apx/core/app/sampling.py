"""The *sampling run* acts (Story 5.1, FR-22) — start, judge, complete, abandon.

Thin Application-layer seams over the :class:`SamplingRunStore` port: the API depends on **these**
functions, never on the store adapter (AD-4). The store owns the guarantees — it derives the
population from *(the order, **the line**, the pins)*, groups it into near-duplicate families,
draws without replacement, freezes the identifiers, writes the freshness stamp and appends the
audit entry, all in one transaction (AD-22/AD-37).

**Nothing here resolves invalidation and nothing here retries it.** FR-22 says a run whose
population moved *"tells the user immediately"*; the store raises
:class:`~apx.core.ports.sampling.InvalidatedRun` and the seam lets it through, because silently
carrying on is precisely the *"letting the verdicts silently become worthless"* the requirement
forbids. The remedy is a human act: abandon and redraw.
"""

from __future__ import annotations

from apx.core.domain.sampling import SamplingRunView, Sizing
from apx.core.ports.sampling import SamplingRunStore


def size_for_target_bound(
    store: SamplingRunStore, *, tenant: str, matter: str, scopes: set[str],
    target_prevalence: float, confidence: float = 0.95, max_size: int | None = None,
    version_no: int | None = None,
) -> Sizing | None:
    """How many near-duplicate families must be drawn to reach ``target_prevalence`` at
    ``confidence`` — or, when the target is out of reach, the best achievable and the fact that it
    is out of reach (FR-22). A preview: writes nothing, audits nothing.

    ``confidence`` and ``target_prevalence`` are validated here, so a preview refuses the same
    inputs a run would — a sizing that answered where the draw would refuse is a nearly-right
    referent of its own.

    ``None`` only when the *matter* is out of scope or absent (non-disclosing, FR-14). A held
    *matter* that is not ranked, has no line, or has an empty discarded set answers *no bound
    applies* — a true statement about her own dossier, never a flattering 0%."""
    if not 0 < confidence < 1:
        raise ValueError(f"confidence must be in (0, 1): {confidence}")
    if not 0.0 <= target_prevalence < 1.0:
        raise ValueError(f"target prevalence must be in [0, 1): {target_prevalence}")
    if not scopes:
        return None  # fail closed — no scope reads nothing (AD-12)
    return store.size_for_target_bound(
        tenant=tenant, matter=matter, scopes=scopes, target_prevalence=target_prevalence,
        confidence=confidence, max_size=max_size, version_no=version_no)


def start_sampling_run(
    store: SamplingRunStore, *, tenant: str, matter: str, actor: str, scopes: set[str],
    sample_size: int | None = None, target_prevalence: float | None = None,
    confidence: float = 0.95, max_size: int | None = None, version_no: int | None = None,
) -> SamplingRunView | None:
    """Start a run over the *matter*'s **derived** discarded set (FR-22).

    Exactly one of ``sample_size`` / ``target_prevalence``. ``None`` when out of scope, absent, not
    ranked, no line placed, or the discarded set is empty — the last is not an error: with nothing
    discarded there is nothing to audit and **no bound applies**, which the surface must say rather
    than showing a flattering 0%.

    The seed is chosen by the store and recorded, but the run's population is frozen by the explicit
    identifier list, never by the seed (FR-22).

    A ``sample_size`` below 1 is REFUSED rather than clamped to 1: a run that drew nothing would
    produce the honest-but-useless bound *"the whole pile could be relevant"* while looking on the
    surface like a review that happened.

    ``confidence`` is validated **here, where the run is born** — not where the bound is computed.
    An out-of-range confidence frozen onto a run makes that run permanently uncompletable: an hour
    of verdicts against a draw that can never produce a number, refused at the last step with a
    message about arithmetic. The refusal has to happen before the lawyer starts reading."""
    if sample_size is not None and sample_size < 1:
        raise ValueError(f"a draw must take at least one family: {sample_size}")
    if not 0 < confidence < 1:
        raise ValueError(f"confidence must be in (0, 1): {confidence}")
    if not scopes:
        return None
    return store.start_sampling_run(
        tenant=tenant, matter=matter, actor=actor, scopes=scopes, sample_size=sample_size,
        target_prevalence=target_prevalence, confidence=confidence, max_size=max_size,
        version_no=version_no)


def record_sampling_verdict(
    store: SamplingRunStore, *, tenant: str, matter: str, actor: str, scopes: set[str],
    run_id: str, family_id: str, relevant: bool,
) -> SamplingRunView | None:
    """Record one verdict on one drawn family — append-only, attributed, audited (FR-22/FR-24).

    A verdict is on the **family**, given through its proxy *pièce*: that is what a near-duplicate
    family is, and it is why forty copies of one email are one draw rather than forty.

    Raises :class:`~apx.core.ports.sampling.InvalidatedRun` when the frozen population has moved and
    :class:`~apx.core.ports.sampling.RunAlreadyClosed` when the run is completed or abandoned.
    ``None`` when out of scope, absent, or the family was not drawn by this run."""
    if not scopes:
        return None
    return store.record_sampling_verdict(
        tenant=tenant, matter=matter, actor=actor, scopes=scopes, run_id=run_id,
        family_id=family_id, relevant=relevant)


def complete_sampling_run(
    store: SamplingRunStore, *, tenant: str, matter: str, actor: str, scopes: set[str],
    run_id: str,
) -> SamplingRunView | None:
    """Close a fully-judged run: tally, bound, audit — atomically (AD-22/FR-53).

    The store refuses a run that is not fully judged: an unjudged family is not a verdict of "not
    relevant" (AD-19 — nothing is imputed), and treating it as one would make every bound look
    better than the evidence supports. ``None`` when out of scope or absent."""
    if not scopes:
        return None
    return store.complete_sampling_run(
        tenant=tenant, matter=matter, actor=actor, scopes=scopes, run_id=run_id)


def abandon_sampling_run(
    store: SamplingRunStore, *, tenant: str, matter: str, actor: str, scopes: set[str],
    run_id: str,
) -> SamplingRunView | None:
    """Give up an open run, audited. Its draw and every verdict stay readable forever (AD-7) — *"an
    hour of my verdicts"* is never destroyed, only marked as no longer answering the question.
    ``None`` when out of scope or absent."""
    if not scopes:
        return None
    return store.abandon_sampling_run(
        tenant=tenant, matter=matter, actor=actor, scopes=scopes, run_id=run_id)
