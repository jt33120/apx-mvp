"""The backup bundle: the *originals* travel, and nothing in it is in the clear (Story 7.2, C3).

AD-32's Rule opens by naming the originals first — *"a complete restorable backup of a tenant —
originals, extracted text, index, audit record, failure register, configuration — … encrypted,
inside the tenant boundary"*. The backup this replaces satisfied neither end of that sentence.

**The originals were not in it.** ``backup_tenant`` selected database rows and nothing else; the
string ``original`` did not occur in the function. A restored *matter* returned *pièces* whose
source document was gone — including through FR-13's exhaustive search, the surface whose whole job
is to prove nothing was lost.

**It was not encrypted.** ``chunk.full_text`` is the one column AD-31 deliberately leaves in the
clear, and its stated protection is the encrypted *volume*. A backup file is the one artefact
designed to leave that volume, and it carried the searchable corpus in plaintext.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apx.adapters.originals_fs.store import FilesystemOriginalStore
from apx.adapters.store_postgres.backup_plan import backup_plan
from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore
from apx.backup_bundle import (
    ORIGINALS_DIR,
    TABLES_FILE,
    BundleFormatError,
    read_bundle,
    restore_originals,
    write_bundle,
)
from apx.core.app.ingest import IngestedPiece, IngestionResult
from apx.core.domain.crypto import (
    Cipher,
    DecryptionError,
    _decode_key,
    generate_key,
)

TENANT, OTHER, MATTER, WALL = "cabinet", "autre", "m", "w"
SECRET = "clause résolutoire du bail commercial signé le 3 mars"
BYTES = b"%PDF-1.4 le bail, en original\n"


@pytest.fixture
def cipher() -> Cipher:
    return Cipher.from_env()


def _store(tmp_path, name: str) -> SqlStore:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / name}.db", future=True)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def _piece(pid: str, content_hash: str) -> IngestedPiece:
    return IngestedPiece(
        id=pid, matter=MATTER, tenant=TENANT, content_hash=content_hash, text_key=content_hash,
        provenance_path=f"/dossier/{pid}.pdf", custodian="Me Martin", extraction_method="pdf",
        extractor_version="v1", schema_version="s1", ingestion_timestamp=datetime.now(UTC),
        full_text=SECRET, text_version="v")


def _hash(seed: str) -> str:
    import hashlib
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _seeded(tmp_path, cipher: Cipher, *, retain: bool = True):  # noqa: ANN001, ANN202
    """One tenant, one *pièce*, its original on the volume the way ingest retains it."""
    store = _store(tmp_path, "src")
    store.provision_tenant(TENANT, "a@x.fr", "pw12345678", "Admin", {WALL}, ["conclusions"])
    content_hash = _hash("bail")
    store.save(IngestionResult(pieces=[_piece("p0", content_hash)]), WALL, actor="admin")
    originals = FilesystemOriginalStore(tmp_path / "vol", cipher)
    if retain:
        originals.put(TENANT, content_hash, BYTES)
    return store, originals, content_hash


# ── C3(a): the originals travel ───────────────────────────────────────────────────────────────

def test_the_retained_original_survives_a_restore(tmp_path, cipher) -> None:  # noqa: ANN001
    """The defect, end to end: back up, restore into an empty installation, open the document. It
    used to raise ``FileNotFoundError`` on every *pièce* of every restored matter."""
    store, originals, content_hash = _seeded(tmp_path, cipher)
    bundle_dir = tmp_path / "bundle"
    coverage = write_bundle(bundle_dir, store.backup_tenant(TENANT), originals, cipher)
    assert coverage.originals == 1 and coverage.is_complete

    fresh = FilesystemOriginalStore(tmp_path / "restored-vol", cipher)
    bundle = read_bundle(bundle_dir, cipher)
    _store(tmp_path, "dst").restore_tenant(bundle.backup)
    restore_originals(bundle_dir, bundle, fresh)

    assert fresh.open(TENANT, content_hash) == BYTES


def test_the_blobs_are_copied_sealed_and_never_decrypted(tmp_path, cipher) -> None:  # noqa: ANN001
    """Taking a backup must not put a firm's corpus in the clear anywhere — not on disk, not in the
    operator's hands. The bundle's blob is the byte-for-byte ciphertext from the volume."""
    store, originals, content_hash = _seeded(tmp_path, cipher)
    bundle_dir = tmp_path / "bundle"
    write_bundle(bundle_dir, store.backup_tenant(TENANT), originals, cipher)

    on_disk = (bundle_dir / ORIGINALS_DIR / content_hash).read_bytes()
    assert on_disk == originals.read_sealed(TENANT, content_hash)
    assert BYTES not in on_disk


def test_a_blob_restored_under_another_tenant_is_unreadable(tmp_path, cipher) -> None:  # noqa: ANN001
    """The tenant boundary travels INSIDE the blob (its AAD binds tenant/hash/kind). A bundle
    restored under the wrong firm fails authentication rather than serving one firm's document as
    another's — the failure a content-addressed store would otherwise make silent."""
    store, originals, content_hash = _seeded(tmp_path, cipher)
    bundle_dir = tmp_path / "bundle"
    write_bundle(bundle_dir, store.backup_tenant(TENANT), originals, cipher)

    wrong = FilesystemOriginalStore(tmp_path / "wrong-vol", cipher)
    wrong.put_sealed(
        OTHER, content_hash, "original", (bundle_dir / ORIGINALS_DIR / content_hash).read_bytes())
    with pytest.raises(DecryptionError):
        wrong.open(OTHER, content_hash)


def test_a_derived_kind_travels_too(tmp_path, cipher) -> None:  # noqa: ANN001
    """The blob inventory is read off the STORE, not off a column. No table names the ``ocr-layout``
    a *pièce* may carry (Story 3.5c-1), so a list-driven backup would have left it behind while
    reporting that it had backed up the originals."""
    store, originals, content_hash = _seeded(tmp_path, cipher)
    originals.put(TENANT, content_hash, b"layout json", kind="ocr-layout")
    bundle_dir = tmp_path / "bundle"
    coverage = write_bundle(bundle_dir, store.backup_tenant(TENANT), originals, cipher)
    assert coverage.originals == 2

    fresh = FilesystemOriginalStore(tmp_path / "restored-vol", cipher)
    bundle = read_bundle(bundle_dir, cipher)
    restore_originals(bundle_dir, bundle, fresh)
    assert fresh.open(TENANT, content_hash, kind="ocr-layout") == b"layout json"


# ── C3(b): nothing in the bundle is in the clear ──────────────────────────────────────────────

def test_the_searchable_text_does_not_leave_the_volume_in_the_clear(tmp_path, cipher) -> None:  # noqa: ANN001
    """``chunk.full_text`` is plaintext in the database ON PURPOSE — you cannot index ciphertext —
    and volume encryption is what protects it. The bundle leaves the volume, so it seals it."""
    store, originals, _ch = _seeded(tmp_path, cipher)
    bundle_dir = tmp_path / "bundle"
    write_bundle(bundle_dir, store.backup_tenant(TENANT), originals, cipher)

    sealed = (bundle_dir / TABLES_FILE).read_bytes()
    assert SECRET.encode("utf-8") not in sealed
    assert b"provenance_path" not in sealed              # not even the column names


def test_a_bundle_does_not_open_without_the_key(tmp_path, cipher) -> None:  # noqa: ANN001
    """A stolen bundle is a stolen ciphertext. Fail closed, never a partial read."""
    store, originals, _ch = _seeded(tmp_path, cipher)
    bundle_dir = tmp_path / "bundle"
    write_bundle(bundle_dir, store.backup_tenant(TENANT), originals, cipher)
    with pytest.raises(DecryptionError):
        read_bundle(bundle_dir, Cipher(_decode_key(generate_key())))


# ── the bundle's own integrity ────────────────────────────────────────────────────────────────

def test_a_blob_missing_from_the_bundle_refuses_the_restore(tmp_path, cipher) -> None:  # noqa: ANN001
    """The sealed inventory names it, the directory does not have it: the bundle is truncated, and
    that is a named missing document rather than a count nobody was comparing."""
    store, originals, content_hash = _seeded(tmp_path, cipher)
    bundle_dir = tmp_path / "bundle"
    write_bundle(bundle_dir, store.backup_tenant(TENANT), originals, cipher)
    (bundle_dir / ORIGINALS_DIR / content_hash).unlink()

    bundle = read_bundle(bundle_dir, cipher)
    with pytest.raises(BundleFormatError, match="truncated"):
        restore_originals(bundle_dir, bundle, FilesystemOriginalStore(tmp_path / "v2", cipher))


def test_a_blob_added_to_the_bundle_afterwards_is_not_restored(tmp_path, cipher) -> None:  # noqa: ANN001
    """The inventory is INSIDE the sealed payload, so what a restore puts back is what the key
    attests. A blob dropped into the directory later is not part of the backup and does not become
    part of the firm's corpus by being in the same folder."""
    store, originals, _ch = _seeded(tmp_path, cipher)
    bundle_dir = tmp_path / "bundle"
    write_bundle(bundle_dir, store.backup_tenant(TENANT), originals, cipher)
    planted = _hash("planted")
    (bundle_dir / ORIGINALS_DIR / planted).write_bytes(b"not ours")

    fresh = FilesystemOriginalStore(tmp_path / "v2", cipher)
    bundle = read_bundle(bundle_dir, cipher)
    assert restore_originals(bundle_dir, bundle, fresh).originals == 1
    assert fresh.size(TENANT, planted) is None


def test_a_backup_over_an_existing_directory_is_refused(tmp_path, cipher) -> None:  # noqa: ANN001
    """Two backups in one directory would hold two tenants' blobs under one sealed payload naming
    one of them — and the extra blobs would restore silently, the blob face being content-addressed
    and unable to ask which backup a file came from."""
    store, originals, _ch = _seeded(tmp_path, cipher)
    bundle_dir = tmp_path / "bundle"
    write_bundle(bundle_dir, store.backup_tenant(TENANT), originals, cipher)
    with pytest.raises(FileExistsError):
        write_bundle(bundle_dir, store.backup_tenant(TENANT), originals, cipher)


def test_the_legacy_plaintext_file_is_refused_by_name(tmp_path, cipher) -> None:  # noqa: ANN001
    """A pre-7.2 backup is 20 of 35 tables with no originals. It is named and refused rather than
    read: restoring it would report success over a tenant missing every ranking, sampling run and
    validation act."""
    legacy = tmp_path / "cabinet.json"
    legacy.write_text('{"tenant": "cabinet"}', encoding="utf-8")
    with pytest.raises(BundleFormatError, match="pre-7.2"):
        read_bundle(legacy, cipher)


# ── AC-7: the recorded outcome states its coverage ────────────────────────────────────────────

def test_a_retained_piece_with_no_document_makes_the_backup_incomplete(tmp_path, cipher) -> None:  # noqa: ANN001
    """The coverage is a fact about the INSTALLATION, not about the bundle. A *pièce* the record
    says is retained, whose original is not on the volume, means the backup is not complete — and
    AD-32's whole subject is a backup whose failure nobody knew about."""
    store, originals, _ch = _seeded(tmp_path, cipher, retain=False)
    coverage = write_bundle(
        tmp_path / "bundle", store.backup_tenant(TENANT), originals, cipher)
    assert coverage.originals == 0
    assert not coverage.is_complete and coverage.orphaned_pieces == 1
    assert "INCOMPLET" in coverage.sentence_fr()


def test_a_complete_backup_says_what_it_covered(tmp_path, cipher) -> None:  # noqa: ANN001
    """And the ordinary case names the tables and the rows, so 'the backup succeeded' can no longer
    coexist with 'nine tables were not in it'."""
    store, originals, _ch = _seeded(tmp_path, cipher)
    coverage = write_bundle(tmp_path / "bundle", store.backup_tenant(TENANT), originals, cipher)
    total = len(backup_plan())                      # derived, so the number cannot go stale here
    assert coverage.tables == total and coverage.rows > 0 and coverage.is_complete
    assert f"{total} tables" in coverage.sentence_fr()
    assert "1 originaux" in coverage.sentence_fr()
