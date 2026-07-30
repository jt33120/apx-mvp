"""The PostgreSQL semantic-search query (Story 3.1, AD-13/AD-16).

A single SELECT: cosine nearest-neighbour over ``chunk.vector`` (the HNSW ``ix_chunk_vector_hnsw``
surface built in migration 0021), with the *RBAC scope* predicate **joined from the authoritative
``matter_scope`` as a pre-filter** (AD-13 — never denormalised onto the chunk row, so a re-scope
takes effect at the next query with nothing to propagate), *tenant* first (AD-12), a min-similarity
floor, ranked by distance, bounded by ``k``.

``<=>`` is pgvector's cosine distance; cosine **similarity** = ``1 - distance``. This is
PostgreSQL-native — on any other dialect ``halfvec`` degrades to JSON and the operator is
unavailable, exactly as the migrations are PG-only. Kept a pure statement builder so its shape is
asserted in CI by compiling to PostgreSQL SQL without a database.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from sqlalchemy import Float, Select, select

from apx.adapters.store_postgres.models import Chunk, MatterScope
from apx.core.domain.retrieval import SemanticResult


class _DistanceRow(Protocol):
    piece_id: str
    chunk_id: str
    distance: float


def results_from_rows(rows: Iterable[_DistanceRow]) -> list[SemanticResult]:
    """Map ``(piece_id, chunk_id, distance)`` rows to ranked ``SemanticResult``s. pgvector's ``<=>``
    is cosine **distance**, so cosine **similarity** = ``1 - distance``. Row order (nearest first)
    is preserved as the ranking."""
    return [
        SemanticResult(piece_id=r.piece_id, chunk_id=r.chunk_id, similarity=1.0 - float(r.distance))
        for r in rows
    ]


def semantic_search_stmt(
    *, tenant: str, scopes: set[str], query_vector: list[float], k: int, min_similarity: float
) -> Select:
    """Build the scoped top-``k`` cosine nearest-neighbour SELECT. Scope is a query pre-filter; the
    caller guarantees ``scopes`` is non-empty (an empty scope reads nothing — handled upstream)."""
    distance = Chunk.vector.op("<=>", return_type=Float)(query_vector)
    max_distance = 1.0 - min_similarity
    return (
        select(Chunk.piece_id, Chunk.chunk_id, distance.label("distance"))
        .join(
            MatterScope,
            (MatterScope.matter == Chunk.matter) & (MatterScope.tenant == Chunk.tenant),
        )
        .where(Chunk.tenant == tenant)
        # Pin BOTH sides of the Chinese wall to the caller's tenant literal (AD-12): the chunk's
        # tenant AND the joined matter_scope's tenant — defence-in-depth so the wall holds even if
        # the join's tenant-equality ever regressed (scope strings are not tenant-qualified).
        .where(MatterScope.tenant == tenant)
        .where(MatterScope.scope.in_(sorted(scopes)))   # the scope PRE-filter (AD-13)
        .where(distance <= max_distance)                # the min-similarity floor
        .order_by(distance)                             # nearest first (HNSW cosine)
        .limit(k)
    )
