"""The real pgvector halfvec write + nearest-neighbour query (Story 2.8, AD-11) — the Postgres leg.

SQLite has no pgvector, so the halfvec column's REAL DDL (the extension, the 1024-dim halfvec type,
the HNSW index) and a vector query can only be proven against PostgreSQL. Skipped unless a
PostgreSQL DATABASE_URL (CI's postgres service runs it, after `alembic upgrade head` proves 0021).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from apx.adapters.store_postgres.chunk_writer import ChunkStore
from apx.adapters.store_postgres.models import EMBEDDING_DIM, Base, Chunk, MatterScope, Piece
from apx.core.domain.identity import chunk_id, piece_id
from apx.core.domain.payload import PayloadRecord

_URL = os.environ.get("DATABASE_URL", "")
_IS_PG = _URL.startswith("postgresql")
pytestmark = pytest.mark.skipif(not _IS_PG, reason="no PostgreSQL DATABASE_URL — CI runs this")

_TS = datetime(2026, 7, 29, tzinfo=UTC)
_SCHEMA, _CFG, _SCOPE = "1", "c1", "wall-penal"


@pytest.fixture
def sf() -> sessionmaker[Session]:
    engine: Engine = create_engine(_URL, future=True)
    with engine.begin() as c:
        c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))  # the halfvec type needs it
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def _seed(sf: sessionmaker[Session]) -> str:
    pid = piece_id("cabinet", "h", "pole-penal")
    with sf() as s, s.begin():
        s.add(MatterScope(matter="pole-penal", tenant="cabinet", scope=_SCOPE))
        s.add(Piece(
            id=pid, tenant="cabinet", matter="pole-penal", content_hash="h", text_key="tk",
            provenance_path="/a.pdf", custodian="me", extraction_method="text",
            extractor_version="v", schema_version=_SCHEMA, ingestion_timestamp=_TS, piece_date=None,
            piece_date_status="undetermined", full_text="le bail", text_identity="ti",
            text_version="tv"))
    return pid


def _payload(pid: str) -> PayloadRecord:
    return PayloadRecord(
        tenant="cabinet", matter="pole-penal", source_piece_id=pid, content_hash="h",
        provenance_path="/a.pdf", custodian="me", extraction_method="text", extractor_version="v",
        schema_version=_SCHEMA, chunking_config_version=_CFG, ingestion_timestamp=_TS, position=0,
        full_text="le bail", text_identity="ti", text_version="tv", piece_date=None,
        piece_date_status="undetermined")


def test_a_halfvec_chunk_round_trips_and_is_queryable(sf: sessionmaker[Session]) -> None:
    pid = _seed(sf)
    store = ChunkStore(sf, schema_version=_SCHEMA, chunking_config_version=_CFG)
    vector = [0.0] * EMBEDDING_DIM
    vector[0] = 1.0
    cid = store.write_chunk(
        _payload(pid), rbac_scope=_SCOPE, vector=vector, model_id="BAAI/bge-m3",
        model_version="bge-m3-1.0")
    assert cid == chunk_id(pid, "tv", 0, _CFG)
    # the trio round-trips, and an HNSW cosine nearest-neighbour query returns the row
    with sf() as s:
        row = s.scalar(select(Chunk).where(Chunk.chunk_id == cid))
        assert row.model_id == "BAAI/bge-m3" and len(row.vector) == EMBEDDING_DIM
        nearest = s.execute(
            text("SELECT chunk_id FROM chunk ORDER BY vector <=> :q LIMIT 1"),
            {"q": str(vector)}).scalar()
        assert nearest == cid
