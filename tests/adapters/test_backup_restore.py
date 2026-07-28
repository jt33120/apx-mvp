"""Logical, tenant-boundary backup + an exercised restore (story 1.11, AD-32/AD-35). SQLite.

Two guarantees: a restore into an EMPTY store reproduces the tenant identically (inventory, audit
sequence, configuration; the chain re-verifies; the head reconciles) — and the AD-35 mandated
test: a restore that moves the head BACKWARDS is detected as a truncation, named, and clears only
by an audited override, never repaired.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import _BACKUP_TABLES, SqlStore
from apx.core.app.ingest import IngestedPiece, IngestionResult
from apx.core.domain.head_journal import HeadJournal

TENANT = "cabinet"


def _store(tmp_path, name: str, journal: HeadJournal | None = None) -> SqlStore:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / name}.db", future=True)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True), head_journal=journal)


def _piece(pid: str) -> IngestedPiece:
    return IngestedPiece(
        id=pid, matter="m", tenant=TENANT, content_hash=pid * 8, text_key=pid * 8,
        provenance_path=f"/secret/{pid}.pdf", custodian="custodian-x", extraction_method="text",
        extractor_version="v1", schema_version="s1", ingestion_timestamp=datetime.now(UTC),
        full_text="le contrat", text_version="v")


def _seed(store: SqlStore) -> None:
    store.provision_tenant(TENANT, "admin@x.fr", "pw12345678", "Admin", {"w"}, ["conclusions"])
    for i in range(3):
        store.save(IngestionResult(pieces=[_piece(f"p{i}")]), "w", actor="admin")
    store.set_config(TENANT, "admin", "interface_language", "en")


def _wipe(store: SqlStore) -> None:
    """Simulate a dump restore's clean slate: drop every tenant-owned row (and user_scope), so a
    backup can be restored into the now-empty store the way real disaster recovery would."""
    with store._sf() as s, s.begin():
        # the piece SETS (Story 2.5) reference pieces by id (no tenant column) — clear them BEFORE
        # the pieces, so no orphan link row survives to collide with the restore's re-insert.
        for tbl in ("piece_provenance", "piece_custodian"):
            s.execute(text(
                f"DELETE FROM {tbl} WHERE piece_id IN "  # noqa: S608
                "(SELECT id FROM piece WHERE tenant = 'cabinet')"))
        for tbl in _BACKUP_TABLES:
            s.execute(text(f"DELETE FROM {tbl} WHERE tenant = 'cabinet'"))  # noqa: S608
        s.execute(text("DELETE FROM user_scope"))


def test_backup_restore_reproduces_the_tenant_identically(tmp_path) -> None:  # noqa: ANN001
    src = _store(tmp_path, "src")
    _seed(src)
    src_inv = src.inventory("m", TENANT, {"w"})
    src_head = src.audit_heads()[TENANT][0]

    backup = src.backup_tenant(TENANT)
    dst = _store(tmp_path, "dst")
    recs = dst.restore_tenant(backup)

    assert not any(r.truncated for r in recs)                 # a clean restore is not a truncation
    dst_inv = dst.inventory("m", TENANT, {"w"})
    assert (dst_inv.submitted, dst_inv.in_corpus) == (src_inv.submitted, src_inv.in_corpus)  # denom
    assert dst.audit_heads()[TENANT][0] == src_head            # audit sequence identical
    assert dst.get_config(TENANT, "interface_language") == "en"   # configuration identical
    assert dst.get_config(TENANT, "taxonomy") == ["conclusions"]
    assert dst.read_audit("m", TENANT, {"w"}).verified         # the chain re-verifies on restore
    # the piece SETS (Story 2.5) survive the round-trip — custodianship and provenance are not lost
    assert dst.custodians("p0") == src.custodians("p0") == {"custodian-x"}
    assert dst.provenances("p0") == src.provenances("p0") == {"/secret/p0.pdf"}


def test_backup_preserves_ciphertext(tmp_path) -> None:  # noqa: ANN001
    src = _store(tmp_path, "src")
    _seed(src)
    backup = src.backup_tenant(TENANT)
    provenance = backup.tables["piece"][0]["provenance_path"]
    assert provenance.startswith("apxenc:")   # content stays ENCRYPTED in the backup, not plaintext


def test_restore_refuses_a_non_empty_tenant(tmp_path) -> None:  # noqa: ANN001
    src = _store(tmp_path, "src")
    _seed(src)
    backup = src.backup_tenant(TENANT)
    with pytest.raises(ValueError, match="already has"):
        src.restore_tenant(backup)   # src already holds the tenant — restore is into an EMPTY store


def test_a_restore_that_truncates_is_detected_named_and_cleared_only_by_override(
    tmp_path,  # noqa: ANN001
) -> None:
    # AD-35's mandated test: restore a snapshot taken before later entries → truncation detected.
    journal = HeadJournal(tmp_path / "heads.journal")
    journal.ensure_writable()
    store = _store(tmp_path, "s", journal=journal)
    _seed(store)
    early = store.backup_tenant(TENANT)          # a backup at the EARLY head
    early_head = store.audit_heads()[TENANT][0]
    for i in range(3):                            # three MORE audited entries advance the head
        store.save(IngestionResult(pieces=[_piece(f"q{i}")]), "w", actor="admin")
    late_head = store.audit_heads()[TENANT][0]
    assert late_head > early_head                # the journal now records the later head

    # simulate a dump restore to the earlier point: replace the tenant's rows with the early backup
    _wipe(store)
    recs = store.restore_tenant(early)           # reconciles vs the journal (still at late_head)

    truncated = [r for r in recs if r.scope == TENANT and r.truncated]
    assert truncated and truncated[0].live_seq == early_head
    assert truncated[0].journal_seq == late_head
    # NAMED: the truncation status is active (an export consults this; exports are epics 6.1/6.2)
    ts = store.truncation_status(TENANT)
    assert ts.active and ts.journal_seq == late_head and ts.live_seq == early_head
    # NEVER repaired: re-reconciling keeps it active
    store.reconcile_heads()
    assert store.truncation_status(TENANT).active
    # cleared ONLY by an audited override with a reason
    with pytest.raises(ValueError):
        store.clear_truncation(TENANT, "patron", "   ")   # an empty reason is refused
    store.clear_truncation(TENANT, "patron", "restored from a verified backup after disk failure")
    assert not store.truncation_status(TENANT).active
    # an acknowledged truncation is not re-flagged on the next reconcile (never un-cleared)
    store.reconcile_heads()
    assert not store.truncation_status(TENANT).active


def test_a_second_truncation_after_an_override_is_not_swallowed(tmp_path) -> None:  # noqa: ANN001
    # AD-35 regression (review A-HIGH1): once a truncation is acknowledged, a LATER restore that
    # lands back INSIDE the old acknowledged band — while the append-only journal's max still sits
    # at the stale pre-truncation head — must NOT be swallowed as "the same cleared truncation".
    journal = HeadJournal(tmp_path / "heads.journal")
    journal.ensure_writable()
    store = _store(tmp_path, "s", journal=journal)
    _seed(store)                                   # head → 7
    early = store.backup_tenant(TENANT)            # snapshot @ 7
    for i in range(3):
        store.save(IngestionResult(pieces=[_piece(f"q{i}")]), "w", actor="admin")  # head → 10

    # first truncation → detected → acknowledged by an audited override (advances the head to 8)
    _wipe(store)
    store.restore_tenant(early)
    assert store.truncation_status(TENANT).active
    store.clear_truncation(TENANT, "patron", "verified backup restore #1")
    assert not store.truncation_status(TENANT).active

    mid = store.backup_tenant(TENANT)              # snapshot @ 8 — the post-override baseline
    store.save(IngestionResult(pieces=[_piece("r0")]), "w", actor="admin")  # head → 9 (still ≤ 10)

    # a SECOND restore back to 8 — inside the acknowledged [7,10] band, journal max still 10, so
    # the pre-fix skip clause swallowed it. Post-override baseline is 9; live 8 < 9 → must flag.
    _wipe(store)
    store.restore_tenant(mid)
    assert store.truncation_status(TENANT).active  # the fresh data loss is not silently accepted


def test_restore_rejects_a_corrupt_audit_chain(tmp_path) -> None:  # noqa: ANN001
    # A corrupt/tampered backup must be rejected AT RESTORE (inside the tx → rollback), not silently
    # accepted and only caught later when someone happens to read the trail (review B-M2).
    src = _store(tmp_path, "src")
    _seed(src)
    backup = src.backup_tenant(TENANT)
    backup.tables["audit_record"][1]["chain"] = "0" * 64   # break one link's chain value
    dst = _store(tmp_path, "dst")
    with pytest.raises(ValueError, match="does not verify"):
        dst.restore_tenant(backup)
    assert dst.audit_heads() == {}                         # atomic: nothing was committed


def test_a_failed_head_write_is_surfaced_as_degraded(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    # AC5 / review A-HIGH2: a post-commit head-journal write failure is SURFACED (the sticky
    # journal_degraded flag the DR status reads), never swallowed silently.
    journal = HeadJournal(tmp_path / "heads.journal")
    journal.ensure_writable()
    store = _store(tmp_path, "s", journal=journal)
    _seed(store)
    assert store.journal_degraded is False

    def _boom(_entry) -> None:  # noqa: ANN001
        raise OSError("disk full")

    monkeypatch.setattr(journal, "record", _boom)
    store.save(IngestionResult(pieces=[_piece("z0")]), "w", actor="admin")  # commit; head fails
    assert store.journal_degraded is True          # the commit still succeeded; the flag is raised


def test_restore_seeds_a_fresh_journal_from_the_backup_head_tail(tmp_path) -> None:  # noqa: ANN001
    # True DR (review C-M4/A-MED4): the journal died WITH the primary. The backup carries a copy of
    # the head tail (AD-35); restore seeds it into the FRESH journal, so the outside record survives
    # the disaster instead of resetting to empty (which would make later truncations undetectable).
    j1 = HeadJournal(tmp_path / "primary.journal")
    j1.ensure_writable()
    src = _store(tmp_path, "src", journal=j1)
    _seed(src)                                     # head → 7
    backup = src.backup_tenant(TENANT)
    assert backup.head_tail and backup.head_tail[0]["seq"] == 7   # the tail rode along on it

    j2 = HeadJournal(tmp_path / "recovered.journal")   # a fresh, empty journal (the old one's gone)
    j2.ensure_writable()
    dst = _store(tmp_path, "dst", journal=j2)
    dst.restore_tenant(backup)
    seeded = j2.latest(TENANT)
    assert seeded is not None and seeded.seq == 7   # seeded from the backup, not left empty
