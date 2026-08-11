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

from apx.core.domain.confidence import RecordedBound, estimator_is_proven
from apx.core.domain.freshness import Freshness, FreshnessStamp, assess_freshness
from apx.core.domain.sampling import (
    KIND_BOUND,
    KIND_CENSUS,
    KIND_COUNTS_ONLY,
    census_statement_fr,
    counts_only_statement_fr,
    is_census,
)
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
    def kind(self) -> str:
        """Which register this bound speaks in — ``census``, ``counts_only`` or ``bound``.

        Decided **once**, here, and read by every consumer: the sentence, the HTTP payload and the
        export. A payload that carried a prevalence while the sentence said *"all of them were
        read"* would let any client render the residual-risk figure FR-22 forbids over a fully
        reviewed population — the registers would be disjoint only in the one string that happened
        to branch.

        The order matters and mirrors :func:`~apx.core.domain.sampling.estimate_for_run`:

        1. a **census** first, because it survives an unproven estimator. It makes no statistical
           claim at all — every unit was read, and the count is a fact about what the lawyer saw.
           Withholding it because the *estimator* is unproven would suppress a true statement on the
           grounds that a different, absent one is untrustworthy;
        2. **counts only** when the simulation gate has not passed (Story 5.3, FR-23). This read
           path has to consult the flag too: a register that existed only where the estimate is
           BORN would be bypassed by every reader — which is the defect the Story 5.2 review found
           three times over, each time on a read path that had its own opinion."""
        b = self.bound.bound
        if is_census(population=b.population, sample_size=b.sample_size):
            return KIND_CENSUS
        return KIND_BOUND if estimator_is_proven() else KIND_COUNTS_ONLY

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
        tail = f"revue du {self.bound.reviewed_at.date().isoformat()} — {self.status_fr}."
        # FR-22: a bound resting on a later draw over the same population states how many runs came
        # first. The sentence travels alone, so the multiplicity fact travels inside it or not at
        # all — and abandon-and-redraw is what it is watching for.
        if self.bound.run_ordinal > 1:
            tail = f"tirage n° {self.bound.run_ordinal} sur cette population — {tail}"
        pieces = self.bound.piece_count if self.bound.piece_count is not None else b.population
        # A CENSUS is a categorically different statement and gets a categorically different
        # sentence — an exact count, never a percentage (Story 5.2, OQ-4 input 2). "au plus 0,0 %
        # est pertinent" over a population that was read in full is a false claim of residual risk,
        # and it is the one this sentence would otherwise make. The two registers never mix.
        if self.kind == KIND_CENSUS:
            sentence = census_statement_fr(
                relevant_units=b.relevant_in_sample,
                relevant_pieces=self.bound.relevant_pieces,
                unit_fr=self.bound.unit_fr, piece_count=pieces)
            # NOT str.capitalize(): it lowercases everything after the first character, which would
            # quietly mangle any proper noun or unit the sentence grows later.
            return sentence[:1].upper() + sentence[1:] + f" — {tail}"
        if self.kind == KIND_COUNTS_ONLY:
            # FR-23's failure path: counts, and nothing derived from them. The reason travels with
            # them, because a number withheld without a reason reads as one the product forgot.
            sentence = counts_only_statement_fr(
                sample_units=b.sample_size, population_units=b.population,
                relevant_units=b.relevant_in_sample, unit_fr=self.bound.unit_fr,
                piece_count=self.bound.piece_count)
            return sentence[:1].upper() + sentence[1:] + f" — {tail}"
        # The denominator is labelled with the unit it was COMPUTED over (Story 5.1): a sampling
        # run draws near-duplicate families, and calling a family count "pièces" would make the
        # sentence false about its own denominator. The pièce count is stated beside it, never
        # substituted into it.
        held = (f" ({self.bound.piece_count} pièces)"
                if self.bound.piece_count is not None else "")
        # The worst case in *pièces*, stated so the reader does not do the rescale herself: 6 of
        # 120 families is 5 %, and 5 % of 1 400 pièces is 70 — which is wrong, and wrong in the
        # flattering direction, because the relevant families may be the largest ones. Absent when
        # the run never froze its family sizes; never guessed (AD-19).
        worst = (f", soit au plus {self.bound.count_upper_pieces} pièces au pire"
                 if self.bound.count_upper_pieces is not None else "")
        return (
            f"Avec une confiance de {b.confidence:.0%}, au plus {b.count_upper} des "
            f"{b.population} {self.bound.unit_fr}{held} étaient pertinentes "
            f"(prévalence ≤ {b.prevalence_upper:.1%}){worst} — {tail}"
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
