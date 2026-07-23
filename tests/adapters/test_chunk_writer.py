"""The one chunk writer's behaviour (story 1.3, AC5/AC6): it writes a complete chunk
under an authorised scope, and refuses — with a typed error, writing nothing — an
incomplete payload, an unauthorised or empty scope, and a version mismatch.

Runs on an in-memory SQLite so the guard logic is covered on every machine; the
real-PostgreSQL DDL (the FK, the enumerated columns, text_identity NOT NULL) is in
test_chunk_writer_postgres.py, gated on a reachable database.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from apx.adapters.store_postgres.chunk_writer import (
    ChunkStore,
    PieceIdentityMismatch,
    UnauthorizedScope,
    VersionMismatch,
)
from apx.adapters.store_postgres.models import Base, Chunk, MatterScope, Piece
from apx.core.domain.identity import chunk_id, piece_id
from apx.core.domain.payload import IncompletePayload, PayloadRecord

_TS = datetime(2026, 7, 23, tzinfo=UTC)
_SCHEMA, _CFG = "1", "c1"
_SCOPE = "wall-penal"


@pytest.fixture
def sf() -> sessionmaker[Session]:
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def _seed(sf: sessionmaker[Session]) -> str:
    """A matter behind a wall, and one piece in it — the ground a chunk needs."""
    pid = piece_id("cabinet", "h", "pole-penal")
    with sf() as s, s.begin():
        s.add(MatterScope(matter="pole-penal", tenant="cabinet", scope=_SCOPE))
        s.add(Piece(
            id=pid, tenant="cabinet", matter="pole-penal", content_hash="h", text_key="tk",
            provenance_path="/dossier/a.pdf", custodian="me@cabinet", extraction_method="text",
            extractor_version="v", schema_version=_SCHEMA, ingestion_timestamp=_TS,
            piece_date=None, piece_date_status="undetermined", full_text="le contrat de bail",
            text_identity="ti", text_version="tv",
        ))
    return pid


def _payload(pid: str, **overrides: object) -> PayloadRecord:
    base = dict(
        tenant="cabinet", matter="pole-penal", source_piece_id=pid, content_hash="h",
        provenance_path="/dossier/a.pdf", custodian="me@cabinet", extraction_method="text",
        extractor_version="v", schema_version=_SCHEMA, chunking_config_version=_CFG,
        ingestion_timestamp=_TS, position=0, full_text="le contrat de bail",
        text_identity="ti", text_version="tv", piece_date=None, piece_date_status="undetermined",
    )
    base.update(overrides)
    return PayloadRecord(**base)  # type: ignore[arg-type]


def _store(sf: sessionmaker[Session]) -> ChunkStore:
    return ChunkStore(sf, schema_version=_SCHEMA, chunking_config_version=_CFG)


def _chunk_count(sf: sessionmaker[Session]) -> int:
    with sf() as s:
        return s.scalar(select(func.count()).select_from(Chunk)) or 0


def test_writes_a_chunk_under_the_authorised_scope(sf: sessionmaker[Session]) -> None:
    pid = _seed(sf)
    cid = _store(sf).write_chunk(_payload(pid), rbac_scope=_SCOPE)
    assert cid == chunk_id(pid, "tv", 0, _CFG)
    with sf() as s:
        row = s.get(Chunk, cid)
        assert row is not None and row.piece_id == pid and row.matter == "pole-penal"
        assert row.full_text_version == "tv" and row.chunking_config_version == _CFG
    # scope and custodian are not columns on the row (AD-9/AD-13)
    columns = {c.name for c in Chunk.__table__.columns}
    assert "rbac_scope" not in columns and "scope" not in columns and "custodian" not in columns


def test_rejects_an_incomplete_payload_and_writes_nothing(sf: sessionmaker[Session]) -> None:
    pid = _seed(sf)
    with pytest.raises(IncompletePayload):
        _store(sf).write_chunk(_payload(pid, custodian=""), rbac_scope=_SCOPE)
    assert _chunk_count(sf) == 0


def test_rejects_a_broken_date_invariant(sf: sessionmaker[Session]) -> None:
    pid = _seed(sf)
    with pytest.raises(IncompletePayload):
        # a date with an 'undetermined' status is never written (AC1)
        _store(sf).write_chunk(
            _payload(pid, piece_date=datetime(2020, 1, 1).date(), piece_date_status="undetermined"),
            rbac_scope=_SCOPE,
        )
    assert _chunk_count(sf) == 0


def test_rejects_an_unauthorised_scope_and_writes_nothing(sf: sessionmaker[Session]) -> None:
    pid = _seed(sf)
    with pytest.raises(UnauthorizedScope):
        _store(sf).write_chunk(_payload(pid), rbac_scope="wall-civil")
    assert _chunk_count(sf) == 0


def test_rejects_an_empty_scope(sf: sessionmaker[Session]) -> None:
    pid = _seed(sf)
    with pytest.raises(UnauthorizedScope):
        _store(sf).write_chunk(_payload(pid), rbac_scope="")
    assert _chunk_count(sf) == 0


def test_rejects_a_source_piece_id_not_matching_its_provenance(sf: sessionmaker[Session]) -> None:
    _seed(sf)
    # a pièce id derived from ANOTHER matter — piece_id encodes the matter (AD-40), so a
    # chunk carrying it would cross the Chinese wall. The single seam refuses it.
    foreign_pid = piece_id("cabinet", "h", "pole-assurance")
    with pytest.raises(PieceIdentityMismatch):
        _store(sf).write_chunk(_payload(foreign_pid), rbac_scope=_SCOPE)
    assert _chunk_count(sf) == 0


def test_rejects_a_scope_from_another_tenant(sf: sessionmaker[Session]) -> None:
    _seed(sf)
    # a payload consistent for ANOTHER tenant (its own tenant-qualified piece id); that
    # tenant holds no matter_scope row here, so the write is refused at the scope check
    # (tenant-first, fail closed — AD-12).
    foreign = _payload(piece_id("autre-cabinet", "h", "pole-penal"), tenant="autre-cabinet")
    with pytest.raises(UnauthorizedScope):
        _store(sf).write_chunk(foreign, rbac_scope=_SCOPE)
    assert _chunk_count(sf) == 0


def test_rejects_a_version_mismatch_and_writes_nothing(sf: sessionmaker[Session]) -> None:
    pid = _seed(sf)
    with pytest.raises(VersionMismatch):
        _store(sf).write_chunk(_payload(pid, schema_version="2"), rbac_scope=_SCOPE)
    with pytest.raises(VersionMismatch):
        _store(sf).write_chunk(_payload(pid, chunking_config_version="c2"), rbac_scope=_SCOPE)
    assert _chunk_count(sf) == 0


def test_a_rewrite_is_idempotent_not_a_duplicate(sf: sessionmaker[Session]) -> None:
    pid = _seed(sf)
    store = _store(sf)
    first = store.write_chunk(_payload(pid), rbac_scope=_SCOPE)
    second = store.write_chunk(_payload(pid), rbac_scope=_SCOPE)
    assert first == second
    assert _chunk_count(sf) == 1
