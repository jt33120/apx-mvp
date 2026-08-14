"""The *validation act* — *"a human read this"* as a mechanism rather than a phrase (Story 5.8,
FR-45 / FR-44 / FR-24).

v1 sold *"this document was read by a human"* as one of its four claims and never built it: the
claim rested on a phrase — *validation act* — that no requirement created. FR-45 creates it, and
the design problem is **not** how to make the gesture easy. It is **how to make the record of it
true when it was easy.**

Four properties live here, and each closes a way the record could flatter the person it describes:

**The assertion is one string, and it is the control's own text.** :data:`ASSERTION_FR` is what the
lawyer presses and what the record attributes to her — the same sentence, not two that drift. A
control labelled *« Valider »* lets her assert it without reading it, and the entry would then be a
claim she never made in the words that were recorded.

**The provenance is DERIVED, never set.** :class:`Provenance` is computed from ``opened_at`` and has
no constructor a caller can hand a boolean to. FR-45's field is *whether the pièce was opened in the
viewer before the act*; storing the **timestamp** and deriving the flag keeps the distance visible,
because *"opened"* alone is equally true of an open six months and three rankings before the act.

**A bulk act is one gesture over many pièces, never one fact about many pièces.** Each *pièce*
carries its **own** provenance (FR-45(c) — *"records for each pièce that it was not opened, unless
it was"*), and :func:`check_confirmed_count` refuses a batch whose confirmation does not name the
size it is about to act on.

**What was accepted is a NAMED version's assessment.** :class:`AcceptedValues` travels with a
``ranking_version_id`` (AD-23), so a re-rank makes the acceptance *stale* — a statement about what
it referred to — and never *invalid*, because the act happened and nothing erases it.

Pure core: stdlib only, no adapter import, no I/O, no clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

# ── the assertion (FR-45) ─────────────────────────────────────────────────────────────────────

#: The meaning of the act, stated in the lawyer's language, exactly as FR-45 words it. The control's
#: own text on all three surfaces (table, viewer, drawer) and the sentence the record attributes to
#: her. One string, because two would drift and the drift would land in a court document.
ASSERTION_FR = "J'ai lu cette pièce et j'accepte l'appréciation de l'outil."

#: What the reversal says, in the same breath as the act (the drawer's band-4 rule).
REVERSAL_FR = "retirez-la — la validation et son retrait restent tous deux inscrits"

ACTION_VALIDATED = "validated"
ACTION_WITHDRAWN = "withdrawn"
ACTIONS: tuple[str, ...] = (ACTION_VALIDATED, ACTION_WITHDRAWN)


class UnknownValidationAction(ValueError):
    """An action the ledger has no column value for. Refused rather than stored: a third action
    would be a state nothing counts and nothing renders."""


def check_action(action: str) -> str:
    if action not in ACTIONS:
        raise UnknownValidationAction(
            f"unknown validation action: {action!r} (expected one of {', '.join(ACTIONS)})")
    return action


# ── the provenance (FR-45 / FR-44) ────────────────────────────────────────────────────────────


class Provenance(StrEnum):
    """How the *pièce* came to be validated — **derived**, never supplied.

    This is FR-45's load-bearing distinction and the whole reason the requirement has a fourth
    consequence: *"the last field is what distinguishes reading from clicking."* There is
    deliberately **no** constructor taking a boolean. The only way to obtain a value is
    :meth:`of`, from the timestamp of an open, so no call site can assert a provenance it did not
    read — which is exactly the shape of the defect FR-45(c) legislates against, a batch stamped
    *not opened* over a *pièce* the lawyer had in fact opened."""

    READ = "read"
    FROM_THE_LIST = "from-the-list"

    @classmethod
    def of(cls, opened_at: datetime | None) -> Provenance:
        return cls.READ if opened_at is not None else cls.FROM_THE_LIST

    @property
    def label_fr(self) -> str:
        return "lue" if self is Provenance.READ else "acceptée depuis la liste"

    @property
    def is_read(self) -> bool:
        return self is Provenance.READ


def provenance_sentence_fr(opened_at_fr: str | None) -> str:
    """What the surface says **before** the act, so the consequence is known rather than discovered.

    Second person and a **date**: the fact recorded is about the acting lawyer, and another
    lawyer's open is not this lawyer's reading — a panel saying *« ouverte le 3 août »* without
    saying by whom would let one lawyer's entry inherit another's diligence. Neither state blocks
    the act; the friction is one sentence naming the consequence, which costs nothing to the
    lawyer who actually read the document."""
    if opened_at_fr is None:
        return (
            "Vous n'avez pas ouvert cette pièce. Cette validation sera inscrite comme "
            "acceptée depuis la liste, non comme lue.")
    return (
        f"Vous avez ouvert cette pièce le {opened_at_fr}. Cette validation sera inscrite "
        "comme lue.")


# ── the values accepted (FR-45, AD-23) ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AcceptedValues:
    """The tool's assessment of a *pièce*, as the surface showed it at the moment of the act.

    FR-45 requires the entry to carry *"the values accepted"*. These are the four the triage table
    shows — the side derived from the line and the pins, the cascade's band and confidence, and the
    taxonomy label — and they travel with the *ranking version* under which they were produced. A
    set of values with no version named would be a verdict with no referent, which AD-23 forbids
    everywhere else in the product and would be most damaging here."""

    ranking_version_id: str
    side: str
    label: str
    band: str | None = None
    confidence: float | None = None


# ── one entry, and the view over the ledger (FR-45, AD-7/AD-39) ───────────────────────────────


@dataclass(frozen=True)
class ValidationEntry:
    """One row of a *pièce*'s validation ledger, as the domain reads it.

    ``opened_at`` is the timestamp of the acting lawyer's most recent open **strictly before** this
    act, or ``None``. ``batch_id`` is ``None`` for an individual act; a bulk act carries the shared
    identifier and the size of the set it was one gesture over (FR-45)."""

    piece_id: str
    seq: int
    action: str
    actor: str
    at: datetime
    ranking_version_id: str
    opened_at: datetime | None = None
    batch_id: str | None = None
    batch_size: int | None = None
    accepted: AcceptedValues | None = None

    def __post_init__(self) -> None:
        check_action(self.action)
        if (self.batch_id is None) != (self.batch_size is None):
            raise ValueError(
                "a batch is identified and sized together: a size with no identifier cannot be "
                "grouped, and an identifier with no size cannot answer 'one gesture over how many'")
        if self.action == ACTION_VALIDATED and self.accepted is None:
            raise ValueError(
                "a validation act accepts values (FR-45) — an entry with none recorded would be an "
                "acceptance of nothing in particular")
        if self.action == ACTION_WITHDRAWN and self.accepted is not None:
            raise ValueError("a withdrawal accepts nothing; it names the acceptance it withdraws")

    @property
    def provenance(self) -> Provenance:
        return Provenance.of(self.opened_at)

    @property
    def in_bulk(self) -> bool:
        return self.batch_id is not None

    @property
    def is_validation(self) -> bool:
        return self.action == ACTION_VALIDATED


def in_force(entries: tuple[ValidationEntry, ...]) -> ValidationEntry | None:
    """The validation currently in force for one *pièce*, or ``None``.

    The **max-seq view** over an append-only ledger — the *pin* precedent (AD-7/AD-39), and never a
    stored membership. A withdrawal lifts the validation exactly as a removal lifts a pin: the
    entry is still there, still readable, still in the export, and no longer in force. "Never
    validated" and "validated then withdrawn" are different facts and the ledger keeps both."""
    if not entries:
        return None
    latest = max(entries, key=lambda e: e.seq)
    return latest if latest.is_validation else None


def is_stale(entry: ValidationEntry, current_ranking_version_id: str | None) -> bool:
    """Whether the acceptance refers to an assessment that is no longer the one shown (AD-23).

    **Not an invalidation.** The act happened, it is in the record, and nothing erases it. This
    says only that what she accepted and what the screen shows today are not the same object —
    which is the same rule the whole product runs on, and the one place where letting a green tick
    survive a re-rank would put a stale acceptance in front of a *bâtonnier* as a current one."""
    if current_ranking_version_id is None:
        return False
    return entry.ranking_version_id != current_ranking_version_id


# ── the bulk gesture (FR-45) ──────────────────────────────────────────────────────────────────


class BatchCountMismatch(ValueError):
    """The confirmation did not name the set it was about to act on. Refused: FR-45(a) requires
    *"an explicit confirmation naming the count"*, and a count that does not match the selection is
    not a confirmation of this act — it is a confirmation of a different one."""


def check_confirmed_count(selected: int, confirmed: int) -> int:
    """FR-45(a) — the confirmation names the count, and the count is the one being acted on.

    Guards the case a dialog cannot: a selection that changed between the confirmation being shown
    and the act being committed. The lawyer confirmed *180 pièces*; if 181 arrive, she has not
    confirmed them."""
    if selected != confirmed:
        raise BatchCountMismatch(
            f"the confirmation named {confirmed} pièce(s) and the act covers {selected} — a count "
            "that does not match the selection confirms a different act")
    return selected


@dataclass(frozen=True)
class BatchSplit:
    """What a bulk confirmation must state: the count **and** the split (FR-45).

    A confirmation naming only the total is friction that obtains consent while telling the lawyer
    nothing she did not already know. The split is the information — how many of the set she has
    opened, and therefore how many entries will read *accepted from the list* rather than *read*."""

    total: int
    opened: int

    @property
    def not_opened(self) -> int:
        return self.total - self.opened

    def sentence_fr(self) -> str:
        """The consequence, in the lawyer's language, before anything is written."""
        if self.opened == 0:
            return (
                f"Vous n'en avez ouvert aucune. Les {self.total} seront inscrites comme "
                "acceptées depuis la liste, jamais comme lues.")
        if self.not_opened == 0:
            return f"Vous les avez toutes ouvertes. Les {self.total} seront inscrites comme lues."
        return (
            f"Vous en avez ouvert {self.opened}. Les {self.not_opened} autres seront inscrites "
            "comme acceptées depuis la liste, jamais comme lues.")


# ── the counts the export prints (FR-26 §7/§8, FR-45(d), §13 q.5) ─────────────────────────────


@dataclass(frozen=True)
class ValidationCounts:
    """§7 of the exported record, and the accepted half of §8.

    **The two registers are never pooled.** FR-45(d) requires bulk to be *"counted and reported
    separately"*, and §13's question 5 asks whether the act was performed individually or as part
    of a bulk gesture and over how many. A reader of the export must always be able to tell 12
    individual judgements from one gesture over 168; a single "validated" total would make that
    impossible while looking complete."""

    #: validations in force, whose acting lawyer had opened the pièce first
    read: int = 0
    #: validations in force, accepted without the pièce having been opened by that lawyer
    from_the_list: int = 0
    #: of the in-force validations, how many were committed as part of a bulk gesture
    in_bulk: int = 0
    #: distinct batches behind ``in_bulk`` — one gesture over many is one batch, not many gestures
    batches: int = 0
    #: validations that were withdrawn (FR-45's reversal); the entries remain readable
    withdrawn: int = 0
    #: pièces in the matter's ranked set with no validation in force
    never_validated: int = 0

    @property
    def in_force(self) -> int:
        return self.read + self.from_the_list

    @property
    def individually(self) -> int:
        return self.in_force - self.in_bulk
