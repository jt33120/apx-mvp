"""Real-PostgreSQL integration for the store — the DDL and constraints the SQLite
tests can't cover. Skipped unless DATABASE_URL points at PostgreSQL (CI sets it to
the postgres service; locally it runs when you have Docker + the compose DB up).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestedPiece, IngestionResult

_URL = os.environ.get("DATABASE_URL", "")
_IS_PG = _URL.startswith("postgresql")

pytestmark = pytest.mark.skipif(not _IS_PG, reason="no PostgreSQL DATABASE_URL — CI runs this")


@pytest.fixture
def pg_store() -> SqlStore:
    engine = create_engine(_URL, future=True)
    # The migration owns the real schema; the test creates/drops in its own way to
    # stay independent of migration state, then relies on the same models.
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def _piece(pid: str) -> IngestedPiece:
    return IngestedPiece(
        id=pid, matter="m", tenant="t", content_hash="h", provenance_path="p",
        custodian="c", extraction_method="text", extractor_version="v",
        schema_version="s", ingestion_timestamp=datetime.now(UTC),
        full_text="hello", text_version="v",
    )


def test_save_and_read_back_on_postgres(pg_store: SqlStore) -> None:
    pg_store.save(IngestionResult(pieces=[_piece("a"), _piece("b")]), actor="Me Dupont", scope="w")
    inv = pg_store.inventory("m", "t", {"w"})
    assert inv.in_corpus == 2 and inv.is_consistent()


def test_date_status_check_constraint_is_enforced_on_postgres(pg_store: SqlStore) -> None:
    engine = create_engine(_URL, future=True)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO piece (id,tenant,matter,content_hash,provenance_path,custodian,"
                "extraction_method,extractor_version,schema_version,ingestion_timestamp,"
                "piece_date,piece_date_status,full_text,text_identity,text_version) VALUES "
                "('x','t','m','h','p','c','text','v','s',now(),'2024-01-01','undetermined',"
                "'t','ti','v')"
            )
        )
