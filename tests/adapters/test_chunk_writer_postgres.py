"""Real-PostgreSQL DDL for the frozen payload schema (story 1.3, AC5/AC7): the enumerated
column set, the piece FK with no cascade, and text_identity NOT NULL — what SQLite cannot
enforce. Skipped unless DATABASE_URL points at PostgreSQL (CI's postgres service runs it,
after `alembic upgrade head` has already proved the migration applies).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from apx.adapters.store_postgres.chunk_writer import ChunkStore
from apx.adapters.store_postgres.models import EMBEDDING_DIM, Base, MatterScope, Piece
from apx.core.domain.identity import chunk_id, piece_id
from apx.core.domain.payload import PayloadRecord

_URL = os.environ.get("DATABASE_URL", "")
_IS_PG = _URL.startswith("postgresql")
pytestmark = pytest.mark.skipif(not _IS_PG, reason="no PostgreSQL DATABASE_URL — CI runs this")

_TS = datetime(2026, 7, 23, tzinfo=UTC)
_SCHEMA, _CFG, _SCOPE = "1", "c1", "wall-penal"

# The AD-9 enumerated chunk columns, now including the embedding trio (story 2.8, AD-11).
_ENUMERATED = {
    "chunk_id", "piece_id", "tenant", "matter", "position",
    "full_text_version", "chunking_config_version", "schema_version", "external_ref",
    "model_id", "model_version", "vector",
}
_VEC = [0.1] * EMBEDDING_DIM  # a valid embedding trio for the write tests (story 2.8)
_MID, _MVER = "bge-m3", "v1"


@pytest.fixture
def engine() -> Engine:
    eng = create_engine(_URL, future=True)
    with eng.begin() as c:
        c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))  # the halfvec column needs it
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def sf(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, future=True)


def _seed(sf: sessionmaker[Session]) -> str:
    pid = piece_id("cabinet", "h", "pole-penal")
    with sf() as s, s.begin():
        s.add(MatterScope(matter="pole-penal", tenant="cabinet", scope=_SCOPE))
        s.add(Piece(
            id=pid, tenant="cabinet", matter="pole-penal", content_hash="h", text_key="tk",
            provenance_path="/a.pdf", custodian="me", extraction_method="text",
            extractor_version="v", schema_version=_SCHEMA, ingestion_timestamp=_TS,
            piece_date=None, piece_date_status="undetermined", full_text="texte",
            text_identity="ti", text_version="tv",
        ))
    return pid


def _payload(pid: str, **overrides: object) -> PayloadRecord:
    base = dict(
        tenant="cabinet", matter="pole-penal", source_piece_id=pid, content_hash="h",
        provenance_path="/a.pdf", custodian="me", extraction_method="text", extractor_version="v",
        schema_version=_SCHEMA, chunking_config_version=_CFG, ingestion_timestamp=_TS,
        position=0, full_text="texte", text_identity="ti", text_version="tv",
        piece_date=None, piece_date_status="undetermined",
    )
    base.update(overrides)
    return PayloadRecord(**base)  # type: ignore[arg-type]


def test_chunk_table_has_exactly_the_enumerated_columns(engine: Engine) -> None:
    cols = {c["name"] for c in inspect(engine).get_columns("chunk")}
    assert cols == _ENUMERATED, f"chunk columns drifted from the AD-9 enumeration: {cols}"


def test_piece_foreign_key_has_no_cascade(engine: Engine) -> None:
    piece_fks = [fk for fk in inspect(engine).get_foreign_keys("chunk")
                 if fk["referred_table"] == "piece"]
    assert piece_fks, "chunk must reference piece"
    for fk in piece_fks:
        ondelete = (fk.get("options") or {}).get("ondelete")
        assert ondelete in (None, "NO ACTION"), f"AD-7: no cascade, got {ondelete!r}"


def test_piece_text_identity_is_not_null(engine: Engine) -> None:
    col = next(c for c in inspect(engine).get_columns("piece") if c["name"] == "text_identity")
    assert col["nullable"] is False


def test_writes_a_chunk_on_postgres(sf: sessionmaker[Session]) -> None:
    pid = _seed(sf)
    store = ChunkStore(sf, schema_version=_SCHEMA, chunking_config_version=_CFG)
    assert store.write_chunk(
        _payload(pid), rbac_scope=_SCOPE, vector=_VEC, model_id=_MID, model_version=_MVER,
    ) == chunk_id(pid, "tv", 0, _CFG)


def test_a_chunk_for_a_missing_piece_is_refused_by_the_fk(sf: sessionmaker[Session]) -> None:
    # matter authorised, but no piece row exists — the real FK rejects it (SQLite cannot).
    with sf() as s, s.begin():
        s.add(MatterScope(matter="pole-penal", tenant="cabinet", scope=_SCOPE))
    store = ChunkStore(sf, schema_version=_SCHEMA, chunking_config_version=_CFG)
    with pytest.raises(IntegrityError):
        store.write_chunk(
            _payload(piece_id("cabinet", "h", "pole-penal")),
            rbac_scope=_SCOPE, vector=_VEC, model_id=_MID, model_version=_MVER)
