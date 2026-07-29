"""Embedding as a precondition of corpus admission (Story 2.8, FR-9/AD-11).

The load-bearing decision: a *pièce* enters the *corpus* only when its embedding succeeds. Between
extraction and persistence, :func:`embed_result` embeds each extracted piece's (whole-piece)
chunk; on a typed :class:`EmbedderError` the piece is **moved from ``pieces`` to ``failures``**
(with the mapped error class), so an embed-failed pièce lands in the *failure register* — never in
the corpus, never a *chunk* — and the *denominator* stays consistent (`submitted == in_corpus +
open`, Story 2.7). On success the piece stays and yields its vector for the single ``write_chunk``
seam. Pure app orchestration over the ``Embedder`` port; persistence is the caller's (the adapter
seam), so the core imports no adapter (AD-4).

The chunking here is a **placeholder**: one chunk = the whole piece's ``full_text`` at position 0.
Real passage chunking with provenance is Story 2.9, which re-chunks under a new chunking-config
version and retires these by state (AD-40).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from apx.core.app.ingest import IngestedFailure, IngestedPiece, IngestionResult
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
    """One embedded whole-piece chunk ready for the single ``write_chunk`` seam: the payload (the
    frozen non-embedding provenance) plus the embedding trio (vector + the embedder identity)."""

    payload: PayloadRecord
    vector: list[float]
    model_id: str
    model_version: str


def _payload_for(piece: IngestedPiece, chunking_config_version: str) -> PayloadRecord:
    """Build the whole-piece chunk payload from an extracted piece (position 0). ``text_identity``
    is the sha256 of the full text — the same deterministic index the store computes for the piece
    row; ``piece_date`` is undetermined here (dating is a later story), mirroring the store."""
    return PayloadRecord(
        tenant=piece.tenant, matter=piece.matter, source_piece_id=piece.id,
        content_hash=piece.content_hash, provenance_path=piece.provenance_path,
        custodian=piece.custodian, extraction_method=piece.extraction_method,
        extractor_version=piece.extractor_version, schema_version=piece.schema_version,
        chunking_config_version=chunking_config_version,
        ingestion_timestamp=piece.ingestion_timestamp, position=0, full_text=piece.full_text,
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
    chunking_config_version: str, model_id: str, model_version: str,
) -> tuple[IngestionResult, list[EmbeddedChunk]]:
    """Embed each extracted piece BEFORE admission. Returns the reshaped result (embed-failed
    pieces moved to ``failures`` with their class) and the embedded chunks to write for the
    survivors. A raised ``EmbedderError`` — or an embedder that returns no vector for real text —
    lands the piece in the register (never the corpus, never a chunk)."""
    kept: list[IngestedPiece] = []
    failures: list[IngestedFailure] = list(result.failures)
    embedded: list[EmbeddedChunk] = []
    for piece in result.pieces:
        try:
            vectors = embedder.embed([piece.full_text])
        except EmbedderError as exc:
            failures.append(_failure_from(piece, error_class_for(exc), redacted_diagnostic(exc)))
            continue
        if not vectors:  # the port never fabricates a vector; none back for real text → halt
            failures.append(_failure_from(
                piece, ErrorClass.EMBEDDER_UNAVAILABLE, "the embedder returned no vector"))
            continue
        if len(vectors[0]) != embedder.dimensions:
            # a wrong-width vector is caught HERE, before admission, so write_chunk never raises
            # AFTER save commits the pièce (which would orphan it in the corpus, Story 2.8 fix).
            failures.append(_failure_from(
                piece, ErrorClass.EMBEDDER_DIMENSION_MISMATCH,
                f"the embedder returned a {len(vectors[0])}-dim vector"))
            continue
        kept.append(piece)
        embedded.append(EmbeddedChunk(
            payload=_payload_for(piece, chunking_config_version), vector=vectors[0],
            model_id=model_id, model_version=model_version))
    reshaped = IngestionResult(
        pieces=kept, failures=failures, exclusions=list(result.exclusions))
    return reshaped, embedded
