"""The Postgres SemanticScorer adapter — the cascade's stage-2 (Story 4.2, FR-38 / AD-18 / AD-13).

Scores each pièce by the **maximum cosine** of its chunks to the embedded query (the case theory),
over the corpus embeddings (FR-9) — the cheap tier that lets stage 3 spend the LLM on only the
uncertain band. Scope is a **query pre-filter** joined from the authoritative ``matter_scope``
(AD-13), *tenant* pinned on both sides (AD-12). ``<=>`` is pgvector cosine **distance**, so the
score is ``1 - min(distance)``; this is PostgreSQL-native (halfvec), exactly like ``semantic_query``
— the pure statement builder's shape is asserted in CI by compiling to PostgreSQL SQL without a DB,
and a fake stands in for the behavioural tests.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from sqlalchemy import Float, Select, func, select
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import Chunk, MatterScope
from apx.core.ports.embedding import Embedder


def piece_scores_stmt(
    *, tenant: str, matter: str, scopes: set[str], query_vector: list[float],
    piece_ids: Sequence[str],
) -> Select:
    """Build the per-pièce max-cosine SELECT: group each pièce's chunks and take its minimum cosine
    distance (its best-matching chunk). Scope is a pre-filter (AD-13); the caller guarantees
    ``scopes`` and ``piece_ids`` are non-empty (an empty scope/set scores nothing — handled up)."""
    distance = Chunk.vector.op("<=>", return_type=Float)(query_vector)
    return (
        select(Chunk.piece_id, func.min(distance).label("dmin"))
        .join(
            MatterScope,
            (MatterScope.matter == Chunk.matter) & (MatterScope.tenant == Chunk.tenant),
        )
        .where(Chunk.tenant == tenant)
        .where(Chunk.matter == matter)
        # Pin BOTH sides of the wall to the caller's tenant literal (AD-12), and pre-filter the
        # scope from the authoritative matter_scope (AD-13) — never denormalised onto the chunk row.
        .where(MatterScope.tenant == tenant)
        .where(MatterScope.scope.in_(sorted(scopes)))
        .where(Chunk.piece_id.in_(list(piece_ids)))
        .group_by(Chunk.piece_id)
    )


class PgSemanticScorer:
    """The stage-2 scorer over PostgreSQL. Composes the ONE embedder (AD-11) — which embeds the
    query text — with the store session factory. A pièce with no scorable chunk is **absent** from
    the returned mapping (the cascade reads absence as no-signal, never a zero — AD-19)."""

    def __init__(self, session_factory: sessionmaker, embedder: Embedder) -> None:
        self._sf = session_factory
        self._embedder = embedder

    def score(
        self, *, tenant: str, matter: str, scopes: set[str], query_text: str,
        piece_ids: Sequence[str],
    ) -> Mapping[str, float]:
        ids = list(piece_ids)
        if not ids or not scopes:
            return {}
        query_vector = self._embedder.embed([query_text])[0]
        stmt = piece_scores_stmt(
            tenant=tenant, matter=matter, scopes=scopes, query_vector=query_vector, piece_ids=ids)
        with self._sf() as session:
            rows = session.execute(stmt).all()
        return {pid: 1.0 - float(dmin) for pid, dmin in rows}
