"""Audit trail: append-only, monotonic, chained — and tamper-evident."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.extraction.files import FileExtractor
from apx.adapters.store_postgres.models import AuditRecord, Base
from apx.adapters.store_postgres.store import ScopeDenied, SqlStore
from apx.core.app.ingest import ingest_folder


@pytest.fixture
def engine():
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    return e


@pytest.fixture
def store(engine) -> SqlStore:
    return SqlStore(sessionmaker(bind=engine, future=True))


def _ingest(root: Path, matter: str):
    (root / "a.txt").write_text("pièce", encoding="utf-8")
    return ingest_folder(root, matter=matter, tenant="t", extractor=FileExtractor())


def test_ingestion_is_recorded_with_actor_and_denominator(tmp_path: Path, store: SqlStore) -> None:
    store.save(_ingest(tmp_path, "m"), scope="w", actor="me.durupt")
    trail = store.read_audit("m", "t", {"w"})
    assert len(trail.entries) == 1
    e = trail.entries[0]
    assert e.action == "ingest" and e.actor == "me.durupt" and "submitted_pieces=1" in e.detail
    assert trail.verified


def test_sequence_is_monotonic_and_chain_verifies(tmp_path: Path, store: SqlStore) -> None:
    store.save(_ingest(tmp_path, "m"), scope="w", actor="a")
    store.save(_ingest(tmp_path, "m"), scope="w", actor="a")  # re-ingest -> a 2nd audit entry
    trail = store.read_audit("m", "t", {"w"})
    assert [e.seq for e in trail.entries] == [1, 2]
    assert trail.verified


def test_tampering_with_a_stored_entry_breaks_verification(tmp_path: Path, store, engine) -> None:
    store.save(_ingest(tmp_path, "m"), scope="w", actor="a")
    # An attacker edits the actor of a committed audit row (append-only is violated).
    with engine.begin() as conn:
        conn.execute(update(AuditRecord).values(actor="not-me"))
    trail = store.read_audit("m", "t", {"w"})
    assert trail.verified is False  # the chain no longer recomputes -> tamper detected


def test_a_deleted_entry_breaks_verification(tmp_path: Path, store, engine) -> None:
    store.save(_ingest(tmp_path, "m"), scope="w", actor="a")
    store.save(_ingest(tmp_path, "m"), scope="w", actor="a")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM audit_record WHERE seq = 1"))  # truncate the chain
    assert store.read_audit("m", "t", {"w"}).verified is False


def test_audit_is_scope_checked(tmp_path: Path, store: SqlStore) -> None:
    store.save(_ingest(tmp_path, "m"), scope="wall-B", actor="a")
    with pytest.raises(ScopeDenied):
        store.read_audit("m", "t", {"wall-A"})
