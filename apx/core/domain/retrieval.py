"""The truth-status data contract for retrieval (Story 3.1 / AD-20).

*Truth status* is a property of the **result set**, carried in data — never derived from a
similarity threshold or any configuration. Two values only: **suggestive** (semantic, ranked,
top-k — supports a finding, can never prove an absence) and **exhaustive** (deterministic, the
complete match set over the whole indexed *corpus* within one scope — Story 3.2). The v1 defect
this design forbids: an off-corpus gate that was a similarity threshold shipped disabled by default,
a guess in the costume of a proof (``addendum.md`` §4).

The semantic engine's status is baked into its **type**: ``SuggestiveResultSet.truth_status`` is a
constant ``SUGGESTIVE``, ``init=False`` (no caller can supply it) and frozen (no code can reassign
it). The set carries a ``k`` and the ``similarity_threshold`` it ran under, and a wording token that
reads as a suggestion — it has **no** total/denominator field, because a *denominator* is a property
only an **exhaustive** set has. So no configuration can make a semantic set claim completeness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from apx.core.domain.inventory import Inventory


class TruthStatus(Enum):
    """The two truth statuses a result set can carry (AD-20), one constant per engine."""

    SUGGESTIVE = "suggestive"   # semantic, ranked, top-k — supports a finding, never proves absence
    EXHAUSTIVE = "exhaustive"   # deterministic, complete within one scope — carries a denominator


@dataclass(frozen=True)
class SemanticResult:
    """One ranked hit of a semantic search: the *pièce* it belongs to and the *chunk* that matched,
    plus its cosine similarity. The ``chunk_id`` is the openable handle — ``store.resolve_chunk``
    resolves it to the exact source passage on demand (FR-11 provenance, resolved not stored per
    AD-9); the span is never carried on the result."""

    piece_id: str
    chunk_id: str
    similarity: float


@dataclass(frozen=True)
class SuggestiveResultSet:
    """A semantic result set. ``truth_status`` is the **constant** ``SUGGESTIVE`` — set here, at
    this one site, never derived from a threshold or config (AD-20). It cannot express completeness:
    it carries ``k`` and the ``similarity_threshold`` it ran under, and a wording token that reads
    as a suggestion. A *denominator* is an exhaustive-only concept and has no field here."""

    results: tuple[SemanticResult, ...]
    k: int
    similarity_threshold: float
    truth_status: TruthStatus = field(default=TruthStatus.SUGGESTIVE, init=False)

    @property
    def wording(self) -> str:
        """A phrasing that cannot be read as completeness (AD-20)."""
        return f"top {self.k} of the corpus by similarity"


@dataclass(frozen=True)
class DeterministicResult:
    """One *pièce* matching an exact, normalised deterministic search: its *matter*, its *pièce*
    identity, and a snippet of where the term matched."""

    matter: str
    piece_id: str
    snippet: str


@dataclass(frozen=True)
class RegisterHit:
    """A name-match in the *failure register* — a *pièce* whose text is NOT in the searched set
    (AD-21). Returned visibly distinct and NEVER counted inside the exhaustive results."""

    matter: str
    filename: str
    error_class: str


@dataclass(frozen=True)
class ExhaustiveResultSet:
    """A deterministic result set (Story 3.2 / AD-20). ``truth_status`` is the **constant**
    ``EXHAUSTIVE`` — the second engine, set at its one site, never derived. It is the **complete**
    match set: it carries **no** ``limit``/``top_k``/page-size field, so it can never be truncated
    (a truncation would downgrade it to suggestive — AD-20). Its honesty is the ``denominator`` (the
    AD-38 six-field ``Inventory``, which itself carries the open-register and unknown-cardinality
    counts) plus the OCR-quality shares of the searched set (AD-42, as data). ``register_hits``
    are searched **separately** and are never inside ``results`` (AD-21). ``normalization`` declares
    the rule the search ran under (AD-21)."""

    results: tuple[DeterministicResult, ...]
    denominator: Inventory
    ocr_share: float                # the OCR-derived share of the searched set (AD-42)
    below_quality_share: float      # the share below the OCR quality signal (AD-42)
    register_hits: tuple[RegisterHit, ...]
    normalization: str
    truth_status: TruthStatus = field(default=TruthStatus.EXHAUSTIVE, init=False)
