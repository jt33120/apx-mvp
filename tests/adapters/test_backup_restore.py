"""Logical, tenant-boundary backup + an exercised restore (story 1.11, AD-32/AD-35). SQLite.

Two guarantees: a restore into an EMPTY store reproduces the tenant identically (inventory, audit
sequence, configuration; the chain re-verifies; the head reconciles) — and the AD-35 mandated
test: a restore that moves the head BACKWARDS is detected as a truncation, named, and clears only
by an audited override, never repaired.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.backup_plan import backup_plan
from apx.adapters.store_postgres.models import EMBEDDING_DIM, Base, Chunk
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestedPiece, IngestionResult
from apx.core.domain.head_journal import HeadJournal, journal_scope

TENANT = "cabinet"
MATTER = "m"
#: Story 5.5 — the ingestion entries live on the MATTER chain now (AD-43); the tenant chain
#: carries provisioning, configuration and the `chain_opened` anchor. A truncation is per chain.
MATTER_CHAIN = journal_scope(TENANT, MATTER)


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
        excl = ["sub/.DS_Store"] if i == 0 else []   # one filesystem-noise exclusion (Story 2.7)
        store.save(
            IngestionResult(pieces=[_piece(f"p{i}")], exclusions=excl), "w", actor="admin")
    # a chunk with its embedding trio, to prove the halfvec vector survives backup/restore (2.8)
    with store._sf() as s, s.begin():
        s.add(Chunk(
            chunk_id="c0", piece_id="p0", tenant=TENANT, matter="m", position=0,
            full_text_version="v", chunking_config_version="c", schema_version="s1",
            model_id="bge-m3", model_version="v1", vector=[0.5] * EMBEDDING_DIM))
    store.set_config(TENANT, "admin", "interface_language", "en")


def _wipe(store: SqlStore) -> None:
    """Simulate a dump restore's clean slate: drop every row the backup plan captures, so a backup
    can be restored into the now-empty store the way real disaster recovery would.

    Driven by the plan and in REVERSE plan order (Story 7.2): a child keyed by its parent must go
    before the parent, or its predicate can no longer find it and an orphan survives to collide
    with the restore's re-insert. The old hand-rolled version cleared two child tables by name and
    would have left the other four behind."""
    plan = backup_plan()
    with store._sf() as s, s.begin():
        for cap in reversed(plan):
            s.execute(
                text(f"DELETE FROM {cap.table} WHERE {cap.predicate}"),  # noqa: S608
                {"t": TENANT})


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
    assert (dst_inv.submitted_pieces, dst_inv.in_corpus) == \
        (src_inv.submitted_pieces, src_inv.in_corpus)  # denominator survives backup/restore
    # the filesystem-noise ledger survives too — count AND the encrypted list (Story 2.7, AD-41)
    assert dst_inv.excluded_as_noise == src_inv.excluded_as_noise == 1
    assert dst.noise_exclusions("m", TENANT, {"w"}) == src.noise_exclusions("m", TENANT, {"w"})
    assert dst.audit_heads()[TENANT][0] == src_head            # audit sequence identical
    assert dst.get_config(TENANT, "interface_language") == "en"   # configuration identical
    assert dst.get_config(TENANT, "taxonomy") == ["conclusions"]
    assert dst.read_audit("m", TENANT, {"w"}).verified         # the chain re-verifies on restore
    # the piece SETS (Story 2.5) survive the round-trip — custodianship and provenance are not lost
    assert dst.custodians("p0") == src.custodians("p0") == {"custodian-x"}
    assert dst.provenances("p0") == src.provenances("p0") == {"/secret/p0.pdf"}
    # a chunk's embedding trio survives the round-trip — the model identity AND the halfvec vector
    # itself, proving the column-agnostic SELECT * backup carries the vector value, not just its
    # presence (Story 2.8, AD-11; the restore re-inserts through the same typed column).
    with dst._sf() as s:
        chunk = s.scalars(select(Chunk).where(Chunk.piece_id == "p0")).one()
    assert chunk.vector == [0.5] * EMBEDDING_DIM
    assert (chunk.model_id, chunk.model_version) == ("bge-m3", "v1")


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
    early_head = store.audit_heads()[MATTER_CHAIN][0]
    for i in range(3):                            # three MORE audited entries advance the head
        store.save(IngestionResult(pieces=[_piece(f"q{i}")]), "w", actor="admin")
    late_head = store.audit_heads()[MATTER_CHAIN][0]
    assert late_head > early_head                # the journal now records the later head

    # simulate a dump restore to the earlier point: replace the tenant's rows with the early backup
    _wipe(store)
    recs = store.restore_tenant(early)           # reconciles vs the journal (still at late_head)

    truncated = [r for r in recs if r.scope == MATTER_CHAIN and r.truncated]
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
    # EVERY chain of the tenant rides along, not just the tenant chain (Story 5.5): a journal
    # that has never heard of a matter chain cannot detect its truncation later.
    tail = {h["scope"]: h["seq"] for h in backup.head_tail}
    assert set(tail) == {TENANT, MATTER_CHAIN} and tail[MATTER_CHAIN] == 3

    j2 = HeadJournal(tmp_path / "recovered.journal")   # a fresh, empty journal (the old one's gone)
    j2.ensure_writable()
    dst = _store(tmp_path, "dst", journal=j2)
    dst.restore_tenant(backup)
    for scope, seq in tail.items():                 # seeded from the backup, not left empty
        seeded = j2.latest(scope)
        assert seeded is not None and seeded.seq == seq


# ── the review's confirmed defects (Story 5.5) ────────────────────────────────────────────────

def test_a_backup_with_no_allocator_restores_and_the_tenant_can_still_write(tmp_path) -> None:  # noqa: ANN001
    """CONFIRMED BY REVIEW, and it is every backup the live deployment holds today. A pre-5.5
    backup carries entries and no `audit_chain_head`; without a rebuild the next audited act
    allocates seq 1 again, collides with the restored entry 1, and AD-22 turns that into a refused
    action — permanently, for every act."""
    src = _store(tmp_path, "src")
    _seed(src)
    backup = src.backup_tenant(TENANT)
    backup.tables["audit_chain_head"] = []          # as a pre-5.5 backup arrives

    dst = _store(tmp_path, "dst")
    dst.restore_tenant(backup)

    # the allocator was rebuilt from the entries — not invented, derived
    heads = dst.audit_heads()
    assert set(heads) == {TENANT, MATTER_CHAIN}
    # ... and the tenant can write again, continuing each chain rather than colliding
    dst.save(IngestionResult(pieces=[_piece("after")]), "w", actor="admin")
    assert dst.audit_heads()[MATTER_CHAIN][0] == heads[MATTER_CHAIN][0] + 1


def test_a_rebuilt_chain_does_not_claim_an_anchor_nobody_recorded(tmp_path) -> None:  # noqa: ANN001
    """A rebuilt matter chain has no recorded anchor, so it reports itself as NOT verifiable in
    isolation rather than claiming one."""
    src = _store(tmp_path, "src")
    _seed(src)
    backup = src.backup_tenant(TENANT)
    backup.tables["audit_chain_head"] = []
    dst = _store(tmp_path, "dst")
    dst.restore_tenant(backup)
    trail = dst.read_audit(MATTER, TENANT, {"w"})
    own = next(s for s in trail.slices if s.chain_scope == MATTER)
    assert own.verified and own.verifiable_in_isolation is False


def test_a_backup_whose_allocator_disagrees_with_its_entries_is_refused(tmp_path) -> None:  # noqa: ANN001
    """CONFIRMED BY REVIEW. A head ahead of its record hands out numbers past a hole the continuity
    check reports forever and AD-22 forbids repairing; a head behind it re-issues numbers already
    used. Either way the restore is refused rather than accepted into a state nobody may correct."""
    src = _store(tmp_path, "src")
    _seed(src)
    backup = src.backup_tenant(TENANT)
    for row in backup.tables["audit_chain_head"]:
        if row["chain_scope"] == MATTER:
            row["seq"] = 100                        # a head far ahead of its entries
    dst = _store(tmp_path, "dst")
    with pytest.raises(ValueError, match="disagrees with the restored record"):
        dst.restore_tenant(backup)
    assert dst.audit_heads() == {}                  # atomic: nothing was committed


def test_a_truncation_across_two_chains_names_both_and_totals_the_loss(tmp_path) -> None:  # noqa: ANN001
    """CONFIRMED BY REVIEW, reproduced by a skeptic. The marker is one row per tenant, so the
    per-chain loop recorded whichever scope sorted last: two matters truncated, and the firm was
    told the smaller number and never told which matters were affected."""
    journal = HeadJournal(tmp_path / "heads.journal")
    journal.ensure_writable()
    store = _store(tmp_path, "s", journal=journal)
    store.provision_tenant(TENANT, "admin@x.fr", "pw12345678", "Admin", {"w"}, ["conclusions"])
    for i in range(4):                              # four acts on the big matter
        store.save(IngestionResult(pieces=[_piece(f"a{i}")]), "w", actor="admin",
                   matter="aaa-grosse", tenant=TENANT)
    store.save(IngestionResult(pieces=[_piece("z0")]), "w", actor="admin",
               matter="zzz-petite", tenant=TENANT)   # one act on the small one
    early = store.backup_tenant(TENANT)
    for i in range(3):                              # three more on the big matter
        store.save(IngestionResult(pieces=[_piece(f"b{i}")]), "w", actor="admin",
                   matter="aaa-grosse", tenant=TENANT)
    store.save(IngestionResult(pieces=[_piece("z1")]), "w", actor="admin",
               matter="zzz-petite", tenant=TENANT)

    _wipe(store)
    store.restore_tenant(early)

    status = store.truncation_status(TENANT)
    assert status.active
    assert status.entries_lost == 4                  # 3 on the big matter + 1 on the small one
    assert "aaa-grosse" in status.chains and "zzz-petite" in status.chains
    # the pair still describes the WORST-hit chain, never the smallest loss
    assert status.journal_seq - status.live_seq == 3


def test_a_quiet_chain_erased_after_an_override_is_still_a_truncation(tmp_path) -> None:  # noqa: ANN001
    """FOUND BY EXECUTION, not by reading. An override resets the reconciliation baseline to the
    heads recorded AFTER it. A chain that has not written since the override had no such head, so
    its baseline was zero — and nothing is below zero. Its entries and its head row could then be
    deleted WHOLESALE and the status stayed clean: the matter's entire history gone, no marker, no
    alarm, on a record whose whole purpose is that this cannot happen quietly (AD-35).

    Only per-matter chains (AD-43) opened it. Under one chain per tenant the override entry, being
    written on that chain, always supplied the baseline itself — which is exactly why the tenant
    chain still escapes here and the matter chains did not.
    """
    journal = HeadJournal(tmp_path / "heads.journal")
    journal.ensure_writable()
    store = _store(tmp_path, "s", journal=journal)
    store.provision_tenant(TENANT, "admin@x.fr", "pw12345678", "Admin", {"w"}, ["conclusions"])
    for i in range(3):
        store.save(IngestionResult(pieces=[_piece(f"a{i}")]), "w", actor="admin",
                   matter="active", tenant=TENANT)
    for i in range(3):
        store.save(IngestionResult(pieces=[_piece(f"q{i}")]), "w", actor="admin",
                   matter="dormante", tenant=TENANT)
    early = store.backup_tenant(TENANT)
    for m in ("active", "dormante"):                 # both advance past the snapshot
        store.save(IngestionResult(pieces=[_piece(f"{m}-later")]), "w", actor="admin",
                   matter=m, tenant=TENANT)

    _wipe(store)                                     # a restore truncates both chains …
    store.restore_tenant(early)
    assert store.truncation_status(TENANT).active
    store.clear_truncation(TENANT, "patron", "restauration verifiee, perte acceptee")
    assert not store.truncation_status(TENANT).active

    # … life goes on for one matter; the other says nothing more, which is an ordinary state for a
    # closed affair and must not be mistaken for having nothing to lose.
    store.save(IngestionResult(pieces=[_piece("a9")]), "w", actor="admin",
               matter="active", tenant=TENANT)
    dormante = journal_scope(TENANT, "dormante")
    assert store.audit_heads()[dormante][0] == 3     # three entries, standing since the override

    with store._sf() as s, s.begin():                # the dormant matter's chain, erased entirely
        s.execute(text("DELETE FROM audit_record WHERE tenant = 'cabinet' "
                       "AND chain_scope = 'dormante'"))
        s.execute(text("DELETE FROM audit_chain_head WHERE tenant = 'cabinet' "
                       "AND chain_scope = 'dormante'"))

    recs = store.reconcile_heads()
    (gone,) = [r for r in recs if r.scope == dormante]
    assert gone.truncated and gone.live_seq == 0 and gone.journal_seq == 3
    status = store.truncation_status(TENANT)
    assert status.active and status.entries_lost == 3
    assert "dormante" in status.chains
