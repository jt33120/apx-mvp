"""Store writer tests against in-memory SQLite (the writer LOGIC; Postgres DDL is
verified in CI). Real SQL, real constraints — not a fixture: the store is a real
adapter, SQLite is only the test substrate for its behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.extraction.files import FileExtractor
from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import ingest_folder


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def _matter(root: Path) -> None:
    (root / "a.txt").write_text("pièce une", encoding="utf-8")
    (root / "b.md").write_text("# pièce deux", encoding="utf-8")
    (root / "bad.jpg").write_bytes(b"nope")  # unsupported-format -> failure


def test_save_then_read_durable_inventory(tmp_path: Path, store: SqlStore) -> None:
    _matter(tmp_path)
    result = ingest_folder(tmp_path, matter="m", tenant="t", extractor=FileExtractor())
    outcome = store.save(result)
    assert outcome.pieces_written == 2
    assert outcome.failures_written == 1

    inv = store.inventory(matter="m", tenant="t")
    assert inv.in_corpus == 2
    assert inv.failures == 1
    assert inv.is_consistent()


def test_re_ingesting_the_same_folder_does_not_duplicate(tmp_path: Path, store: SqlStore) -> None:
    _matter(tmp_path)
    result = ingest_folder(tmp_path, matter="m", tenant="t", extractor=FileExtractor())
    store.save(result)
    store.save(result)  # same content, same matter -> same ids -> no duplication (AD-40)

    inv = store.inventory(matter="m", tenant="t")
    assert inv.in_corpus == 2  # not 4
    assert inv.failures == 1  # not 2


def test_matters_are_isolated_in_read_back(tmp_path: Path, store: SqlStore) -> None:
    _matter(tmp_path)
    r1 = ingest_folder(tmp_path, matter="m1", tenant="t", extractor=FileExtractor())
    r2 = ingest_folder(tmp_path, matter="m2", tenant="t", extractor=FileExtractor())
    store.save(r1)
    store.save(r2)
    # Same files, two matters -> two separate pieces each (confidentiality follows the matter).
    assert store.inventory("m1", "t").in_corpus == 2
    assert store.inventory("m2", "t").in_corpus == 2
