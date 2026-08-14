"""The *matter* record as a document — the artefact a *bâtonnier* reads without the system
(Story 5.7, FR-26 / FR-11 / FR-53 / AD-35 / AD-43).

FR-26 asks for the record of a whole *matter*, exportable, self-contained, scoped, and honest about
its own limits. This module is that document **as data**: a pure structure with no clock, no store
and no I/O, so that the self-containment assertion is possible at all — a test can rebuild the whole
thing in a process with no access to the application's stores and recompute every number in it.

**The tier is not a filter applied afterwards.** It is an argument to the assembly, and the
numbers-only document is *built without* the content rather than built and then stripped. A
stripping step is one forgotten field away from shipping a quoted passage to opposing counsel; a
constructor that never receives the passage cannot.

**The cover carries the document's limits, first.** The scope it was produced under, the continuity
verdict **per chain** (AD-43 — only the *matter*'s own chain is recomputable by a reader holding
this document alone, and saying so is the point), an unacknowledged truncation (AD-35), and
**degraded** with its count where a retained extract no longer resolves (FR-11).

**A section whose act does not exist yet says so.** It prints a sentence naming the story, never an
empty table and never a zero — zero is a finding about the firm, *not built* is a finding about the
build, and a reader given the first would draw a conclusion the second does not support.
:data:`PENDING_SECTIONS` is **empty as of Story 5.8**: the *validation acts* and the accepted-as-is
half of the breakdown were the last two, and both acts now exist. Their blocks are not *replaced by
a zero* — they are retired because the thing they protected against is gone, and a **0** in §7 is
now a finding about the firm, which is precisely what it was not the day before.

Pure core: stdlib only, no adapter import, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum

from apx.core.domain.audit import (
    WITNESS_FR,
    WITNESS_PARTIAL,
    ChainVerdict,
    HeadComparison,
    HeadWitness,
    VerifiableEntry,
    compare_to_witness,
    verify_chains,
    witness_sentence_fr,
)

# ── the tier (FR-26 §11) ──────────────────────────────────────────────────────────────────────


class Tier(StrEnum):
    """Which document is being produced. Chosen **before** production, never toggled after.

    ``NUMBERS_ONLY`` is the default everywhere a default is offered: it carries counts, versions,
    verdicts, positions and bounds and no client content — everything SM-1's reconstruction needs.
    ``FULL`` additionally carries retained extracts, *override* reasons verbatim, justifications and
    *failure register* filenames and paths, and it is the one act in the product that moves client
    content out of the firm on purpose (§11's third named egress path)."""

    NUMBERS_ONLY = "numbers-only"
    FULL = "full"

    @property
    def carries_client_content(self) -> bool:
        return self is Tier.FULL

    @property
    def label_fr(self) -> str:
        return "Chiffres seuls" if self is Tier.NUMBERS_ONLY else "Dossier complet"


#: Which catalogued act fills each section that once had none. The map is the **referent** of the
#: pending declaration below: a section is pending exactly when its act does not exist, and
#: ``a_pending_section_is_not_a_zero`` asserts the biconditional in both directions. Without it,
#: "pending" was a hand-maintained claim that could drift from the catalogue in either direction —
#: a section still printing *not built* after its act shipped, or a section printing a zero before.
SECTION_ACTS: dict[str, str] = {
    "validation_acts": "validate_piece",
    "accepted_as_is": "values_accepted",
}

#: The story that owns each section the record cannot fill yet. A section here prints its heading
#: and a sentence naming the story — never an empty table, never a zero.
#:
#: **Empty as of Story 5.8.** Both entries were this story's, and both acts now exist. The blocks
#: are not *replaced by a zero* — they are retired because the thing they protected against no
#: longer exists, and a **0** in §7 is now a finding about the firm, which is exactly what it was
#: not yesterday. Kept as a declared empty mapping: the next section to arrive ahead of its act
#: belongs here, and a rule with nowhere to be declared is one that gets skipped.
PENDING_SECTIONS: dict[str, str] = {}


def pending_sentence_fr(section: str) -> str:
    """What a not-yet-built section says, in the lawyer's language. Explicit about *why* it is
    empty, because "empty" and "nothing happened" are the two readings and only one is true."""
    story = PENDING_SECTIONS[section]
    return (
        "Cette section est vide parce que l'acte n'existe pas encore : il est livré avec la story "
        f"{story}. Ce document ne dit donc rien à ce sujet — ni qu'il y en a eu, ni qu'il n'y en a "
        "pas eu."
    )


# ── the cover (FR-26, AD-43, AD-35, FR-11) ────────────────────────────────────────────────────


@dataclass(frozen=True)
class WitnessLine:
    """One chain's head as an outside record holds it (AD-35), copied onto the document.

    Everything else on this page is produced by the system the document describes. This is the one
    value that is not: it comes from the head journal, an append-only file on a volume the database
    dump does not cover, and it is what lets a reader conclude that the record in their hands is
    **all of it**. Without it a truncation to an earlier consistent point recomputes perfectly and
    reads as clean — which is precisely how a restore can shorten an audit trail and still pass
    every check the system runs on itself."""

    seq: int
    chain: str
    recorded_at: str = ""
    app_version: str = ""
    schema_version: str = ""


@dataclass(frozen=True)
class ChainVerdictLine:
    """One chain's continuity verdict as the cover prints it (AD-43/FR-53).

    ``recomputable_from_this_document`` is the whole reason there are two lines and not one
    boolean: a reader holding a scoped export can recompute the *matter*'s own chain and cannot
    recompute the *tenant* chain, whose links run through entries they are not entitled to see. One
    verdict over both would claim a property of bytes the reader does not hold.

    **It is derived at assembly from this document's own contents** (Story 5.9) — the document holds
    this chain's entries *and* its anchor — and from nothing else. It used to be copied from a
    boolean about the server's own storage: whether the ``audit_chain_head`` row in the database
    carried an anchor. So it printed **True** on a document from which literally nothing could be
    recomputed, because the document carried no entries at all. The name of the field is the
    requirement; a value taken from anywhere but the document cannot satisfy it.

    ``verified`` and ``broken_at`` remain the PRODUCER's verdict, computed against the live store.
    That is not redundant with the reader's own recomputation — it is what the reader's
    recomputation is checked against, and a disagreement between them is itself a finding."""

    chain_scope: str
    label_fr: str
    entries: int
    verified: bool
    #: this document holds this chain's entries — the material to recompute WITH
    carries_its_entries: bool = False
    #: …and its anchor, so the FIRST link is provable too. The two are separate because they fail
    #: separately: a document can carry every entry of a chain whose head row was rebuilt at
    #: restore, in which case every link after the first is proved and the first is admitted. One
    #: flag over both would let *admitted* read as *proved*.
    recomputable_from_this_document: bool = False
    broken_at: int | None = None
    #: what broke, per :mod:`apx.core.domain.audit` — a gap, a link, an unreadable field
    cause: str | None = None
    #: the value this chain's FIRST entry chains onto. ``""`` is meaningful on the *tenant* chain
    #: (it is the root); ``None`` means unknown — a head row rebuilt at restore never carried one —
    #: and the two must not be conflated, so the first link is taken as given rather than as proved.
    anchor: str | None = None
    #: the outside witness for this chain, when one was recorded
    witness: WitnessLine | None = None


@dataclass(frozen=True)
class Cover:
    """The document's first page: what it is, what it may contain, and what it cannot prove.

    ``degraded_extracts`` is computed at **read** time from the extracts' show-time verdicts
    (FR-11), so a document produced clean can be produced degraded later — the number describes
    the moment of production and the cover says which moment that was."""

    matter: str
    scope: str
    tier: Tier
    produced_by: str
    # ISO 8601, supplied by the caller — the Domain has no clock
    produced_at: str
    chains: tuple[ChainVerdictLine, ...] = ()
    truncation_unacknowledged: bool = False
    truncation_note: str | None = None
    degraded_extracts: int = 0
    #: The *tenant* the record belongs to. Not decoration: it is one of the fields the chained value
    #: is taken over, so a document without it cannot be recomputed by anyone (FR-53).
    tenant: str = ""

    @property
    def degraded(self) -> bool:
        """FR-11 — a state of the document, said on its face with its count, never a footnote."""
        return self.degraded_extracts > 0

    @property
    def degraded_sentence_fr(self) -> str | None:
        if not self.degraded:
            return None
        n = self.degraded_extracts
        if n == 1:
            return "1 extrait retenu ne se résout plus — ce document est dégradé."
        return f"{n} extraits retenus ne se résolvent plus — ce document est dégradé."


# ── the eight sections FR-26 enumerates ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class DenominatorLine:
    """§1 — one named count of the scoped *denominator* (AD-38). Seven of them, never one number."""

    key: str
    label_fr: str
    count: int


@dataclass(frozen=True)
class CaseTheoryLine:
    """§2 — one version of the *case theory*. ``text`` is present only in the FULL tier: a case
    theory is the firm's legal strategy, which is exactly what numbers-only must not carry."""

    version_no: int
    version_id: str
    actor: str
    at: str
    text: str | None = None


@dataclass(frozen=True)
class LineHistoryLine:
    """§3 — one position **the line** has held, with its author and the price shown for it (FR-24).

    ``priced_statement`` is ``None`` for a first placement, which was not a move. Both tiers carry
    it: it is a projection over counts, not client content."""

    version_no: int
    seq: int
    last_retained_piece_id: str
    basis: str
    placed_by: str
    at: str
    priced_statement: str | None = None


@dataclass(frozen=True)
class PinLine:
    """§4 — one entry of the pin ledger. **All** pins, including those later lifted: a pin posed and
    removed is a decision that was taken. ``reason`` only in the FULL tier (it is an *override*
    reason, written by a lawyer about a document)."""

    piece_id: str
    seq: int
    action: str
    set_by: str
    at: str
    reason: str | None = None


@dataclass(frozen=True)
class SamplingRunLine:
    """§5 — one *sampling run* and the sentence it produced. ``bound_sentence_fr`` is **quoted**
    from the server's composer, never re-assembled here: every path through that composer carries
    the wall and the staleness, and a document that rebuilt the sentence from numeric fields could
    drop either (FR-58/FR-23)."""

    run_id: str
    status: str
    drawn: int
    reviewed: int
    population_size: int
    bound_sentence_fr: str | None = None


@dataclass(frozen=True)
class OverrideLine:
    """§6 — one *override* (FR-25). ``reason`` only in the FULL tier; the ground and the act are
    counts-safe and appear in both."""

    seq: int
    action: str
    action_fr: str
    ground: str
    ground_fr: str
    actor: str
    at: str
    reason: str | None = None


@dataclass(frozen=True)
class ValidationLine:
    """§7 — one entry of the validation ledger (FR-45). **All** entries, including withdrawn ones:
    a validation performed and then withdrawn is a decision that was taken, and dropping it because
    it is no longer in force would let a reader conclude it never happened (the pin precedent).

    ``provenance`` is FR-45's load-bearing field — *read* or *from-the-list* — and ``opened_at`` is
    the timestamp behind it, carried so the reader can judge the distance between the reading and
    the act. ``batch_id`` present means the act was one gesture over ``batch_size`` *pièces*.

    Both tiers carry every field: an accepted band, side, label and confidence are the tool's own
    categorical output, not client content."""

    piece_id: str
    seq: int
    action: str
    actor: str
    at: str
    provenance: str
    ranking_version_id: str
    opened_at: str | None = None
    batch_id: str | None = None
    batch_size: int | None = None
    accepted_side: str | None = None
    accepted_label: str | None = None
    accepted_band: str | None = None
    accepted_confidence: float | None = None


@dataclass(frozen=True)
class ValidationSummary:
    """§7's counts, split by register and **never pooled** (FR-45(d), §13 q.5).

    A reader of this document must always be able to tell individual judgements from one gesture
    over many, and reading from accepting-from-the-list. A single *validated* total would make both
    impossible while looking complete — which is the shape of every compliance number that has ever
    been reported instead of measured."""

    read: int
    from_the_list: int
    individually: int
    in_bulk: int
    batches: int
    withdrawn: int
    never_validated: int

    @property
    def in_force(self) -> int:
        return self.read + self.from_the_list


@dataclass(frozen=True)
class ChainEntryLine:
    """§9 — one entry of the *audit record* as the document carries it (FR-53).

    This section exists because the document had a continuity verdict and no way to check it. Every
    other number here is one a reader can re-derive from the page; the chain's verdict was the one
    claim that had to be taken on the producer's word, since the entries it was computed over never
    left the database.

    Every field is an **input to the chained value**, and there are no others: the recipe is
    ``chained_content(version, seq, tenant, chain_scope, matter, actor, action, detail, timestamp,
    app_version, schema_version)`` and this line carries each of them, with the *tenant* on the
    cover. ``at`` is the timestamp **in the rendering the chain was taken over** — UTC, tz-naive,
    microseconds — not the display rendering used elsewhere in this document: a reader handed
    ``2026-08-13T10:00:00+00:00`` and asked to recompute a value taken over
    ``2026-08-13T10:00:00.000000`` concludes the record was tampered with, which is the false alarm
    the content-version machinery exists to avoid.

    ``chain_scope`` is on every line because a *matter*'s history spans two chains with two
    independent countings (AD-43), and a sequence number printed without its chain is a number a
    reader will cross-reference against an unrelated one."""

    chain_scope: str
    seq: int
    at: str
    #: ``None`` where the ciphertext could not be authenticated. Carried as absence rather than as
    #: a placeholder string: a reader handed ``"«illisible»"`` recomputes a value that does not
    #: match and concludes the entry was REWRITTEN, when what happened is that a field cannot be
    #: read at all. Two different findings, and the document must not merge them.
    actor: str | None
    action: str
    detail: str | None
    chain: str
    content_version: int
    app_version: str = ""
    schema_version: str = ""
    #: the *matter* the act was ABOUT, which is not always the chain it was counted on: a
    #: tenant-level act names its matter here and lands on the tenant chain (FR-24)
    matter: str | None = None


@dataclass(frozen=True)
class PendingSection:
    """A section whose act does not exist yet (FR-26 + the project's standing rule)."""

    key: str
    heading_fr: str
    story: str
    sentence_fr: str


@dataclass(frozen=True)
class MatterRecord:
    """The whole document, as data (FR-26).

    Assembled by :func:`assemble`, which is the only place the tier decides what is carried. Nothing
    here is rendered: a renderer turns this into a page, and the self-containment test rebuilds
    every number from this structure alone."""

    cover: Cover
    denominator: tuple[DenominatorLine, ...] = ()
    case_theory: tuple[CaseTheoryLine, ...] = ()
    line_history: tuple[LineHistoryLine, ...] = ()
    pins: tuple[PinLine, ...] = ()
    sampling_runs: tuple[SamplingRunLine, ...] = ()
    overrides: tuple[OverrideLine, ...] = ()
    #: FR-25: counted over the WHOLE record, never the length of ``overrides`` (a tier or a filter
    #: could shorten the list; neither changes how many overrides the matter holds).
    overrides_total: int = 0
    #: §7 (FR-45) — every entry of the validation ledger, and the counts split by register.
    validations: tuple[ValidationLine, ...] = ()
    validation_summary: ValidationSummary | None = None
    #: §8 — the modified-versus-accepted breakdown. ``accepted_values`` counts the **pièces** whose
    #: values stand accepted as-is — one per validation act in force, not one per field it covered —
    #: and it is derived from the validation ledger and from **nothing else**: FR-45 is explicit
    #: that no default, elapsed time, scroll position or screen visit produces one. ``modified_
    #: values`` counts the recorded acts of modification beside it, which is the asymmetry FR-24
    #: §614 draws: a modification is an edit, an acceptance needs a gesture behind it.
    modified_values: int = 0
    accepted_values: int = 0
    #: §9 (FR-53) — the entries themselves, so the cover's continuity verdict is a claim the reader
    #: can check rather than one they must accept. **FULL tier only**: an entry's ``detail``
    #: carries, for some verbs, what a lawyer typed (a search query) or a document's own name, and
    #: numbers-only exists precisely to leave the building without those. A numbers-only document
    #: says on its face that it holds the producer's word — see :func:`read_continuity`.
    trail: tuple[ChainEntryLine, ...] = ()
    pending: tuple[PendingSection, ...] = field(default_factory=tuple)

    @property
    def tier(self) -> Tier:
        return self.cover.tier


# ── the assembly — the ONE place the tier decides what is carried ──────────────────────────────

_DENOMINATOR_FR: tuple[tuple[str, str], ...] = (
    ("submitted_pieces", "Pièces soumises"),
    ("in_corpus", "Au corpus"),
    ("open_register_entries", "Au registre, ouvertes"),
    ("overridden_register_entries", "Écartées par dérogation"),
    ("excluded_as_noise", "Exclues comme bruit"),
    ("retired", "Retirées"),
    ("unknown_cardinality_entries", "Archives non ouvertes, contenu inconnu"),
)

#: The heading each section prints, whether it is built or pending. One registry, so a section that
#: retires its pending block keeps the name a reader has already seen.
SECTION_HEADINGS_FR: dict[str, str] = {
    "validation_acts": "Les actes de validation",
    "accepted_as_is": "Accepté en l'état",
}


def _pending_sections() -> tuple[PendingSection, ...]:
    return tuple(
        PendingSection(
            key=key, heading_fr=SECTION_HEADINGS_FR[key], story=story,
            sentence_fr=pending_sentence_fr(key))
        for key, story in PENDING_SECTIONS.items())


# ── the continuity check, run on the DOCUMENT (§9, FR-53) ─────────────────────────────────────


@dataclass(frozen=True)
class ChainReading:
    """What a reader holding **only this document** establishes about one chain (FR-53).

    ``verdict`` is the reader's OWN recomputation, and it is ``None`` exactly when the document does
    not carry the material — never a ``verified=True`` standing in for *not checked*.
    ``agrees_with_producer`` compares that recomputation against the verdict printed on the cover:
    the point of printing both is that they can disagree, and a disagreement is a finding about the
    document rather than about the record.

    ``comparison`` is the other half, and the one no amount of recomputation supplies: whether the
    chain ends where a witness outside the store saw it end."""

    chain_scope: str
    label_fr: str
    recomputable: bool
    comparison: HeadComparison
    #: how many of this chain's entries the document turned out to hold — the difference between
    #: *a slice, by design* and *none of it at all*, which are two different things to tell a reader
    holds_entries: int = 0
    verdict: ChainVerdict | None = None
    #: ``None`` when no recomputation was performed — *agrees* is a comparison, and a comparison
    #: nobody made is not agreement.
    agrees_with_producer: bool | None = None
    printed_verified: bool = False

    @property
    def sound(self) -> bool:
        """The reader's conclusion: recomputed, recomputes, agrees with what the page says, and ends
        where the outside witness saw it end. Every one of the four is required, and the property is
        written as a conjunction of positives so that a state nobody thought about defaults to
        *not established* rather than to *fine*."""
        return bool(
            self.recomputable
            and self.verdict is not None
            and self.verdict.verified
            and self.verdict.anchored
            and self.agrees_with_producer is True
            and self.comparison.complete
        )

    @property
    def sentence_fr(self) -> str:
        """The reading as the cover prints it — one chain, one sentence, in her own language."""
        producers_word = (
            "ce document ne porte pas les entrées de cette chaîne : sa continuité y est affirmée "
            "par le producteur, elle n'y est pas vérifiable."
        )
        if self.comparison.state == WITNESS_PARTIAL:
            # A slice held by design (the tenant chain, under this reader's wall) says so; a chain
            # the document carries NOTHING of says the other thing. Both are limits, and telling a
            # reader the wrong one sends them looking for the wrong explanation.
            return WITNESS_FR[WITNESS_PARTIAL] if self.holds_entries else producers_word
        if self.verdict is None:
            head = producers_word
        elif not self.verdict.verified:
            head = (
                f"recalculée depuis ce document, la chaîne rompt au n° {self.verdict.broken_at} — "
                f"{self.verdict.cause_fr}"
            )
        elif self.agrees_with_producer is False:
            head = (
                "recalculée depuis ce document, la chaîne se vérifie, mais le verdict imprimé sur "
                "ce document dit le contraire : les deux ne portent pas sur la même chose."
            )
        elif not self.verdict.anchored:
            head = (
                "recalculée depuis ce document, la chaîne se vérifie à partir de sa deuxième "
                "entrée : ce document ne porte pas la valeur sur laquelle la première s'accroche, "
                "elle est donc admise et non prouvée."
            )
        else:
            head = "recalculée depuis ce document, la chaîne se vérifie de bout en bout."
        return f"{head} {witness_sentence_fr(self.comparison)}"


def _verifiable(record: MatterRecord, scope: str) -> list[VerifiableEntry]:
    """This document's entries for one chain, in the shape the shared verifier reads. Built from the
    page and from nothing else — that constraint is the whole point of the section."""
    return [
        VerifiableEntry(
            tenant=record.cover.tenant, chain_scope=e.chain_scope, seq=e.seq, matter=e.matter,
            actor=e.actor, action=e.action, detail=e.detail, timestamp=e.at, chain=e.chain,
            content_version=e.content_version, app_version=e.app_version,
            schema_version=e.schema_version)
        for e in record.trail if e.chain_scope == scope
    ]


def read_continuity(record: MatterRecord) -> tuple[ChainReading, ...]:
    """Run the continuity check **on the document**, chain by chain, in the order the cover names
    them (FR-53).

    Nothing here touches a store, a clock or a network: given the bytes of an export and this
    module, a reader recomputes every link the document carries and compares the end of each chain
    against the head recorded outside the restorable store. That is what *"detectable by a reader
    holding only the export"* asks for, and until Story 5.9 the product satisfied none of it — the
    document carried a verdict and no entries.

    A chain the document does not carry in full is reported as **partial** rather than as truncated:
    a scoped export holds this *matter*'s share of the *tenant* chain and no more, and where that
    chain ends is not this reader's to establish."""
    readings: list[ChainReading] = []
    for line in record.cover.chains:
        entries = _verifiable(record, line.chain_scope)
        witness = (
            HeadWitness(
                chain_scope=line.chain_scope, seq=line.witness.seq, chain=line.witness.chain,
                recorded_at=line.witness.recorded_at, app_version=line.witness.app_version,
                schema_version=line.witness.schema_version)
            if line.witness is not None else None)
        # The recomputation runs on whatever the document CARRIES; the anchor decides only whether
        # the first link is proved or admitted, and ``ChainVerdict.anchored`` says which. Gating the
        # recomputation on the anchor instead would throw away every link a rebuilt-head document
        # can still prove — and, worse, would make that document report *partial*, which would skip
        # its truncation check entirely.
        carries = line.carries_its_entries and bool(entries)
        # A FULL-tier document is BUILT to carry the *matter*'s own chain. Holding none of it is
        # therefore not a tier omission — it is the maximal truncation, the whole chain gone, and
        # reporting that as *partial* would silence the one loss that removes everything. A
        # numbers-only document omits §9 by design and says so instead.
        built_to_carry = line.chain_scope == record.cover.matter and record.cover.tier is Tier.FULL
        partial = not (carries or built_to_carry)
        verdict: ChainVerdict | None = None
        if carries:
            anchors = {line.chain_scope: line.anchor} if line.anchor is not None else {}
            found = verify_chains(entries, anchors)
            verdict = next((v for v in found if v.chain_scope == line.chain_scope), None)
        readings.append(ChainReading(
            chain_scope=line.chain_scope,
            label_fr=line.label_fr,
            recomputable=line.recomputable_from_this_document and bool(entries),
            comparison=compare_to_witness(entries, witness, partial=partial),
            holds_entries=len(entries),
            verdict=verdict,
            # ``None``, not True, when nothing was recomputed: *agrees* is a comparison, and a
            # comparison nobody performed must not print as agreement — the shape of every
            # reassuring default this project has had to take back out.
            agrees_with_producer=None if verdict is None else verdict.verified == line.verified,
            printed_verified=line.verified,
        ))
    return tuple(readings)


def assemble(
    *,
    cover: Cover,
    denominator: object,
    case_theory: tuple[CaseTheoryLine, ...] = (),
    line_history: tuple[LineHistoryLine, ...] = (),
    pins: tuple[PinLine, ...] = (),
    sampling_runs: tuple[SamplingRunLine, ...] = (),
    overrides: tuple[OverrideLine, ...] = (),
    overrides_total: int = 0,
    validations: tuple[ValidationLine, ...] = (),
    validation_summary: ValidationSummary | None = None,
    modified_values: int = 0,
    accepted_values: int = 0,
    trail: tuple[ChainEntryLine, ...] = (),
) -> MatterRecord:
    """Build the document for ``cover.tier``.

    **The tier is applied here and only here, by omission.** A numbers-only record is *built
    without* the content-bearing fields, not built and then stripped: a stripping step is one
    forgotten field away from putting a quoted passage in front of opposing counsel, and a
    constructor that never receives the passage cannot leak it. The caller may pass the full lines
    either way — this function drops what the tier does not carry, so a caller cannot leak by
    forgetting to check the tier, which is the mistake worth designing against.

    ``denominator`` is the seven-count ``Inventory`` (AD-38), read by attribute so the Domain does
    not import the store's shape; a missing count is a build error here rather than a silently
    absent line in a court document."""
    numbers_only = cover.tier is Tier.NUMBERS_ONLY
    lines = tuple(
        DenominatorLine(key=key, label_fr=label, count=int(getattr(denominator, key)))
        for key, label in _DENOMINATOR_FR)
    # §9 is dropped by the tier like every other content-bearing section: an entry's ``detail``
    # carries, for some verbs, a lawyer's own search terms.
    carried = () if numbers_only else trail
    #: **Derived here and only here** (Story 5.9), from what this document turns out to hold. A
    #: chain is recomputable by a reader holding this document when the document carries its
    #: entries AND the chain is the *matter*'s own — AD-43's reason, readable off the page: the
    #: *tenant* chain's links run through acts outside this reader's wall, so a scoped export holds
    #: a slice of it and can conclude nothing about where it begins or ends. The caller's value is
    #: DISCARDED rather than trusted: it used to be a fact about the server's own storage, printed
    #: under a name that asserts a property of the reader's bytes.
    with_entries = {e.chain_scope for e in carried}
    chains = tuple(
        replace(
            line,
            carries_its_entries=(
                line.chain_scope == cover.matter and line.chain_scope in with_entries),
            # AC-5, literally: the entries AND the anchor. A chain whose anchor this document does
            # not carry has an ADMITTED first link, not a proved one, and the flag that gates the
            # reader's conclusion must not treat the two as the same thing.
            recomputable_from_this_document=(
                line.chain_scope == cover.matter
                and line.chain_scope in with_entries
                and line.anchor is not None))
        for line in cover.chains)
    return MatterRecord(
        cover=replace(cover, chains=chains),
        denominator=lines,
        case_theory=tuple(
            CaseTheoryLine(
                version_no=c.version_no, version_id=c.version_id, actor=c.actor, at=c.at,
                text=None if numbers_only else c.text)
            for c in case_theory),
        line_history=line_history,
        pins=tuple(
            PinLine(
                piece_id=p.piece_id, seq=p.seq, action=p.action, set_by=p.set_by, at=p.at,
                reason=None if numbers_only else p.reason)
            for p in pins),
        sampling_runs=sampling_runs,
        overrides=tuple(
            OverrideLine(
                seq=o.seq, action=o.action, action_fr=o.action_fr, ground=o.ground,
                ground_fr=o.ground_fr, actor=o.actor, at=o.at,
                reason=None if numbers_only else o.reason)
            for o in overrides),
        overrides_total=overrides_total,
        validations=validations,
        validation_summary=validation_summary,
        modified_values=modified_values,
        accepted_values=accepted_values,
        trail=tuple(carried),
        pending=_pending_sections(),
    )
