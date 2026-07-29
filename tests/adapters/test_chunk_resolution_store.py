"""Store-backed chunk resolution — the provenance round-trip on real stored chunks (Story 2.9,
FR-11). A chunk admitted through the real seam resolves back to the exact passage the deterministic
chunker produces; a resolution that fails at read time is honest, scope-checked, and degrades its
container. SQLite with a fake embedder at the port boundary (the real model is never loaded).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.admission import admit
from apx.adapters.store_postgres.models import Base, Chunk, Piece
from apx.adapters.store_postgres.store import ScopeDenied, SqlStore
from apx.core.app.ingest import SCHEMA_VERSION, IngestedPiece, IngestionResult
from apx.core.domain.chunking import (
    CONTAINMENT_FAILED,
    PIECE_GONE,
    TEXT_CHANGED,
    FailedResolution,
    ResolvedPassage,
    chunk,
    chunking_config,
    is_degraded,
)
from apx.core.domain.config import ConfigError
from apx.core.domain.identity import content_hash, piece_id
from apx.core.ports.embedding import EmbedderTimeout
from tests.embedding_fakes import FailingEmbedder, FakeEmbedder

TENANT, WALL = "t", "wall"
# long enough to split into several passages under the default config (target 1200 chars)
_LONG = "Le contrat de bail commercial est nul et de nul effet. La cour le confirme enfin. " * 30
_PID = piece_id(TENANT, content_hash(_LONG.encode()), "m")


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def _piece(text: str) -> IngestedPiece:
    ch = content_hash(text.encode())
    return IngestedPiece(
        id=piece_id(TENANT, ch, "m"), matter="m", tenant=TENANT, content_hash=ch, text_key=ch,
        provenance_path="c.txt", custodian="Dupont", extraction_method="text",
        extractor_version="v", schema_version=SCHEMA_VERSION,
        ingestion_timestamp=datetime.now(UTC), full_text=text, text_version="tv")


def _admit(store: SqlStore, text: str) -> list[tuple[str, int]]:
    admit(store, FakeEmbedder(), IngestionResult(pieces=[_piece(text)]),
          scope=WALL, actor="a", matter="m", tenant=TENANT, audit=False)
    with store._sf() as s:
        return [(r.chunk_id, r.position)
                for r in s.scalars(select(Chunk).order_by(Chunk.position))]


def test_every_stored_chunk_resolves_to_its_exact_passage(store: SqlStore) -> None:
    ids = _admit(store, _LONG)
    assert len(ids) > 1  # the long text really produced several stored chunks
    passages = chunk(_LONG, chunking_config(lambda k: store.get_config(TENANT, k)))
    for cid, pos in ids:
        r = store.resolve_chunk(cid, TENANT, {WALL})
        assert isinstance(r, ResolvedPassage)
        assert (r.text, r.start, r.end) == \
            (passages[pos].text, passages[pos].start, passages[pos].end)
        assert _LONG[r.start:r.end] == r.text  # provenance to the character


def test_a_re_extraction_makes_the_old_chunk_resolve_as_text_changed(store: SqlStore) -> None:
    cid = _admit(store, _LONG)[0][0]
    with store._sf() as s, s.begin():  # a re-extraction: the pièce's text_version moves on (AD-40)
        s.get(Piece, _PID).text_version = "tv2"
    assert store.resolve_chunk(cid, TENANT, {WALL}) == FailedResolution(TEXT_CHANGED)


def test_a_gone_piece_resolves_as_piece_gone(store: SqlStore) -> None:
    cid = _admit(store, _LONG)[0][0]
    with store._sf() as s, s.begin():  # fault injection: a dangling chunk (its pièce row is gone)
        s.delete(s.get(Piece, _PID))
    assert store.resolve_chunk(cid, TENANT, {WALL}) == FailedResolution(PIECE_GONE)


def test_a_tampered_stored_extract_fails_containment(store: SqlStore) -> None:
    cid = _admit(store, _LONG)[0][0]
    r = store.resolve_chunk(cid, TENANT, {WALL}, expected_text="clause jamais ecrite ici")
    assert r == FailedResolution(CONTAINMENT_FAILED)


def test_resolution_is_scope_checked_and_discloses_nothing(store: SqlStore) -> None:
    # review MED-2: an out-of-scope caller is refused WITHOUT the exception disclosing the matter,
    # or that the chunk exists. The arg echoes ONLY the caller-supplied chunk_id, same shape as the
    # unknown-chunk branch, so there is no existence oracle and no cross-wall matter leak (AD-13).
    cid = _admit(store, _LONG)[0][0]
    with pytest.raises(ScopeDenied) as forbidden:
        store.resolve_chunk(cid, TENANT, {"another-wall"})
    assert str(forbidden.value) == cid                       # the id we passed, never the matter
    with pytest.raises(ScopeDenied) as unknown:
        store.resolve_chunk("no-such-chunk", TENANT, {WALL})
    assert str(unknown.value) == "no-such-chunk"             # same shape → indistinguishable


def test_chunking_config_is_immutable_once_a_corpus_exists(store: SqlStore) -> None:
    # review MED-1 (AD-40): the chunking config is editable before any corpus, then frozen — a
    # change once chunks exist would strand them all as config-superseded, so it is refused.
    store.set_config(TENANT, "admin", "chunking_target_chars", 800)  # no corpus yet → allowed
    _admit(store, _LONG)                                              # a corpus now exists
    with pytest.raises(ConfigError, match="immutable once a corpus"):
        store.set_config(TENANT, "admin", "chunking_target_chars", 900)


def test_a_multi_passage_partial_embed_failure_fails_the_whole_piece_in_the_store(
    store: SqlStore,
) -> None:
    # AC7 at the STORE level (the 2.8-review pattern): a multi-passage pièce whose 2nd passage fails
    # to embed is ONE register entry, in_corpus=0, ZERO chunks — assert the three counts
    # independently, since is_consistent() alone can be masked by the 2.7 watermark tautology.
    passages = chunk(_LONG, chunking_config(lambda k: store.get_config(TENANT, k)))
    assert len(passages) > 1
    embedder = FailingEmbedder(EmbedderTimeout("x"), fails_on=lambda t: t == passages[1].text)
    admit(store, embedder, IngestionResult(pieces=[_piece(_LONG)]),
          scope=WALL, actor="a", matter="m", tenant=TENANT, audit=False)
    inv = store.inventory("m", TENANT, {WALL})
    with store._sf() as s:
        n_chunks = s.scalar(select(func.count()).select_from(Chunk)) or 0
    assert inv.in_corpus == 0 and inv.open_register_entries == 1 and n_chunks == 0
    assert inv.is_consistent()


def test_a_container_carrying_a_failed_extract_is_degraded(store: SqlStore) -> None:
    cid = _admit(store, _LONG)[0][0]
    good = store.resolve_chunk(cid, TENANT, {WALL})
    bad = store.resolve_chunk(cid, TENANT, {WALL}, expected_text="absente de la source")
    assert not is_degraded([good]) and is_degraded([good, bad])  # any failure taints the container
