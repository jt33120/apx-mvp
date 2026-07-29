"""Embedding as a precondition of corpus admission (Story 2.8, FR-9/AD-11).

The load-bearing decision: a *pièce* enters the *corpus* only when its embedding succeeds. Between
extraction and persistence, :func:`embed_result` embeds each extracted piece's (whole-piece)
chunk; on a typed :class:`EmbedderError` the piece is **moved from ``pieces`` to ``failures``**
(with the mapped error class), so an embed-failed pièce lands in the *failure register* — never in
the corpus, never a *chunk* — and the *denominator* stays consistent (`submitted == in_corpus +
open`, Story 2.7). On success the piece stays and yields one vector per passage for the single
``write_chunk`` seam. Pure app orchestration over the ``Embedder`` port and the deterministic
chunker; persistence is the caller's (the adapter seam), so the core imports no adapter (AD-4).

The chunking is real passage chunking (Story 2.9, FR-11): :func:`embed_result` chunks each piece's
``full_text`` under the tenant's :class:`ChunkingConfig`, embeds **each passage's own text**, and
emits one chunk per passage at positions ``0..N-1``, each stamped with the config's derived version.
It is **all-or-nothing per pièce** (AC7): if any passage fails to embed, the WHOLE pièce is a
register entry with zero chunks — never a corpus pièce with partial provenance (the *denominator*
stays honest, Story 2.7). Provenance is by resolution: a chunk stores only ``position`` + the
versions, and the passage is recovered by re-chunking the stored full text (AD-9/AD-10).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from apx.core.app.ingest import IngestedFailure, IngestedPiece, IngestionResult
from apx.core.domain.chunking import ChunkingConfig, chunk
from apx.core.domain.failures import ErrorClass, redacted_diagnostic
from apx.core.domain.payload import PayloadRecord
from apx.core.ports.embedding import (
    Embedder,
    EmbedderAuthFailed,
    EmbedderDimensionMismatch,
    EmbedderError,
    EmbedderRateLimited,
    EmbedderTimeout,
    EmbedderUnavailable,
)

# Each port failure maps one-to-one to a register error class (FR-9). An unclassified embedder
# error is `unknown` with a redacted diagnostic (AD-28) — never dropped, never `str(exc)`.
_ERROR_CLASS: dict[type[EmbedderError], ErrorClass] = {
    EmbedderUnavailable: ErrorClass.EMBEDDER_UNAVAILABLE,
    EmbedderRateLimited: ErrorClass.EMBEDDER_RATE_LIMITED,
    EmbedderTimeout: ErrorClass.EMBEDDER_TIMEOUT,
    EmbedderDimensionMismatch: ErrorClass.EMBEDDER_DIMENSION_MISMATCH,
    EmbedderAuthFailed: ErrorClass.EMBEDDER_AUTH_FAILED,
}


def error_class_for(exc: EmbedderError) -> ErrorClass:
    """The register error class for an embedder failure (FR-9). Any unrecognised subclass is
    ``UNKNOWN`` — never dropped."""
    for cls, ec in _ERROR_CLASS.items():
        if isinstance(exc, cls):
            return ec
    return ErrorClass.UNKNOWN


@dataclass(frozen=True)
class EmbeddedChunk:
    """One embedded passage chunk ready for the single ``write_chunk`` seam: the payload (the frozen
    non-embedding provenance, its ``position`` the passage index) plus the embedding trio (the
    passage's vector + the embedder identity)."""

    payload: PayloadRecord
    vector: list[float]
    model_id: str
    model_version: str


def _payload_for(
    piece: IngestedPiece, chunking_config_version: str, position: int,
) -> PayloadRecord:
    """Build the chunk payload for one passage of an extracted piece (Story 2.9). Only ``position``
    varies across a piece's passages: ``full_text``/``text_identity``/``text_version`` stay the
    PIECE's (AD-10 — provenance to the one addressable full-text artefact the passage is resolved
    from), and ``text_identity`` is the sha256 of that full text (the store's deterministic index).
    ``piece_date`` is undetermined here (dating is a later story), mirroring the store."""
    return PayloadRecord(
        tenant=piece.tenant, matter=piece.matter, source_piece_id=piece.id,
        content_hash=piece.content_hash, provenance_path=piece.provenance_path,
        custodian=piece.custodian, extraction_method=piece.extraction_method,
        extractor_version=piece.extractor_version, schema_version=piece.schema_version,
        chunking_config_version=chunking_config_version,
        ingestion_timestamp=piece.ingestion_timestamp, position=position, full_text=piece.full_text,
        text_identity=hashlib.sha256(piece.full_text.encode()).hexdigest(),
        text_version=piece.text_version, piece_date=None, piece_date_status="undetermined",
    )


def _failure_from(piece: IngestedPiece, error_class: ErrorClass, detail: str) -> IngestedFailure:
    return IngestedFailure(
        filename=piece.provenance_path.replace("\\", "/").rsplit("/", 1)[-1],
        submitted_path=piece.provenance_path, matter=piece.matter, tenant=piece.tenant,
        error_class=error_class, detail=detail, custodian=piece.custodian)


def embed_result(
    result: IngestionResult, embedder: Embedder, *,
    chunking_config: ChunkingConfig, model_id: str, model_version: str,
) -> tuple[IngestionResult, list[EmbeddedChunk]]:
    """Chunk and embed each extracted piece BEFORE admission (Story 2.9). Returns the reshaped
    result (pieces that could not be fully chunked-and-embedded moved to ``failures`` with their
    class) and the embedded chunks to write for the survivors — one per passage at positions
    ``0..N-1``. **All-or-nothing per pièce** (AC7): a raised ``EmbedderError``, an empty extraction,
    a wrong vector count or a wrong-width vector lands the WHOLE pièce in the register — never the
    corpus, never a partial set of chunks (the denominator stays honest, Story 2.7)."""
    version = chunking_config.version
    kept: list[IngestedPiece] = []
    failures: list[IngestedFailure] = list(result.failures)
    embedded: list[EmbeddedChunk] = []
    for piece in result.pieces:
        passages = chunk(piece.full_text, chunking_config)
        if not passages or not piece.full_text.strip():
            # empty or whitespace-only extraction — nothing indexable, a register entry (never a
            # corpus chunk with a meaningless vector). Common blank text is caught upstream at
            # extraction; this is the seam's own backstop (and covers embed_result called outside
            # the extraction path). Exotic zero-width-only content is a documented LOW.
            failures.append(_failure_from(
                piece, ErrorClass.EXTRACTED_EMPTY, "the extracted text has no indexable content"))
            continue
        try:
            vectors = embedder.embed([p.text for p in passages])
        except EmbedderError as exc:
            failures.append(_failure_from(piece, error_class_for(exc), redacted_diagnostic(exc)))
            continue
        # the port never fabricates a vector: one per passage, each the column width, or the WHOLE
        # pièce halts here — before admission — so write_chunk never raises AFTER save commits the
        # pièce (which would orphan it in the corpus with partial provenance, the Story 2.8 fix).
        if len(vectors) != len(passages):
            failures.append(_failure_from(
                piece, ErrorClass.EMBEDDER_UNAVAILABLE,
                f"the embedder returned {len(vectors)} vectors for {len(passages)} passages"))
            continue
        if any(len(v) != embedder.dimensions for v in vectors):
            failures.append(_failure_from(
                piece, ErrorClass.EMBEDDER_DIMENSION_MISMATCH,
                "the embedder returned a wrong-width vector"))
            continue
        kept.append(piece)
        for position, vector in enumerate(vectors):
            embedded.append(EmbeddedChunk(
                payload=_payload_for(piece, version, position), vector=vector,
                model_id=model_id, model_version=model_version))
    reshaped = IngestionResult(
        pieces=kept, failures=failures, exclusions=list(result.exclusions))
    return reshaped, embedded
