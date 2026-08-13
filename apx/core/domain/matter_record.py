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

**A section whose act does not exist yet says so.** The *validation acts* and the accepted-as-is
half of the modified-versus-accepted breakdown are Story 5.8's. They print a sentence naming the
story, never an empty table and never a zero — zero is a finding about the firm, *not built* is a
finding about the build, and a reader given the first would draw a conclusion the second does not
support.

Pure core: stdlib only, no adapter import, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

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


#: The story that owns each section the record cannot fill yet. A section here prints its heading
#: and a sentence naming the story — never an empty table, never a zero.
PENDING_SECTIONS: dict[str, str] = {
    "validation_acts": "5.8",
    "accepted_as_is": "5.8",
}


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
class ChainVerdictLine:
    """One chain's continuity verdict as the cover prints it (AD-43/FR-53).

    ``recomputable_from_this_document`` is the whole reason there are two lines and not one
    boolean: a reader holding a scoped export can recompute the *matter*'s own chain and cannot
    recompute the *tenant* chain, whose links run through entries they are not entitled to see. One
    verdict over both would claim a property of bytes the reader does not hold."""

    chain_scope: str
    label_fr: str
    entries: int
    verified: bool
    recomputable_from_this_document: bool
    broken_at: int | None = None


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
    modified_values: int = 0
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

_PENDING_HEADINGS_FR: dict[str, str] = {
    "validation_acts": "Les actes de validation",
    "accepted_as_is": "Accepté en l'état",
}


def _pending_sections() -> tuple[PendingSection, ...]:
    return tuple(
        PendingSection(
            key=key, heading_fr=_PENDING_HEADINGS_FR[key], story=story,
            sentence_fr=pending_sentence_fr(key))
        for key, story in PENDING_SECTIONS.items())


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
    modified_values: int = 0,
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
    return MatterRecord(
        cover=cover,
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
        modified_values=modified_values,
        pending=_pending_sections(),
    )
