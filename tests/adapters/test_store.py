"""Store tests against in-memory SQLite: persistence, idempotency, and the
Chinese-wall scope PRE-filter. Real SQL, real constraints — not a fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.extraction.files import FileExtractor
from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import ScopeDenied, SqlStore
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


def _ingest(root: Path, matter: str):
    return ingest_folder(root, matter=matter, tenant="t", extractor=FileExtractor())


def test_save_then_read_durable_inventory(tmp_path: Path, store: SqlStore) -> None:
    _matter(tmp_path)
    out = store.save(_ingest(tmp_path, "m"), scope="wall-1")
    assert out.pieces_written == 2 and out.failures_written == 1
    inv = store.inventory("m", "t", {"wall-1"})
    assert inv.in_corpus == 2 and inv.failures == 1 and inv.is_consistent()


def test_re_ingesting_does_not_duplicate(tmp_path: Path, store: SqlStore) -> None:
    _matter(tmp_path)
    r = _ingest(tmp_path, "m")
    store.save(r, scope="wall-1")
    store.save(r, scope="wall-1")
    inv = store.inventory("m", "t", {"wall-1"})
    assert inv.in_corpus == 2 and inv.failures == 1  # not doubled (AD-40)


def test_scope_prefilter_hides_matters_outside_the_wall(tmp_path: Path, store: SqlStore) -> None:
    _matter(tmp_path)
    store.save(_ingest(tmp_path, "m-a"), scope="wall-A")
    store.save(_ingest(tmp_path, "m-b"), scope="wall-B")

    # A user holding only wall-A sees m-a and NOT m-b.
    assert {m.matter for m in store.matters("t", {"wall-A"})} == {"m-a"}
    # Holding both walls sees both.
    assert {m.matter for m in store.matters("t", {"wall-A", "wall-B"})} == {"m-a", "m-b"}
    # No scope -> nothing (fail closed).
    assert store.matters("t", set()) == []


def test_reading_a_matter_outside_scope_is_refused(tmp_path: Path, store: SqlStore) -> None:
    _matter(tmp_path)
    store.save(_ingest(tmp_path, "m-b"), scope="wall-B")
    with pytest.raises(ScopeDenied):
        store.inventory("m-b", "t", {"wall-A"})  # holds the wrong wall
    with pytest.raises(ScopeDenied):
        store.inventory("does-not-exist", "t", {"wall-A"})  # existence not disclosed


def test_deduplicate_collapses_copies_modulo_formatting(tmp_path: Path, store: SqlStore) -> None:
    # Different bytes (so distinct pieces by content_hash) but the SAME text modulo
    # whitespace/case -> one near-duplicate cluster.
    (tmp_path / "a.txt").write_text("Le contrat est signé.", encoding="utf-8")
    (tmp_path / "b.txt").write_text("le   CONTRAT  est signé.", encoding="utf-8")
    (tmp_path / "c.txt").write_text("Autre pièce, distincte.", encoding="utf-8")
    store.save(_ingest(tmp_path, "m"), scope="wall-1")

    d = store.deduplicate("m", "t", {"wall-1"})
    assert d.submitted == 3 and d.distinct == 2 and d.duplicates == 1
    assert d.submitted == d.distinct + d.duplicates  # nothing lost — copies kept, collapsed
    (g,) = d.groups
    assert g.size == 2 and set(g.members) == {"a.txt", "b.txt"}


def test_deduplicate_is_scope_checked(tmp_path: Path, store: SqlStore) -> None:
    (tmp_path / "a.txt").write_text("pièce", encoding="utf-8")
    store.save(_ingest(tmp_path, "m-b"), scope="wall-B")
    with pytest.raises(ScopeDenied):
        store.deduplicate("m-b", "t", {"wall-A"})  # the wall pre-filters triage too
