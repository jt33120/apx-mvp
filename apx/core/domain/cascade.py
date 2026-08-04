"""The relevance-judgement cascade — its domain vocabulary (Story 4.2, FR-38/AD-18/AD-19/AD-36).

A pièce's relevance is assessed by a **three-stage gate**, not an LLM call each: (1) deterministic
filters + near-duplicate grouping, (2) cheap semantic scoring, (3) an LLM judgement on **only** the
uncertain band the cheap stages could not separate, plus a mandatory calibration sample of the
confident bands. This module is the pure vocabulary the orchestrator (`core/app/cascade.py`) and a
later ranking act (Story 4.3) speak; it stores nothing.

The load-bearing invariant is **AD-36 / AD-19 — two sets, never a third**: at all times a pièce is
in exactly one of the *ranked order* (carrying an enumerated **rejection class** when a cheap filter
kept it out of judgement) or the explicit **UNSCORED** set (its judgement *failed*, AD-19). A
stage-1/2 rejection is NOT unscored — it stays in the order with its class. UNSCORED holds only
judgement failures: a pièce the model could not judge is **never scored zero, never ranked last,
never dropped** from the population a future *confidence bound* reports on.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum


class Stage(IntEnum):
    """The cascade stage a pièce reached before its outcome was decided."""

    STAGE_1 = 1  # deterministic filters + near-duplicate family grouping
    STAGE_2 = 2  # cheap semantic scoring over the FR-9 embeddings
    STAGE_3 = 3  # the LLM judgement — only the uncertain band + a calibration sample


class Band(StrEnum):
    """The stage-2 band a scored pièce falls in. The uncertain band is what stage 3 judges."""

    CONFIDENT_RELEVANT = "confident-relevant"
    UNCERTAIN = "uncertain"
    CONFIDENT_DISCARD = "confident-discard"


class RejectionClass(StrEnum):
    """AD-36: the enumerated reason a cheap filter kept a pièce OUT OF JUDGEMENT. A rejected pièce
    stays IN the ranked order carrying this class — it is NEVER in the unscored set. **Append-only**
    (a persisted class string must always decode, like ``failures.ErrorClass``): a value is never
    renamed or removed once shipped. Story 4.2 decides only the near-duplicate class; the rest are
    reserved for the stage-1 filters that need structured metadata not yet extracted (document type,
    participant roles, dates against the case-theory period)."""

    EXACT_DUPLICATE_MEMBER = "exact-duplicate-member"  # a non-representative member of a family
    # ── reserved (declared now so a later story adds the filter without a schema change) ──
    OUT_OF_PERIOD = "out-of-period"          # date outside the case-theory period (needs a period)
    NON_MATCHING_TYPE = "non-matching-type"  # a document type the filter excludes
    NON_PARTICIPANT = "non-participant"      # none of the case-theory's participant roles
    OBVIOUS_NOISE = "obvious-noise"          # boilerplate / auto-generated noise


class IntrinsicSignal(StrEnum):
    """FR-38: the enumerated, named intrinsic signals a ranking is relative to **where no case
    theory exists** — every artefact from such a ranking states none was given and names these."""

    DOCUMENT_TYPE = "document-type"
    PARTICIPANT_ROLES = "participant-roles"
    DATE_DISTRIBUTION = "date-distribution"
    DUPLICATION = "duplication"
    OBVIOUS_NOISE = "obvious-noise"


INTRINSIC_SIGNALS: tuple[IntrinsicSignal, ...] = tuple(IntrinsicSignal)


class Outcome(StrEnum):
    """The tag of a pièce's cascade outcome — exhaustive and mutually exclusive (AD-36/AD-19)."""

    JUDGED = "judged"        # in the order, with a band (and, if it reached stage 3, a label)
    REJECTED = "rejected"    # in the order, kept out of judgement with a rejection class (AD-36)
    UNSCORED = "unscored"    # OUT of the order — the judgement FAILED (AD-19), never imputed


@dataclass(frozen=True)
class CascadeUnit:
    """One input pièce for the cascade: its identity, the text a judge would read, and the chunk ids
    (its retained-extract candidates). ``text`` derives the near-duplicate key; the cascade persists
    nothing, so this is a pure input carrier."""

    piece_id: str
    text: str
    chunk_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class PieceJudgement:
    """One pièce's cascade outcome — a tagged union over ``outcome`` (AD-36/AD-19). Exactly the
    fields of the tag are set; ``__post_init__`` enforces exhaustiveness + mutual exclusion so a
    pièce can never be simultaneously judged and unscored, or rejected without a class."""

    piece_id: str
    family_id: str
    is_representative: bool
    stage_reached: Stage
    outcome: Outcome
    # JUDGED — in the order; a band always, a semantic score where one was computed (None for the
    # intrinsic path), a stage-3 label only if it reached the LLM, and the extracts the judge used.
    score: float | None = None
    band: Band | None = None
    label: str | None = None
    retained_extract_chunk_ids: tuple[str, ...] = ()
    # REJECTED — in the order, kept out of judgement with an AD-36 class.
    rejection_class: RejectionClass | None = None
    # UNSCORED — out of the order; the judgement failed (AD-19), with a redacted reason.
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.outcome is Outcome.JUDGED:
            if self.band is None:
                raise ValueError("a judged pièce must carry a band")
            if self.rejection_class is not None or self.failure_reason is not None:
                raise ValueError("a judged pièce carries no rejection_class / failure_reason")
        elif self.outcome is Outcome.REJECTED:
            if self.rejection_class is None:
                raise ValueError("a rejected pièce must carry a rejection_class (AD-36)")
            if self.score is not None or self.band is not None or self.label is not None \
                    or self.failure_reason is not None:
                raise ValueError("a rejected pièce carries no score/band/label/failure_reason")
        elif self.outcome is Outcome.UNSCORED:
            if self.failure_reason is None:
                raise ValueError("an unscored pièce must carry a failure_reason (AD-19)")
            if self.score is not None or self.band is not None or self.label is not None \
                    or self.rejection_class is not None:
                raise ValueError(
                    "an unscored pièce is never imputed a score/band/label (AD-19) and is not "
                    "a rejection")

    @classmethod
    def judged(cls, *, piece_id: str, family_id: str, is_representative: bool, stage_reached: Stage,
               band: Band, score: float | None = None, label: str | None = None,
               retained_extract_chunk_ids: tuple[str, ...] = ()) -> PieceJudgement:
        return cls(piece_id, family_id, is_representative, stage_reached, Outcome.JUDGED,
                   score=score, band=band, label=label,
                   retained_extract_chunk_ids=retained_extract_chunk_ids)

    @classmethod
    def rejected(cls, *, piece_id: str, family_id: str, is_representative: bool,
                 stage_reached: Stage, rejection_class: RejectionClass) -> PieceJudgement:
        return cls(piece_id, family_id, is_representative, stage_reached, Outcome.REJECTED,
                   rejection_class=rejection_class)

    @classmethod
    def unscored(cls, *, piece_id: str, family_id: str, is_representative: bool,
                 failure_reason: str) -> PieceJudgement:
        return cls(piece_id, family_id, is_representative, Stage.STAGE_3, Outcome.UNSCORED,
                   failure_reason=failure_reason)


@dataclass(frozen=True)
class CascadeResult:
    """The outcome of one cascade run over a matter's pièces — pure data (Story 4.3 persists it
    against a ranking version). Carries the per-pièce judgements, the near-duplicate ``families``
    (id → member ids), the **UNSCORED** set as its own named count (AD-36), the **SM-18**
    ``stage3_share`` (the
    number that decides cost/latency/egress), whether it exceeds the configured ceiling, and the
    ``basis`` the judgement was relative to (a case theory, or the named intrinsic signals)."""

    judgements: tuple[PieceJudgement, ...]
    families: Mapping[str, tuple[str, ...]]
    unscored: tuple[str, ...]
    stage3_share: float
    over_stage3_floor: bool
    basis: str  # "case-theory" | "intrinsic"
    intrinsic_signals: tuple[IntrinsicSignal, ...] = field(default_factory=tuple)

    def is_consistent(self) -> bool:
        """The unscored set is exactly the pièces whose outcome is UNSCORED — no imputation, no
        double-membership (AD-36/AD-19)."""
        unscored_outcomes = {j.piece_id for j in self.judgements if j.outcome is Outcome.UNSCORED}
        return set(self.unscored) == unscored_outcomes

    @property
    def in_order(self) -> tuple[PieceJudgement, ...]:
        """The pièces IN the ranked order — judged + rejected, never unscored (AD-36)."""
        return tuple(j for j in self.judgements if j.outcome is not Outcome.UNSCORED)
