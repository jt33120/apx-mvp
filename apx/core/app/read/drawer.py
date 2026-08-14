"""The *audit drawer* for one *pièce* — the trust surface the sceptic lives in (Story 5.7, FR-26).

The UX contract fixes four bands and states that **the order is the argument**: what the tool
concluded, what that rests on, what will be written if the lawyer acts, and what she can do. A
lawyer who reads them top to bottom has been walked from conclusion to evidence to consequence to
choice; one who reads a set of buttons with no argument behind them has been handed every
compliance feature that ever shipped and got dismissed.

This seam assembles the bands from reads that already exist — it writes nothing and decides
nothing. Three properties it does not get to choose:

**The confidence is derived** (4.4) and says so, naming its *ranking version* (AD-23). A drawer
that showed a bare figure would be showing something indistinguishable from a self-report.

**Every extract is verified at show time** (4.6/FR-11), by the same ``read_justification`` a
containment failure already governs — one verification path, so the drawer can never show a lawyer
something the export would call degraded.

**The proposed entries come from the catalogue** (:mod:`apx.core.domain.proposed_entry`), so the
panel that says where an entry will land and the writer that files it there cannot disagree. An act
the record has no way to file cannot be proposed at all, and that refusal — not a convention
somebody has to remember — is what kept the *validation act*'s control disabled until Story 5.8
catalogued its verb.

**The validation provenance is read, not asserted** (5.8, FR-45/FR-44). The drawer carries *when
this caller last opened this pièce*, so the panel states what a *validation act* would record
**before** she commits it rather than letting her discover it afterwards. Another lawyer's open is
not her reading, which is why the read is per-actor, and the value is a timestamp rather than a flag
because *"opened"* alone is equally true of an open six months and three rankings ago.

Imports Ports and Domain only (AD-4), touches no store.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from apx.core.domain import audit as AUDIT
from apx.core.domain.justification import VerifiedJustification
from apx.core.domain.proposed_entry import (
    ProposedEntry,
    ProposedEntryUnavailable,
    propose,
)
from apx.core.domain.validation import (
    REVERSAL_FR as VALIDATION_REVERSAL_FR,
)
from apx.core.domain.validation import (
    Provenance,
)
from apx.core.ports.justification import JustificationStore

#: The acts the drawer offers, in the contract's order, each with the sentence naming **its own
#: reversal**. FR-26 requires every action in the drawer to be reversible; saying how, in the same
#: breath, is what stops "reversible" from being a property only the architecture knows about.
OFFERED_ACTS: tuple[tuple[str, str], ...] = (
    (AUDIT.ACT_PIECE_LABELLED,
     "reclassez à nouveau — chaque valeur que la pièce a portée reste au journal"),
    (AUDIT.ACT_JUSTIFICATION_REJECTED,
     "rétablissez-la — le rejet reste lisible, rien n'est effacé"),
    (AUDIT.ACT_JUSTIFICATION_RESTORED,
     "écartez-la de nouveau ; les deux actes restent inscrits"),
    (AUDIT.ACT_PIN_OVERRIDE,
     "retirez l'épingle — la pose et le retrait restent tous deux inscrits"),
    (AUDIT.ACT_PIN_REMOVED,
     "épinglez à nouveau ; le registre garde chaque épingle et chaque retrait"),
    (AUDIT.ACT_VALIDATE_PIECE, VALIDATION_REVERSAL_FR),
    (AUDIT.ACT_VALIDATION_WITHDRAWN,
     "validez à nouveau ; chaque validation et chaque retrait restent inscrits"),
)

#: An act the drawer names but cannot offer, and the story that owns it. Rendered **disabled with
#: its reason** rather than hidden: a hidden control cannot be asked about, and a disabled one that
#: says why tells the truth about the build to the only person either could mislead.
#:
#: **Empty as of Story 5.8**, whose act was the only entry. :func:`_pending` raises the moment a
#: listed verb becomes catalogued — deliberately, so a control cannot stay disabled after its act
#: ships. That tripwire fired on this story and was answered by removing the row, never by
#: weakening the assertion.
PENDING_ACTS: dict[str, tuple[str, str]] = {}


@dataclass(frozen=True)
class OfferedAction:
    """One reversible action, with the entry it would write and how it is undone."""

    action: str
    action_fr: str
    reversal_fr: str
    proposed: ProposedEntry

    @property
    def reason_required(self) -> bool:
        return self.proposed.reason_required


@dataclass(frozen=True)
class PendingAction:
    """An action whose act does not exist yet — shown, disabled, naming its story."""

    label_fr: str
    story: str

    @property
    def disabled_reason_fr(self) -> str:
        return f"Cette action arrive avec la story {self.story}."


@dataclass(frozen=True)
class Drawer:
    """The four bands, as data. A renderer turns this into the panel; nothing here is a decision.

    ``justification`` is ``None`` when the tool recorded none for this *pièce* — which the surface
    states as itself, never as an empty band: "no justification was recorded" and "the justification
    is empty" are different facts and only one of them can be true."""

    piece_id: str
    matter: str
    #: the *ranking version* the caller read against (AD-23 — no unqualified reference to a ranked
    #: figure). Carried from the caller rather than re-derived: the drawer must name the version the
    #: SURFACE is showing, not whichever is newest at the moment the panel opens.
    ranking_version_no: int | None
    justification: VerifiedJustification | None
    actions: tuple[OfferedAction, ...]
    pending_actions: tuple[PendingAction, ...]
    #: When THIS caller last opened this *pièce* in the viewer, or ``None`` (FR-45/FR-44). The
    #: drawer carries the timestamp rather than a flag so the surface can print the date: the
    #: consequence of the act is stated **before** it is committed, and *"opened"* alone is equally
    #: true of an open six months and three rankings ago.
    opened_at: datetime | None = None

    @property
    def validation_provenance(self) -> Provenance:
        """What a *validation act* performed now would record (FR-45) — derived, never asserted."""
        return Provenance.of(self.opened_at)

    @property
    def is_unverified(self) -> bool:
        """FR-11 — at least one named extract failed containment **at this read**. An
        intrinsic-only justification is NOT unverified; that distinction is load-bearing and the
        domain already draws it."""
        return self.justification is not None and self.justification.is_unverified

    @property
    def unresolved_extracts(self) -> int:
        if self.justification is None:
            return 0
        return sum(1 for e in self.justification.extracts if not e.verified)


def _offered(matter: str, actor: str) -> tuple[OfferedAction, ...]:
    offered: list[OfferedAction] = []
    for action, reversal in OFFERED_ACTS:
        proposed = propose(action, actor=actor, matter=matter)
        offered.append(OfferedAction(
            action=action, action_fr=proposed.action_fr, reversal_fr=reversal,
            proposed=proposed))
    return tuple(offered)


def _pending() -> tuple[PendingAction, ...]:
    out: list[PendingAction] = []
    for verb, (story, label) in PENDING_ACTS.items():
        try:
            propose(verb, actor="probe", matter="probe")
        except ProposedEntryUnavailable:
            out.append(PendingAction(label_fr=label, story=story))
        else:                                  # pragma: no cover — the act shipped; remove the row
            raise AssertionError(
                f"{verb!r} is catalogued now — it belongs in OFFERED_ACTS, not in PENDING_ACTS")
    return tuple(out)


def read_drawer(
    store: JustificationStore, *, tenant: str, matter: str, actor: str, piece_id: str,
    scopes: set[str], version_no: int | None = None, interface_language: str | None = None,
) -> Drawer | None:
    """The drawer for one *pièce* (FR-26). ``None`` when out of scope or absent — the same answer
    for both, so a caller cannot tell an out-of-scope *pièce* from one that does not exist.

    A pure read: it writes nothing, and the acts it offers are **proposals**. The lawyer's act is a
    separate call to the use case that owns it.

    The scope is checked **explicitly**, not inferred from the justification read: that read
    returns ``None`` for "out of scope" and for "no justification recorded" alike, and a drawer
    built on the ambiguity answered with an open panel — and a list of proposed acts — for a
    *matter* behind a wall the caller does not hold."""
    if not store.matter_is_held(tenant=tenant, matter=matter, scopes=scopes):
        return None
    shown = store.read_justification(
        tenant=tenant, matter=matter, scopes=scopes, piece_id=piece_id, version_no=version_no,
        interface_language=interface_language)
    return Drawer(
        piece_id=piece_id,
        matter=matter,
        ranking_version_no=version_no,
        justification=shown,
        actions=_offered(matter, actor),
        pending_actions=_pending(),
        # FR-45/FR-44 — read for THIS actor, so the panel states what a validation act would record
        # rather than letting her discover it afterwards. Another lawyer's open is not her reading.
        opened_at=store.last_open_by(
            tenant=tenant, matter=matter, piece_id=piece_id, actor=actor, scopes=scopes),
    )
