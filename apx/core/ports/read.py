"""The read-side port — scoped reads of *tenant* data (AD-14).

Every read of *tenant*-owned data has one entry point (``core/app/read/``), and the port it depends
on exposes **no method that accepts an identifier without a tenant and a scope argument** (AD-14).
Scope is a query **pre-filter** (AD-13), passed into the query — never a post-filter over a fetched
result set, which leaks silently. Story 3.1 adds the semantic-search method; the deterministic
engine (3.2) and the other reads (3.3) extend this port.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from apx.core.domain.inventory import Inventory
from apx.core.domain.retrieval import DeterministicResult, RegisterHit, SemanticResult


@dataclass(frozen=True)
class ExactSearch:
    """One snapshot of a deterministic exhaustive search (AD-20: computed in one snapshot). The
    COMPLETE match set, the register name-matches (searched separately, AD-21), the denominator,
    and the OCR-quality shares — everything the ``ExhaustiveResultSet`` carries as data (AD-42)."""

    results: list[DeterministicResult]
    register_hits: list[RegisterHit]
    denominator: Inventory
    ocr_share: float
    below_quality_share: float


class SemanticReader(Protocol):
    def search_semantic(
        self,
        *,
        tenant: str,
        scopes: set[str],
        query_vector: list[float],
        k: int,
        min_similarity: float,
    ) -> list[SemanticResult]:
        """Up to ``k`` chunks ranked by descending cosine similarity to ``query_vector``, each with
        similarity ``>= min_similarity``, with ``tenant`` and the ``scopes`` predicate applied as a
        query **pre-filter** (AD-12/AD-13). An empty ``scopes`` set returns ``[]`` — a caller with
        no scope reads nothing (fail-closed, AD-12). There is deliberately no identifier-only method
        and no result-set parameter (AD-14: scope is never a post-filter)."""
        ...


class ExactSearchReader(Protocol):
    def open_import_jobs(self, *, tenant: str, scopes: set[str]) -> list[str]:
        """The ids/names of open (not-done) import jobs for the in-scope *matters* — the engine
        refuses over a moving population (AD-20). Empty scope → ``[]``."""
        ...

    def exact_search(self, *, tenant: str, scopes: set[str], normalized_query: str) -> ExactSearch:
        """The COMPLETE normalised exact match over the scoped *corpus* — no limit/top-k (AD-20) —
        with ``tenant`` and ``scopes`` a query **pre-filter** (AD-13), plus the register matches,
        the AD-38 denominator and the OCR shares, all in one snapshot. There is no identifier-only
        method and no result-set post-filter (AD-14)."""
        ...
