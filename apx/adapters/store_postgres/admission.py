"""Corpus admission with embedding (Story 2.8) — the single seam both ingestion paths call.

Embedding is a precondition of corpus admission (FR-9/AD-11): :func:`admit` embeds each extracted
piece BEFORE persistence (:func:`apx.core.app.embedding.embed_result`), so an embedder failure
lands the piece in the *failure register* with its class — never a ``Piece``, never a ``Chunk`` —
and the *denominator* stays consistent (Story 2.7). It then persists the survivors and writes their
passage chunks (Story 2.9) through the single ``write_chunk`` seam. Both the async worker
(``queue._persist_unit``) and the synchronous API (``api.app._persist``) route through here, so the
embed-before-admit contract holds identically on every path (AD-16, one ingestion path).
"""

from __future__ import annotations

from apx.adapters.store_postgres.chunk_writer import ChunkStore
from apx.adapters.store_postgres.models import EMBEDDING_DIM
from apx.adapters.store_postgres.store import SaveOutcome, SqlStore
from apx.core.app.embedding import embed_result
from apx.core.app.ingest import SCHEMA_VERSION, IngestionResult
from apx.core.domain.chunking import chunking_config
from apx.core.ports.embedding import Embedder


def admit(
    store: SqlStore, embedder: Embedder, result: IngestionResult, *,
    scope: str, actor: str, matter: str, tenant: str, audit: bool,
    case_theory: str | None = None,
) -> SaveOutcome:
    """Embed, persist, and write chunks — the embed-before-admission seam (Story 2.8). Returns the
    ``SaveOutcome`` of the reshaped result (embed-failed pieces counted as register entries).

    Two disjointness guards keep a unit in EXACTLY ONE of corpus / register (SM-3, Story 2.7):
    (1) a pièce ALREADY in the corpus is NOT re-embedded — it has met the embed-precondition, so a
    re-embed failure on it would double-count it; it passes straight to ``save`` (a recognised
    no-op). (2) The chunk identity (``model_id``/``model_version``) is stamped from the EMBEDDER
    that produced the vector (AD-11 — detectability, never a config label that can diverge), and
    ``embed_result`` validates the vector WIDTH before ``save``, so ``write_chunk`` can never raise
    AFTER a pièce is admitted (which would orphan it in the corpus without a chunk)."""
    if embedder.dimensions != EMBEDDING_DIM:  # a mis-provisioned embedder halts loud, pre-write
        raise ValueError(
            f"embedder width {embedder.dimensions} != the halfvec column {EMBEDDING_DIM} (AD-11)")
    cfg = chunking_config(lambda k: store.get_config(tenant, k))  # config-as-data; version derived
    present = store.existing_piece_ids(tenant, matter, [p.id for p in result.pieces])
    new_pieces = [p for p in result.pieces if p.id not in present]
    already = [p for p in result.pieces if p.id in present]  # already admitted — skip re-embedding
    reshaped, embedded = embed_result(
        IngestionResult(pieces=new_pieces, failures=result.failures, exclusions=result.exclusions),
        embedder, chunking_config=cfg,
        model_id=embedder.model_id, model_version=embedder.model_version)
    outcome = store.save(
        IngestionResult(
            pieces=reshaped.pieces + already, failures=reshaped.failures,
            exclusions=reshaped.exclusions),
        scope, actor, matter=matter, tenant=tenant, case_theory=case_theory, audit=audit)
    # the one write_chunk seam — an embedded chunk per passage of each newly-admitted pièce (2.9)
    chunks = ChunkStore(
        store._sf, schema_version=SCHEMA_VERSION, chunking_config_version=cfg.version)
    for ec in embedded:
        chunks.write_chunk(
            ec.payload, rbac_scope=scope, vector=ec.vector,
            model_id=ec.model_id, model_version=ec.model_version)
    return outcome
