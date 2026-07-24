"""Key rotation in place (story 1.8, AD-47): the re-key pass moves every application-encrypted
value from a previous key to the new primary, records the rotation on each tenant's audit chain
(naming a key fingerprint, never the key), and leaves the searchable text index untouched (no
re-index). SQLite everywhere.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.backfill import rekey_all
from apx.adapters.store_postgres.models import AuditRecord, Base
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestedPiece, IngestionResult
from apx.core.domain.crypto import Cipher, DecryptionError, generate_key, load_key_from_env

TENANT, MATTER, SCOPE = "cabinet", "m", "wall"


def _key() -> bytes:
    return base64.urlsafe_b64decode(generate_key())


def _piece(pid: str = "p1", *, full_text: str = "le contrat") -> IngestedPiece:
    return IngestedPiece(
        id=pid, matter=MATTER, tenant=TENANT, content_hash=pid * 8, text_key=pid * 8,
        provenance_path=f"/secret/{pid}.pdf", custodian="c", extraction_method="text",
        extractor_version="v", schema_version="s", ingestion_timestamp=datetime.now(UTC),
        full_text=full_text, text_version="v",
    )


def _store(tmp_path) -> tuple[object, SqlStore]:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    Base.metadata.create_all(engine)
    return engine, SqlStore(sessionmaker(bind=engine, future=True))


def test_rekey_all_moves_values_to_a_new_primary_key(tmp_path) -> None:  # noqa: ANN001
    # the ORM seeds provenance under the CURRENT (conftest) key
    current = load_key_from_env()
    new = _key()
    engine, store = _store(tmp_path)
    store.save(IngestionResult(pieces=[_piece()]), SCOPE, actor="a")

    # rotate: new primary, the current key as the previous fallback
    with engine.begin() as conn:
        assert rekey_all(conn, Cipher([new, current])) >= 1

    with engine.connect() as conn:
        raw = conn.exec_driver_sql("SELECT provenance_path FROM piece").scalar()
    ctx = "piece.provenance_path"
    assert Cipher([new]).decrypt(raw, aad=ctx) == "/secret/p1.pdf"  # readable under the new key
    with pytest.raises(DecryptionError):
        Cipher([current]).decrypt(raw, aad=ctx)  # the retired key can no longer read it


def test_rekey_command_re_encrypts_and_records_rotation_per_tenant(tmp_path) -> None:  # noqa: ANN001
    from apx.manage import rekey

    _engine, store = _store(tmp_path)
    store.create_user(TENANT, "a@a.test", "password1", "Avocat A", set())  # the tenant exists
    store.save(IngestionResult(pieces=[_piece()]), SCOPE, actor="a")

    message = rekey(store)
    assert "re-encrypted" in message and "1 tenant" in message

    with store._sf() as s:
        actions = s.execute(
            select(AuditRecord.action).where(AuditRecord.tenant == TENANT)
        ).scalars().all()
        rotation = s.execute(
            select(AuditRecord.detail).where(AuditRecord.action == "key_rotated")
        ).scalars().all()
    assert "key_rotated" in actions
    assert rotation and rotation[0].startswith("key=")  # names a fingerprint, not the key
    # the trail still verifies after the rotation entry
    assert store.read_audit(MATTER, TENANT, {SCOPE}).verified


def test_rekey_audits_a_data_only_tenant_with_no_user(tmp_path) -> None:  # noqa: ANN001
    from apx.manage import rekey

    _engine, store = _store(tmp_path)
    # a tenant with ingested pieces but NO user row (data before user creation, or users removed)
    store.save(IngestionResult(pieces=[_piece()]), SCOPE, actor="a")
    message = rekey(store)
    assert "1 tenant" in message  # the data-only tenant is counted from the DATA surface
    with store._sf() as s:
        actions = s.execute(
            select(AuditRecord.action).where(AuditRecord.tenant == TENANT)
        ).scalars().all()
    assert "key_rotated" in actions  # its rotation IS on the record, not silently skipped


def test_rekey_leaves_the_text_index_untouched(tmp_path) -> None:  # noqa: ANN001
    # full_text is the AD-31 exempt index — not application-encrypted — so a rotation must not
    # rewrite it (that is what "rotatable without re-indexing" means).
    engine, store = _store(tmp_path)
    store.save(IngestionResult(pieces=[_piece(full_text="le contrat de bail")]), SCOPE, actor="a")
    with engine.connect() as conn:
        before = conn.exec_driver_sql("SELECT full_text FROM piece").scalar()
    with engine.begin() as conn:
        rekey_all(conn)
    with engine.connect() as conn:
        after = conn.exec_driver_sql("SELECT full_text FROM piece").scalar()
    assert before == after == "le contrat de bail"  # unchanged and still plaintext
