"""The inventory guarantee and the permanent denominator (Story 2.7; FR-6/FR-57/AD-38, SM-3).

Against the real SQLite store: ``submitted_pieces`` is a frozen, independent, idempotent
high-water mark (NOT recomputed as the sum), so a pièce lost from the corpus after it was counted
fails the invariant — the release-blocker (AC4) at the store level. Filesystem noise is
configuration-as-data, durable, countable, listable and scope-checked; the unknown-cardinality
containers are counted durably and rendered in words.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.extraction.files import FileExtractor
from apx.adapters.store_postgres.models import Base, Piece
from apx.adapters.store_postgres.store import ScopeDenied, SqlStore
from apx.core.app.ingest import IngestionResult, ingest_folder
from apx.core.domain.failures import ErrorClass
from apx.core.domain.identity import content_hash, piece_id
from tests.adapters.test_failure_register import TENANT, WALL, _fail, _piece


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


# ── AC1 / Task 2: submitted_pieces is a frozen, independent, idempotent high-water mark ──────────

def test_submitted_pieces_equals_the_sum_when_the_matter_is_clean(store: SqlStore) -> None:
    store.save(
        IngestionResult(
            pieces=[_piece("a", prov="a.txt"), _piece("b", prov="b.txt")],
            failures=[_fail("bad.pdf")]),
        scope=WALL, matter="m", tenant=TENANT)
    inv = store.inventory("m", TENANT, {WALL})
    assert inv.submitted_pieces == 3 and inv.in_corpus == 2 and inv.open_register_entries == 1
    assert inv.is_consistent()


def test_a_piece_lost_from_the_corpus_fails_the_invariant(store: SqlStore) -> None:
    # AC4 at the store: because submitted_pieces is a FROZEN watermark (not recomputed as the sum),
    # a pièce dropped from the corpus after being counted makes it exceed the live sum → SM-3 fires.
    store.save(
        IngestionResult(pieces=[_piece("a", prov="a.txt"), _piece("b", prov="b.txt")]),
        scope=WALL, matter="m", tenant=TENANT)
    assert store.inventory("m", TENANT, {WALL}).submitted_pieces == 2
    lost = piece_id(TENANT, content_hash(b"b"), "m")
    with store._sf() as s, s.begin():
        s.execute(delete(Piece).where(Piece.id == lost))  # a drop the store never authorised
    inv = store.inventory("m", TENANT, {WALL})
    assert inv.submitted_pieces == 2 and inv.in_corpus == 1  # watermark frozen; corpus shrank
    with pytest.raises(ValueError, match="inventory invariant violated"):
        inv.require_consistent()


def test_reimporting_the_same_folder_does_not_grow_submitted_pieces(store: SqlStore) -> None:
    result = IngestionResult(pieces=[_piece("a", prov="a.txt")], failures=[_fail("bad.pdf")])
    store.save(result, scope=WALL, matter="m", tenant=TENANT)
    store.save(result, scope=WALL, matter="m", tenant=TENANT)  # the same material again (Story 2.5)
    inv = store.inventory("m", TENANT, {WALL})
    assert inv.submitted_pieces == 2  # NOT 4 — recognised-already-present, the watermark holds
    assert inv.is_consistent()


def test_submitted_pieces_grows_monotonically_with_genuinely_new_pieces(store: SqlStore) -> None:
    store.save(IngestionResult(pieces=[_piece("a", prov="a.txt")]),
               scope=WALL, matter="m", tenant=TENANT)
    assert store.inventory("m", TENANT, {WALL}).submitted_pieces == 1
    store.save(IngestionResult(pieces=[_piece("a", prov="a.txt"), _piece("c", prov="c.txt")]),
               scope=WALL, matter="m", tenant=TENANT)
    assert store.inventory("m", TENANT, {WALL}).submitted_pieces == 2  # +1 new (a recognised)


def test_retry_resolving_to_a_content_duplicate_keeps_the_invariant(store: SqlStore) -> None:
    # a.txt = content X in corpus; b.txt = the SAME document (same content), transiently failed →
    # one open entry. submitted_pieces=2 while both stand apart. The retry recovers content X for
    # b.txt — a DUPLICATE (same piece_id) → dedup: in_corpus stays 1, the entry resolves. The
    # distinct count legitimately drops to 1; a monotonic watermark would wrongly trip SM-3.
    store.save(IngestionResult(pieces=[_piece("X", prov="a.txt")], failures=[_fail("b.txt")]),
               scope=WALL, matter="m", tenant=TENANT)
    assert store.inventory("m", TENANT, {WALL}).submitted_pieces == 2
    entry = next(e for e in store.register("m", TENANT, {WALL}) if e.submitted_path == "b.txt")
    out = store.retry_failure(
        entry.id, lambda: IngestionResult(pieces=[_piece("X", prov="b.txt")]),
        TENANT, {WALL}, actor="avocat")
    assert out.outcome == "resolved"
    inv = store.inventory("m", TENANT, {WALL})
    assert inv.in_corpus == 1 and inv.open_register_entries == 0    # deduped; entry resolved
    assert inv.submitted_pieces == 1 and inv.is_consistent()        # decremented — dup collapsed


def test_bulk_retry_resolving_to_a_duplicate_never_wedges_the_matter(store: SqlStore) -> None:
    store.save(IngestionResult(pieces=[_piece("X", prov="a.txt")], failures=[_fail("b.txt")]),
               scope=WALL, matter="m", tenant=TENANT)
    out = store.bulk_retry(
        TENANT, {WALL}, matter="m", actor="avocat",
        reingest_for=lambda e: (lambda: IngestionResult(pieces=[_piece("X", prov="b.txt")])))
    assert out.resolved == 1 and out.errored == 0                   # resolved, not silently errored
    inv = store.inventory("m", TENANT, {WALL})
    assert inv.submitted_pieces == 1 and inv.in_corpus == 1 and inv.open_register_entries == 0
    assert inv.is_consistent()  # NOT wedged — consistent, never a persisted inconsistency


# ── AC2 / Task 3: filesystem noise — config-as-data, durable, countable, listable, scope-checked ─

def test_noise_is_persisted_counted_and_listable_outside_the_identity(store: SqlStore) -> None:
    store.save(
        IngestionResult(
            pieces=[_piece("a", prov="a.txt")], exclusions=["sub/.DS_Store", "sub/Thumbs.db"]),
        scope=WALL, matter="m", tenant=TENANT)
    inv = store.inventory("m", TENANT, {WALL})
    assert inv.excluded_as_noise == 2 and inv.in_corpus == 1 and inv.submitted_pieces == 1
    assert inv.is_consistent()  # noise is OUTSIDE the identity: 1 == 1 + 0
    listing = store.noise_exclusions("m", TENANT, {WALL})
    assert {e.submitted_path for e in listing} == {"sub/.DS_Store", "sub/Thumbs.db"}  # decrypted
    assert {e.filename for e in listing} == {".DS_Store", "Thumbs.db"}                # basename


def test_reexcluding_the_same_noise_file_is_idempotent(store: SqlStore) -> None:
    r = IngestionResult(pieces=[_piece("a", prov="a.txt")], exclusions=["x/.DS_Store"])
    store.save(r, scope=WALL, matter="m", tenant=TENANT)
    store.save(r, scope=WALL, matter="m", tenant=TENANT)
    assert store.inventory("m", TENANT, {WALL}).excluded_as_noise == 1  # not 2


def test_the_noise_list_is_scope_checked_fail_closed(store: SqlStore) -> None:
    store.save(IngestionResult(pieces=[_piece("a", prov="a.txt")], exclusions=["x/.DS_Store"]),
               scope=WALL, matter="m", tenant=TENANT)
    with pytest.raises(ScopeDenied):
        store.noise_exclusions("m", TENANT, {"other-wall"})


def test_default_noise_patterns_exclude_os_detritus_and_lock_files(tmp_path) -> None:
    (tmp_path / "real.txt").write_text("un document", encoding="utf-8")
    (tmp_path / ".DS_Store").write_bytes(b"noise")
    (tmp_path / "~$real.docx").write_bytes(b"office lock")
    (tmp_path / "._real.txt").write_bytes(b"appledouble fork")
    r = ingest_folder(tmp_path, matter="m", tenant="t", extractor=FileExtractor())
    assert set(r.exclusions) == {".DS_Store", "~$real.docx", "._real.txt"}
    assert r.inventory.excluded_as_noise == 3 and r.inventory.in_corpus == 1
    assert r.inventory.is_consistent()


def test_a_tenant_noise_list_replaces_the_default_config_as_data(tmp_path) -> None:
    (tmp_path / "note.txt").write_text("gardé", encoding="utf-8")
    (tmp_path / "temp.tmp").write_text("bruit configuré", encoding="utf-8")
    (tmp_path / ".DS_Store").write_text("plus du bruit par défaut", encoding="utf-8")
    r = ingest_folder(
        tmp_path, matter="m", tenant="t", extractor=FileExtractor(), noise_patterns=["*.tmp"])
    assert r.exclusions == ["temp.tmp"]           # the custom list REPLACES the default
    assert ".DS_Store" not in r.exclusions        # no longer noise → accounted inside the identity
    # .DS_Store is now a pièce-or-failure (here an unsupported-format failure), never silently gone:
    assert r.inventory.excluded_as_noise == 1 and r.inventory.submitted_pieces == 2
    assert r.inventory.is_consistent()


# ── AC3 / Task 4: the unknown-cardinality containers, counted durably and rendered in words ──────

def test_unknown_cardinality_containers_are_counted_durably_and_in_words(store: SqlStore) -> None:
    store.save(
        IngestionResult(failures=[_fail("bomb.zip", cls=ErrorClass.CONTAINER_UNOPENABLE)]),
        scope=WALL, matter="m", tenant=TENANT)
    inv = store.inventory("m", TENANT, {WALL})
    assert inv.open_register_entries == 1 and inv.unknown_cardinality_entries == 1
    assert inv.unknown_cardinality_phrase() == "1 archive unopened, contents unknown"
    assert inv.is_consistent()  # the container is 1 open entry; the unknown is a subset, not summed
