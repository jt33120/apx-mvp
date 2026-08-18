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

from collections.abc import Callable
from dataclasses import dataclass

from apx.core.domain.confidence import RecordedBound, estimator_is_proven
from apx.core.domain.config import coerce
from apx.core.domain.freshness import (
    Freshness,
    FreshnessStamp,
    assess_freshness,
    trigger,
)
from apx.core.domain.sampling import (
    KIND_BOUND,
    KIND_CENSUS,
    KIND_COUNTS_ONLY,
    is_census,
)
from apx.core.domain.statement import (
    UNFIT_SHARE_KEY,
    StatementInputs,
    Unfitness,
    statement_fr,
    unfitness,
    unfitness_statement_fr,
)
from apx.core.domain.worklist import (
    OFFER_REPLACE_LINE,
    WorklistLine,
    unfitness_line,
    worklist_lines,
)
from apx.core.ports.freshness import FreshnessReader


@dataclass(frozen=True)
class BoundReading:
    """The *matter*'s current *confidence bound* and the verdict on it (FR-58).

    ``freshness`` is ``None`` only when the bound carries no stamp at all — a bound recorded before
    this story existed. That is **not** freshness: the surface must say the bound's inputs cannot be
    verified, never that they are unchanged, and the export refuses it for the same reason it
    refuses a stale one. An absence of evidence is not evidence of freshness.

    ``unfit_relevant_share`` is the *tenant*'s configured FR-23 threshold, resolved by
    :func:`read_bound` and carried here so the finding is derived **once**, in the core, and every
    surface reads the same field. It has no default: a reading that answered "fit" because nobody
    supplied a threshold would be a verdict nobody computed.
    """

    bound: RecordedBound
    freshness: Freshness | None
    unfit_relevant_share: float

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
    def statement_inputs(self) -> StatementInputs:
        """Everything the sentence needs, and nothing else (Story 5.4, FR-23).

        Assembled **here**, from the recorded artefact, and handed to the one Domain composer. The
        register-dependent fields are gated by an ALLOW-list on :attr:`kind`, exactly as the HTTP
        payload gates them: gating some of a register's fields is not gating the register, and the
        Story 5.3 review found that half-gating shipping a *pièce* projection beside a payload
        announcing it had no bound to state.
        """
        b = self.bound.bound
        bound_register = self.kind == KIND_BOUND
        return StatementInputs(
            kind=self.kind,
            unit_fr=self.bound.unit_fr,
            population_units=b.population,
            sample_units=b.sample_size,
            relevant_units=b.relevant_in_sample,
            confidence=b.confidence,
            piece_count=self.bound.piece_count,
            count_upper_units=b.count_upper if bound_register else None,
            prevalence_upper=b.prevalence_upper if bound_register else None,
            count_upper_pieces=(
                self.bound.count_upper_pieces if bound_register else None),
            relevant_pieces=(
                self.bound.relevant_pieces if self.kind == KIND_CENSUS else None),
            scope=self.bound.scope,
            run_ordinal=self.bound.run_ordinal,
            reviewed_on=self.bound.reviewed_at.date(),
            freshness_fr=self.status_fr)

    @property
    def copy_text(self) -> str:
        """The sentence the surface copies to the clipboard — **composed on the server**.

        FR-58: a stale bound *"cannot be copied as text without its staleness in the copied
        string"*. FR-23: the sentence carries the *RBAC scope* it was computed under. Both are only
        structurally true if the client copies a string it did not compose — and this property
        delegates to the ONE Domain composer, which has no branch that omits either. A client
        assembling its own sentence from the numeric fields could drop them, which is why the
        surface copies this and nothing else.
        """
        return statement_fr(self.statement_inputs)

    @property
    def unfitness(self) -> Unfitness | None:
        """FR-23's seventh consequence: where K approaches N the finding is that **this ranking
        version carries no signal on this matter**, not that the line is misplaced.

        Derived here, once, from the same counts the sentence states — so the panel, the payload
        and the export cannot disagree about whether the remedy on offer is a line move. The
        threshold is the *tenant*'s configured share, resolved by :func:`read_bound`; a default
        baked in here would be a threshold every caller could inherit while believing it had
        consulted the tenant's.
        """
        b = self.bound.bound
        return unfitness(
            relevant_units=b.relevant_in_sample, sample_units=b.sample_size,
            threshold=self.unfit_relevant_share)

    @property
    def unfitness_fr(self) -> str | None:
        """The declaration in words, or ``None`` when there is none to make.

        Also ``None`` on a **legacy** bound, which recorded no *ranking version*: FR-23's finding is
        that *this ranking version* is unfit, and AD-23 forbids an unqualified reference to one. A
        declaration naming no version would be an accusation with no defendant — and the legacy
        ``recall_review`` was computed over a different population entirely (planning decision A1),
        so a finding about the current order could not be drawn from it anyway.
        """
        finding = self.unfitness
        if finding is None or self.bound.ranking_version_no is None:
            return None
        return unfitness_statement_fr(
            finding, version_no=self.bound.ranking_version_no, unit_fr=self.bound.unit_fr,
            kind=self.kind)


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
            current=by_version[version_no], superseded=superseded, version_no=version_no))
    return tuple(assessments)


#: The trigger whose movement discharges FR-23's unfitness line. Resolved through ``trigger()`` so
#: a typo is a loud import-time failure rather than a condition that silently never fires — which
#: would leave the banner undischargeable again, in exactly the way this story exists to fix.
_RANKING_VERSION_MOVED = trigger("ranking_version_no").key


def read_worklist(
    *, tenant: str, matter: str, scopes: set[str], reader: FreshnessReader,
    config_get: Callable[[str], object],
) -> tuple[WorklistLine, ...] | None:
    """The *matter*'s worklist — one line per stale artefact, naming the inputs that moved and
    **offering** the recomputation (FR-58) — plus FR-23's unfitness line where the *ranking
    version* has been found not to rank.

    The unfitness line is **not** a staleness line and is deliberately built here rather than in
    :func:`~apx.core.domain.worklist.worklist_lines`: nothing is stale, the ranking is current, and
    the offer is a re-rank with a **revised case theory** rather than the plain re-rank a moved
    corpus would ask for. CONFIRMED by the review — FR-23 has four clauses and this one, *"produces
    a worklist line offering a re-rank with a revised or newly written case theory (FR-37)"*, had
    no code anywhere.

    Reading it writes nothing and starts nothing. ``()`` = read, nothing to do; ``None`` = not
    read."""
    assessments = read_freshness(tenant=tenant, matter=matter, scopes=scopes, reader=reader)
    if assessments is None:
        return None
    lines = list(worklist_lines(assessments))
    bound = read_bound(
        tenant=tenant, matter=matter, scopes=scopes, reader=reader, config_get=config_get)
    # FR-23's line is emitted only while the finding is about the ranking IN FORCE. The finding is
    # MEASURED — a share of relevant units in a drawn sample — and it belongs to the *ranking
    # version* the bound was drawn over. Once the matter has been re-ranked, that version is not the
    # one on screen, and this module's own rule for a superseded artefact applies with full force:
    # "the offer never discharges: the user accepts the re-rank and the banner still demands one,
    # growing by one paragraph per act until nobody reads it". It was applied to every line except
    # the one whose offer is hardest to satisfy, and it was harmless only while no re-rank control
    # existed — story 7.6 shipped that control.
    #
    # Silence afterwards would be dishonest if it were silence. It is not: version n+1 has NOT been
    # measured, so declaring it unfit would be a verdict nobody computed; and the bound itself is
    # now stale on ``ranking_version_no``, so the worklist already carries "La borne de confiance —
    # périmé depuis : un nouveau classement. Ré-échantillonner…", which is the next act.
    #
    # The comparison is the one this module already computes: the bound's own freshness reports
    # ``ranking_version_no`` among its changed inputs exactly when the ranking has moved since the
    # bound was drawn. Reading it here rather than fetching the current version again keeps one
    # referent for one fact. An UNSTAMPED bound emits nothing, which is the stance BoundReading
    # already takes — an absence of evidence is not evidence of validity.
    in_force = (
        bound is not None
        and bound.freshness is not None
        and not bound.freshness.superseded
        and _RANKING_VERSION_MOVED not in bound.freshness.changed)
    if bound is not None and bound.unfitness_fr is not None and in_force:
        # FR-23: the system *"does not offer a line move as the remedy"*. Raised by the review, and
        # correctly: the offer lives in ``worklist.OFFER_REPLACE_LINE``, which the structural check
        # was not looking at. No surface acts on it today — Story 4.9's control does not exist — but
        # a stale LINE already produces the offer, so a *matter* whose ranking carries no signal AND
        # whose line has moved would hand the lawyer both "re-rank with a revised theory" and
        # "replace the line". Removing it is the requirement; greying it would not be, and neither
        # is waiting for the surface that will read it.
        lines = [line for line in lines if line.offer != OFFER_REPLACE_LINE]
        # The line names the RANKING VERSION it accuses, by identity — AD-23 forbids an unqualified
        # reference to one, and an offer with no named subject is an instruction with no argument.
        lines.append(unfitness_line(
            version_id=f"ranking-v{bound.bound.ranking_version_no}",
            version_no=bound.bound.ranking_version_no,
            said_fr=bound.unfitness_fr))
    return tuple(lines)


def read_bound(
    *, tenant: str, matter: str, scopes: set[str], reader: FreshnessReader,
    config_get: Callable[[str], object],
) -> BoundReading | None:
    """The current *confidence bound* and the verdict on it. ``None`` when out of scope, absent, or
    when no bound has been recorded — the surface renders "no bound yet" as its own state.

    ``config_get`` resolves the FR-23 unfitness threshold as *configuration-as-data* (AD-24), the
    same shape the semantic read seam uses for its similarity floor: the value that runs is the
    *tenant*'s, never a caller-supplied override. It is ``coerce``d rather than read bare, so a
    stray type or an out-of-range share fails loudly instead of silently disabling the declaration.
    """
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
    return BoundReading(
        bound=bound, freshness=verdict,
        unfit_relevant_share=float(coerce(UNFIT_SHARE_KEY, config_get(UNFIT_SHARE_KEY))))
