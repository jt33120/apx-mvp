"""Read the freshness of a *matter*'s derived artefacts (Story 4.13) — through the ONE read entry
point (AD-14).

Three thin seams over :class:`~apx.core.ports.freshness.FreshnessReader`: the assessments, the
derived *worklist* built from them, and the current *confidence bound* with its own assessment.

**The rule lives here, in the core.** The port reports observables only; comparing a recorded stamp
with the current one is :func:`~apx.core.domain.freshness.assess_freshness`, a pure Domain function.
A store that could answer *"is it stale?"* would hold the rule adapter-side, where no structural
check reaches it (AD-4).

Every seam is a pure read: nothing here writes, nothing here queues a recomputation, and nothing
here resolves staleness — FR-58 resolves it only by an explicit user-initiated act that produces a
**new** artefact. Fail-closed like every other read: an empty scope set reads nothing (AD-12), and
out-of-scope is indistinguishable from absent (FR-14). The API depends on this module, never on the
store adapter (AD-4).
"""

from __future__ import annotations

from dataclasses import dataclass

from apx.core.domain.confidence import RecordedBound
from apx.core.domain.freshness import Freshness, FreshnessStamp, assess_freshness
from apx.core.domain.worklist import WorklistLine, worklist_lines
from apx.core.ports.freshness import FreshnessReader


@dataclass(frozen=True)
class BoundReading:
    """The *matter*'s current *confidence bound* and the verdict on it (FR-58).

    ``freshness`` is ``None`` only when the bound carries no stamp at all — a bound recorded before
    this story existed. That is **not** freshness: the surface must say the bound's inputs cannot be
    verified, never that they are unchanged, and the export refuses it for the same reason it
    refuses a stale one. An absence of evidence is not evidence of freshness.
    """

    bound: RecordedBound
    freshness: Freshness | None

    @property
    def exportable_as_current(self) -> bool:
        """FR-58: a stale bound cannot be exported as current. Neither can an unverifiable one."""
        return self.freshness is not None and self.freshness.fresh

    @property
    def status_fr(self) -> str:
        """The bound's freshness in one French phrase — never absent, never optimistic."""
        if self.freshness is None:
            return "fraîcheur invérifiable : cette borne n'a pas enregistré ses entrées"
        return self.freshness.reason()

    @property
    def copy_text(self) -> str:
        """The sentence the surface copies to the clipboard — **composed here, on the server**.

        FR-58: a stale bound *"cannot be copied as text without its staleness in the copied
        string"*. That is only structurally true if the client copies a string it did not compose:
        every path through this property appends :attr:`status_fr`, so there is no branch that
        produces the number without its freshness. A client that assembled its own sentence from
        the numeric fields could omit it — which is why the surface copies this and nothing else.
        """
        b = self.bound.bound
        return (
            f"Avec une confiance de {b.confidence:.0%}, au plus {b.count_upper} des "
            f"{b.population} pièces écartées étaient pertinentes "
            f"(prévalence ≤ {b.prevalence_upper:.1%}) — "
            f"revue du {self.bound.reviewed_at.date().isoformat()} — {self.status_fr}."
        )


def read_freshness(
    *, tenant: str, matter: str, scopes: set[str], reader: FreshnessReader,
) -> tuple[Freshness, ...] | None:
    """The verdict on every stamped derived artefact of the *matter*, oldest first.

    ``()`` means the *matter* was read and has produced no stamped artefact yet; ``None`` means out
    of scope or absent — the surface must not render the two the same way (the Story 4.10 lesson: a
    failed read is not a verified absence).

    Each artefact is compared against **its own version's** inputs: the line is version-bound, so a
    placement over ranking version 2 is assessed against version 2's placement, never against the
    latest version's. Getting this wrong is not symmetric — it can read a line whose own cut moved
    as *fresh*, which is the catastrophic direction (AD-23). The version comes from the artefact
    itself (the reader resolves it); a bound has none of its own, so it falls back to the *matter*
    maximum its stamp recorded, which is what it was drawn over.

    The current stamp is computed **once per distinct version**, not once per artefact: the
    observables are a full pass over the *matter*'s pièces, and a page showing a ranking, its line
    and a bound would otherwise pay for three identical passes.
    """
    if not scopes:
        return None  # fail closed — no scope reads nothing (AD-12)
    stamps = reader.read_artefact_stamps(tenant=tenant, matter=matter, scopes=scopes)
    if stamps is None:
        return None
    by_version: dict[int | None, FreshnessStamp] = {}
    assessments: list[Freshness] = []
    for kind, artefact_id, own_version_no, superseded, recorded in stamps:
        version_no = own_version_no if own_version_no is not None else recorded.ranking_version_no
        if version_no not in by_version:
            current = reader.current_stamp(
                tenant=tenant, matter=matter, scopes=scopes, version_no=version_no)
            if current is None:
                return None  # unreadable mid-read — never assess against nothing
            by_version[version_no] = current
        assessments.append(assess_freshness(
            kind=kind, artefact_id=artefact_id, recorded=recorded,
            current=by_version[version_no], superseded=superseded))
    return tuple(assessments)


def read_worklist(
    *, tenant: str, matter: str, scopes: set[str], reader: FreshnessReader,
) -> tuple[WorklistLine, ...] | None:
    """The *matter*'s worklist — one line per stale artefact, naming the inputs that moved and
    **offering** the recomputation (FR-58). Derived from the assessments, stored nowhere.

    Reading it writes nothing and starts nothing. ``()`` = read, nothing stale; ``None`` = not
    read."""
    assessments = read_freshness(tenant=tenant, matter=matter, scopes=scopes, reader=reader)
    if assessments is None:
        return None
    return worklist_lines(assessments)


def read_bound(
    *, tenant: str, matter: str, scopes: set[str], reader: FreshnessReader,
) -> BoundReading | None:
    """The current *confidence bound* and the verdict on it. ``None`` when out of scope, absent, or
    when no bound has been recorded — the surface renders "no bound yet" as its own state."""
    if not scopes:
        return None
    bound = reader.read_current_bound(tenant=tenant, matter=matter, scopes=scopes)
    if bound is None:
        return None
    assessments = read_freshness(tenant=tenant, matter=matter, scopes=scopes, reader=reader)
    if assessments is None:
        return None
    verdict = next(
        (a for a in assessments if a.artefact_id == bound.artefact_id), None)
    return BoundReading(bound=bound, freshness=verdict)
