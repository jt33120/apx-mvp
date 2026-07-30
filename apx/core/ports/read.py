"""The read-side port — scoped reads of *tenant* data (AD-14).

Every read of *tenant*-owned data has one entry point (``core/app/read/``), and the port it depends
on exposes **no method that accepts an identifier without a tenant and a scope argument** (AD-14).
Scope is a query **pre-filter** (AD-13), passed into the query — never a post-filter over a fetched
result set, which leaks silently. Story 3.1 adds the semantic-search method; the deterministic
engine (3.2) and the other reads (3.3) extend this port.
"""

from __future__ import annotations

from typing import Protocol

from apx.core.domain.retrieval import SemanticResult


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
