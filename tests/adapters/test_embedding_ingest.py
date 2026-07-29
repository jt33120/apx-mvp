"""The embedder fails loudly and admission couples with embedding (Story 2.8; FR-9/AD-11, SM-3).

Against the real SQLite store with a FAKE embedder injected at the port boundary (AD-11 — the real
model is never loaded): embedding is a precondition of corpus admission, so an embedder failure is
one open register entry with its class, no Piece and no Chunk; a success admits the piece WITH a
chunk carrying the embedding trio; the denominator stays consistent; a dimension mismatch halts the
unit and leaves the corpus intact. The real ``halfvec`` write/query is the Postgres leg.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.admission import admit
from apx.adapters.store_postgres.models import EMBEDDING_DIM, Base, Chunk
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.embedding import embed_result
from apx.core.app.ingest import SCHEMA_VERSION, IngestedPiece, IngestionResult
from apx.core.domain.identity import content_hash, piece_id
from apx.core.ports.embedding import EmbedderDimensionMismatch, EmbedderTimeout
from tests.embedding_fakes import FailingEmbedder, FakeEmbedder

TENANT, WALL = "t", "wall"


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def _piece(text: str, *, prov: str, matter: str = "m") -> IngestedPiece:
    ch = content_hash(text.encode())
    return IngestedPiece(
        id=piece_id(TENANT, ch, matter), matter=matter, tenant=TENANT, content_hash=ch,
        text_key=ch, provenance_path=prov, custodian="Dupont", extraction_method="text",
        extractor_version="v", schema_version=SCHEMA_VERSION,  # must match the ChunkStore stamp
        ingestion_timestamp=datetime.now(UTC), full_text=text, text_version="tv")


def _chunks(store: SqlStore) -> int:
    with store._sf() as s:
        return s.scalar(select(func.count()).select_from(Chunk)) or 0


class _WrongWidthEmbedder:
    """An embedder that returns a WRONG-width vector WITHOUT raising — the port ``dimensions`` says
    1024, but ``embed`` yields 512. ``embed_result`` must catch this before admission."""

    dimensions = EMBEDDING_DIM
    model_id = "wrong"
    model_version = "v"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 512 for _ in texts]


def _admit(store: SqlStore, embedder, result: IngestionResult) -> None:
    admit(store, embedder, result, scope=WALL, actor="avocat", matter="m", tenant=TENANT,
          audit=False)


# ── AC1 / AC5: a success is admitted WITH a chunk; a failure is a register entry, no chunk ──────

def test_embed_success_admits_with_a_chunk_and_failure_goes_to_register(store: SqlStore) -> None:
    # the embedder fails on piece "b" (a timeout), succeeds on "a"
    embedder = FailingEmbedder(EmbedderTimeout("slow"), fails_on=lambda t: t == "b")
    _admit(store, embedder, IngestionResult(
        pieces=[_piece("a", prov="a.txt"), _piece("b", prov="b.txt")]))
    inv = store.inventory("m", TENANT, {WALL})
    assert inv.in_corpus == 1 and inv.open_register_entries == 1 and inv.is_consistent()
    reg = store.register("m", TENANT, {WALL})
    assert [e.error_class for e in reg] == ["embedder-timeout"]  # the failed one, with its class
    assert reg[0].submitted_path == "b.txt"
    assert _chunks(store) == 1  # only the embedded pièce "a" produced a chunk (AC1: none for "b")


def test_a_whole_job_stays_consistent_under_a_transient_failure(store: SqlStore) -> None:
    # AC5: some indexed, the failed ones in the register, the denominator consistent throughout.
    embedder = FailingEmbedder(EmbedderTimeout("429"), fails_on=lambda t: t in ("b", "d"))
    _admit(store, embedder, IngestionResult(pieces=[
        _piece(t, prov=f"{t}.txt") for t in ("a", "b", "c", "d", "e")]))
    inv = store.inventory("m", TENANT, {WALL})
    assert inv.in_corpus == 3 and inv.open_register_entries == 2  # a,c,e indexed; b,d failed
    assert inv.submitted_pieces == 5 and inv.is_consistent()      # SM-3 holds
    assert _chunks(store) == 3


# ── AC4: a dimension mismatch halts the unit, leaves the corpus intact ───────────────────────────

def test_a_dimension_mismatch_halts_the_unit_and_leaves_the_corpus_intact(store: SqlStore) -> None:
    _admit(store, FakeEmbedder(), IngestionResult(pieces=[_piece("kept", prov="kept.txt")]))
    assert store.inventory("m", TENANT, {WALL}).in_corpus == 1   # an existing corpus pièce
    embedder = FailingEmbedder(EmbedderDimensionMismatch("512 != 1024"))
    _admit(store, embedder, IngestionResult(pieces=[_piece("bad", prov="bad.txt")]))
    inv = store.inventory("m", TENANT, {WALL})
    assert inv.in_corpus == 1 and inv.open_register_entries == 1  # the existing pièce is untouched
    assert store.register("m", TENANT, {WALL})[0].error_class == "embedder-dimension-mismatch"
    assert inv.is_consistent()


# ── AC5: the entry is retryable; a retry that re-embeds and still fails stays open with its class ─

def test_a_retry_that_still_fails_embedding_keeps_the_entry_open_with_its_class(
        store: SqlStore) -> None:
    # The register entry from an embedder failure is retryable (FR-5/2.6). A retry re-runs the FULL
    # ingest (re-extract + re-embed via the same seam); if the embedder is still down the pièce is a
    # failure again and the entry stays open, refreshed with the embedder class. A retry that
    # re-embeds SUCCESSFULLY resolves it and writes the chunk through the same admit seam — wired by
    # the retry handler with the worklist UX (Story 2.11), exactly as the retry HTTP surface itself
    # was deferred from Story 2.6.
    _admit(store, FailingEmbedder(EmbedderTimeout("down")),
           IngestionResult(pieces=[_piece("x", prov="x.txt")]))
    entry = store.register("m", TENANT, {WALL})[0]
    assert entry.retryable and entry.error_class == "embedder-timeout"

    def reingest() -> IngestionResult:  # re-extract + re-embed; the embedder is STILL down
        reshaped, _ = embed_result(
            IngestionResult(pieces=[_piece("x", prov="x.txt")]),
            FailingEmbedder(EmbedderTimeout("still down")),
            chunking_config_version="v1", model_id="bge-m3", model_version="v1")
        return reshaped

    out = store.retry_failure(entry.id, reingest, TENANT, {WALL}, actor="avocat")
    assert out.outcome == "still-failing"                        # stayed open, not clobbered
    assert store.inventory("m", TENANT, {WALL}).is_consistent()  # denominator still holds


# ── review fixes: disjointness under re-import + a bad-width vector; the embedder-sourced stamp ──

def test_reimporting_an_already_indexed_piece_during_an_outage_is_not_double_counted(
        store: SqlStore) -> None:
    # a pièce already in the corpus has met the embed-precondition; a re-import while the embedder
    # is DOWN must NOT re-register it (which would double-count it — in_corpus AND an open entry,
    # masked by the 2.7 watermark). Regression for the review HIGH.
    _admit(store, FakeEmbedder(), IngestionResult(pieces=[_piece("x", prov="x.txt")]))
    assert store.inventory("m", TENANT, {WALL}).in_corpus == 1
    _admit(store, FailingEmbedder(EmbedderTimeout("down")),
           IngestionResult(pieces=[_piece("x", prov="x.txt")]))       # same "x", embedder down
    inv = store.inventory("m", TENANT, {WALL})
    assert inv.in_corpus == 1 and inv.open_register_entries == 0 and inv.is_consistent()


def test_a_wrong_width_vector_is_a_register_entry_never_an_orphaned_corpus_piece(
        store: SqlStore) -> None:
    # a fake embedder returning a 512-dim vector (without raising) is caught BEFORE save, so the
    # pièce is a register entry — never a corpus pièce with no chunk (the review HIGH: write_chunk
    # must never raise after save admits the pièce).
    _admit(store, _WrongWidthEmbedder(), IngestionResult(pieces=[_piece("bad", prov="bad.txt")]))
    inv = store.inventory("m", TENANT, {WALL})
    assert inv.in_corpus == 0 and inv.open_register_entries == 1 and _chunks(store) == 0
    assert store.register("m", TENANT, {WALL})[0].error_class == "embedder-dimension-mismatch"
    assert inv.is_consistent()


def test_the_chunk_is_stamped_with_the_embedders_own_identity(store: SqlStore) -> None:
    # AD-11 detectability: the stamp is the embedder that PRODUCED the vector, not a config label.
    _admit(store, FakeEmbedder(), IngestionResult(pieces=[_piece("a", prov="a.txt")]))
    with store._sf() as s:
        chunk = s.scalars(select(Chunk)).first()
    assert chunk.model_id == "fake-embedder" and chunk.model_version == "fake-v1"
