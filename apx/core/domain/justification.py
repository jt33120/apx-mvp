"""Per-pièce justification derived from named evidence (Story 4.6, FR-41 / FR-18 / FR-11).

A justification says, in one line, **why** a *pièce* is where it is — but the sentence is a model's
summary, **not** the evidence. The evidence is **named**: the specific *retained extracts* the
*relevance judgement* used (each a *chunk* identifier + the exact quoted passage), or — on the
intrinsic path — the named intrinsic signals. **The checkable part is the named evidence**; a
justification cannot exist without it (R-11 is mitigated by making the checkable part structural,
not by asserting the sentence is good).

At **show** time every named extract is re-verified by **exact containment** against its source
(FR-11): an extract that no longer resolves is surfaced as **unverified**, never as ordinary. This
module owns the value object, the assembly from a cascade judgement, and the pure show-time
verification — the containment resolver is **injected** (the store supplies its scope-gated
``resolve_chunk`` with ``expected_text``); the domain rebuilds nothing.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from apx.core.domain.cascade import IntrinsicSignal, Outcome, PieceJudgement, Stage
from apx.core.domain.chunking import FailedResolution, ResolvedPassage
from apx.core.domain.piece_confidence import ConfidenceSignal

BASIS_CASE_THEORY = "case-theory"
BASIS_INTRINSIC = "intrinsic"


@dataclass(frozen=True)
class JustificationBasis:
    """The **stated input set** a justification was derived FROM, named (FR-41): either a *case
    theory* version (the ``case-theory`` kind, carrying its version id) or the named intrinsic
    signals (the ``intrinsic`` kind, FR-38). Never free text — the basis is auditable and
    reproducible from the *ranking version* (Story 4.3). ``__post_init__`` enforces the tag."""

    kind: str
    case_theory_version_id: str | None = None
    intrinsic_signals: tuple[IntrinsicSignal, ...] = ()

    def __post_init__(self) -> None:
        if self.kind == BASIS_CASE_THEORY:
            if not self.case_theory_version_id:
                raise ValueError("a case-theory basis names its case-theory version id")
            if self.intrinsic_signals:
                raise ValueError("a case-theory basis carries no intrinsic signals")
        elif self.kind == BASIS_INTRINSIC:
            if not self.intrinsic_signals:
                raise ValueError("an intrinsic basis names at least one intrinsic signal (FR-38)")
            if self.case_theory_version_id is not None:
                raise ValueError("an intrinsic basis carries no case-theory version id")
        else:
            raise ValueError(f"unknown justification basis kind: {self.kind!r}")

    @property
    def named(self) -> str:
        """The basis rendered as a stable, non-content string (``case-theory:<id>`` |
        ``intrinsic:<named signals>``) — the same shape as a line/ranking ``basis``."""
        if self.kind == BASIS_CASE_THEORY:
            return f"case-theory:{self.case_theory_version_id}"
        return "intrinsic:" + ",".join(s.value for s in self.intrinsic_signals)

    @classmethod
    def case_theory(cls, version_id: str) -> JustificationBasis:
        return cls(BASIS_CASE_THEORY, case_theory_version_id=version_id)

    @classmethod
    def intrinsic(cls, signals: tuple[IntrinsicSignal, ...]) -> JustificationBasis:
        return cls(BASIS_INTRINSIC, intrinsic_signals=tuple(signals))


@dataclass(frozen=True)
class EvidenceExtract:
    """One **named retained extract**: the *chunk* identity the judgement used (``chunk_id``) and
    the exact quoted passage (``quoted_text``) that gets exact-containment-checked at show time
    (FR-11/FR-41). The quote is what detects the source text changing under the extract."""

    chunk_id: str
    quoted_text: str


def validate_named_evidence(
    sentence: str, basis: JustificationBasis, evidence: tuple[EvidenceExtract, ...]
) -> None:
    """The FR-41 invariant, callable at a **write seam** before anything is persisted (mirrors
    ``pin.validate_pin_reason``): a justification carries a one-line sentence and **names checkable
    evidence** — retained extracts, or an intrinsic basis with ≥1 named signal — and every named
    extract carries a non-empty quote (an empty quote would pass containment vacuously, so it is
    not evidence). :class:`Justification` delegates its ``__post_init__`` here, so the write seam
    and the read path enforce ONE invariant: a persisted justification is always readable."""
    if not sentence or not sentence.strip():
        raise ValueError("a justification carries a one-line sentence")
    if any(not e.quoted_text for e in evidence):
        raise ValueError(
            "a named extract carries the quoted passage it is checked against — an empty quote "
            "would satisfy containment vacuously (FR-41/FR-11)")
    names_evidence = bool(evidence) or (
        basis.kind == BASIS_INTRINSIC and bool(basis.intrinsic_signals))
    if not names_evidence:
        raise ValueError(
            "a justification must name checkable evidence — retained extracts or named "
            "intrinsic signals; the sentence alone is never a justification (FR-41)")


@dataclass(frozen=True)
class Justification:
    """A per-*pièce* justification (FR-18/FR-41): a one-line ``sentence`` (a model **summary**, NOT
    the evidence), derived from a stated ``basis`` (named), backed by **named** ``evidence``
    extracts, in an optional ``source_language``, carrying the **derived** ``confidence`` (Story 4.4
    — ``None`` when not derived, never imputed).

    **Invariant (the R-11 mitigation, made structural):** a justification **names checkable
    evidence** — ``evidence`` is non-empty, OR the ``basis`` is intrinsic with ≥1 named signal. A
    justification whose only content is its ``sentence`` cannot be constructed. The rule lives in
    :func:`validate_named_evidence` so the **write seam runs it too** (a persisted justification is
    always readable — the review's confirmed finding). Enforced further by the structural check
    ``justification_names_its_evidence`` (single construction site + a validating write seam)."""

    piece_id: str
    sentence: str
    basis: JustificationBasis
    evidence: tuple[EvidenceExtract, ...]
    source_language: str | None = None
    confidence: float | None = None
    confidence_signals: tuple[ConfidenceSignal, ...] = ()

    def __post_init__(self) -> None:
        validate_named_evidence(self.sentence, self.basis, self.evidence)


def build_justification(
    judgement: PieceJudgement, *, sentence: str, basis: JustificationBasis,
    evidence: tuple[EvidenceExtract, ...], source_language: str | None = None,
    confidence: float | None = None, confidence_signals: tuple[ConfidenceSignal, ...] = (),
) -> Justification | None:
    """Assemble a justification from a **stage-3 judged** *pièce* — the pièces the LLM actually
    judged, whose ``retained_extract_chunk_ids`` name the extracts it used (``cascade.py``). Returns
    ``None`` when there is nothing to derive: not stage-3 judged, or (case-theory path) no named
    extracts — a *pièce* with no derivable justification is shown as such, **never imputed**
    (mirrors ``derive_confidence`` → ``None``, AD-19). Refuses (``ValueError``) evidence that is not
    a subset of the extracts the judgement used, so persisted evidence is exactly what it relied
    on."""
    if judgement.outcome is not Outcome.JUDGED or judgement.stage_reached is not Stage.STAGE_3:
        return None
    used = set(judgement.retained_extract_chunk_ids)
    if not {e.chunk_id for e in evidence} <= used:
        raise ValueError(
            "a justification's evidence must be extracts the judgement used "
            "(retained_extract_chunk_ids)")
    if basis.kind == BASIS_CASE_THEORY and not evidence:
        return None  # a case-theory justification with no named extracts has no checkable evidence
    return Justification(
        piece_id=judgement.piece_id, sentence=sentence, basis=basis, evidence=evidence,
        source_language=source_language, confidence=confidence,
        confidence_signals=confidence_signals)


def rebuild_justification(
    *, piece_id: str, sentence: str, basis_kind: str, case_theory_version_id: str | None,
    intrinsic_signals: tuple[str, ...], evidence: tuple[tuple[str, str], ...],
    source_language: str | None, confidence: float | None,
    confidence_signals: tuple[str, ...],
) -> Justification:
    """Reconstruct a persisted justification from its stored primitives (the store's read seam) —
    the ONLY reconstruction path, so ``Justification`` is still built in exactly one module
    (``justification_names_its_evidence``). The invariant re-runs, so a persisted justification that
    somehow lost its named evidence is refused on read, never shown as ordinary."""
    if basis_kind == BASIS_CASE_THEORY:
        basis = JustificationBasis.case_theory(case_theory_version_id or "")
    else:
        basis = JustificationBasis.intrinsic(
            tuple(IntrinsicSignal(s) for s in intrinsic_signals))
    extracts = tuple(EvidenceExtract(chunk_id, quoted_text) for chunk_id, quoted_text in evidence)
    return Justification(
        piece_id=piece_id, sentence=sentence, basis=basis, evidence=extracts,
        source_language=source_language, confidence=confidence,
        confidence_signals=tuple(ConfidenceSignal(s) for s in confidence_signals))


@dataclass(frozen=True)
class ExtractVerification:
    """One named extract, re-verified at **show time** (FR-11): ``verified`` is the
    exact-containment result; ``cause`` is the enumerated resolution-failure cause when it did not
    resolve (else ``None``)."""

    chunk_id: str
    verified: bool
    cause: str | None = None


@dataclass(frozen=True)
class VerifiedJustification:
    """A justification **as shown** (FR-41/FR-11): the ``justification``, each named extract's
    show-time verification, and whether the tool's assessment for this *pièce* has been ``rejected``
    (set aside, reversibly — FR-18).

    ``is_unverified`` is True when there ARE named extracts and **at least one** failed containment
    — such a justification is shown **unverified**, never as ordinary. An intrinsic-only
    justification (no extracts) is **not** "unverified": its named signals are its checkable part,
    not a containment claim."""

    justification: Justification
    extracts: tuple[ExtractVerification, ...]
    rejected: bool = False

    @property
    def is_unverified(self) -> bool:
        return bool(self.extracts) and any(not e.verified for e in self.extracts)


def verify_justification(
    justification: Justification,
    resolve: Callable[[str, str], ResolvedPassage | FailedResolution],
    *, rejected: bool = False,
) -> VerifiedJustification:
    """Verify **every** named extract by exact containment at show time (FR-11): for each
    :class:`EvidenceExtract`, call ``resolve(chunk_id, quoted_text)`` (the store's scope-gated
    ``resolve_chunk`` with ``expected_text``). A :class:`FailedResolution` ⇒ the extract is
    unverified, carrying its cause; a :class:`ResolvedPassage` ⇒ verified. Pure — the resolver is
    injected, so the domain neither reads the store nor re-implements containment."""
    checks: list[ExtractVerification] = []
    for extract in justification.evidence:
        outcome = resolve(extract.chunk_id, extract.quoted_text)
        if isinstance(outcome, FailedResolution):
            checks.append(ExtractVerification(extract.chunk_id, False, outcome.cause))
        else:
            checks.append(ExtractVerification(extract.chunk_id, True, None))
    return VerifiedJustification(justification, tuple(checks), rejected=rejected)


def source_language_note(justification: Justification, *, interface_language: str) -> str | None:
    """The source *pièce*'s language, stated **only where it differs** from the interface language
    (FR-41/FR-36); ``None`` when it is unknown or equal (no note is made)."""
    src = justification.source_language
    if src is None or src == interface_language:
        return None
    return src
