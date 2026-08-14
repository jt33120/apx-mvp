"""The witness is compared, not counted (Story 5.9, FR-53 AC-8 / AD-35).

The head journal has recorded a chain VALUE on every advance since Story 1.11, and until this story
nothing ever read it back: ``reconcile`` compared sequence numbers, ``Reconciliation`` had no chain
field, and ``HeadEntry.chain`` was written by four call sites and read by none.

What that left open is exact, and Story 5.5 wrote it down after two skeptics reproduced it: the
chain is an unkeyed SHA-256 and the anchor is a plaintext column, so anyone with write access
rewrites the entries, **re-chains them from the true anchor**, and leaves the record internally
perfect — every link recomputes, the allocator agrees with its entries, the length never moved. Both
sides of every check the product ran lived inside the restorable store.

These tests forge exactly that record and assert the journal catches it.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import AuditRecord, Base, TruncationMarker
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestedPiece, IngestionResult
from apx.core.domain import audit
from apx.core.domain.head_journal import HeadEntry, HeadJournal, journal_scope

TENANT, MATTER, WALL = "cabinet", "affaire-a", "mur-a"
TENANT_CHAIN = journal_scope(TENANT, audit.TENANT_CHAIN)
MATTER_CHAIN = journal_scope(TENANT, MATTER)


def _piece(pid: str) -> IngestedPiece:
    return IngestedPiece(
        id=pid, matter=MATTER, tenant=TENANT, content_hash=pid * 8, text_key=pid * 8,
        provenance_path=f"/dossier/{pid}.pdf", custodian="Me Martin", extraction_method="text",
        extractor_version="v1", schema_version="slice-a",
        ingestion_timestamp=datetime.now(UTC), full_text="le contrat", text_version="v")


@pytest.fixture
def journal(tmp_path) -> HeadJournal:  # noqa: ANN001
    # On its OWN volume, as AD-35 requires — here, its own directory, so the test that makes the
    # journal unwritable does not also make the database unwritable and prove nothing.
    directory = tmp_path / "outside"
    directory.mkdir()
    return HeadJournal(directory / "heads.journal")


@pytest.fixture
def store(tmp_path, journal: HeadJournal) -> SqlStore:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx'}.db", future=True)
    Base.metadata.create_all(engine)
    s = SqlStore(sessionmaker(bind=engine, future=True), head_journal=journal)
    for i in range(3):
        s.save(IngestionResult(pieces=[_piece(f"p{i}")]), WALL, actor="Me Dupont",
               matter=MATTER, tenant=TENANT)
    return s


def _entries(store: SqlStore, scope: str) -> list[AuditRecord]:
    with store._sf() as session:
        return list(session.scalars(
            select(AuditRecord)
            .where(AuditRecord.tenant == TENANT, AuditRecord.chain_scope == scope)
            .order_by(AuditRecord.seq)))


def _rechain_from_the_true_anchor(store: SqlStore, scope: str, at_seq: int, detail: str) -> None:
    """The forgery, performed properly: rewrite one entry and recompute EVERY chain value after it
    from the real anchor, so the record that comes out is internally flawless. Anything less would
    be caught by the ordinary verifier and would prove nothing about the witness."""
    rows = _entries(store, scope)
    with store._sf() as session, session.begin():
        prev = session.scalar(
            select(AuditRecord.chain).where(
                AuditRecord.tenant == TENANT, AuditRecord.chain_scope == scope,
                AuditRecord.seq == at_seq - 1)) if at_seq > 1 else _anchor(store, scope)
        for row in rows:
            if row.seq < at_seq:
                continue
            new_detail = detail if row.seq == at_seq else row.detail
            content = audit.chained_content(
                version=row.content_version, seq=row.seq, tenant=row.tenant,
                chain_scope=row.chain_scope, matter=row.matter, actor=row.actor,
                action=row.action, detail=new_detail,
                timestamp=_ts(row.timestamp), app_version=row.app_version or "",
                schema_version=row.schema_version or "")
            prev = audit.chain_value(prev or "", content)
            session.execute(
                update(AuditRecord)
                .where(AuditRecord.id == row.id)
                .values(detail=new_detail, chain=prev))
        session.execute(
            update(_head()).where(
                _head().c.tenant == TENANT, _head().c.chain_scope == scope
            ).values(chain=prev))


def _head():  # noqa: ANN202
    from apx.adapters.store_postgres.models import AuditChainHead
    return AuditChainHead.__table__


def _anchor(store: SqlStore, scope: str) -> str:
    from apx.adapters.store_postgres.models import AuditChainHead
    with store._sf() as session:
        return session.scalar(
            select(AuditChainHead.anchor).where(
                AuditChainHead.tenant == TENANT, AuditChainHead.chain_scope == scope)) or ""


def _ts(value) -> str:  # noqa: ANN001
    from apx.adapters.store_postgres.store import _audit_ts
    return _audit_ts(value)


# ── AC-8: a record rewritten and re-chained to the same length is a FORK ───────────────────────

def test_a_rechained_record_of_the_same_length_passes_every_in_store_check(
    store: SqlStore,
) -> None:
    """The premise. If this failed, the fork check below would be proving something easier than the
    thing it is for."""
    before = len(_entries(store, MATTER))
    _rechain_from_the_true_anchor(store, MATTER, at_seq=2, detail="corrigé après coup")
    assert len(_entries(store, MATTER)) == before, "the forgery must not change the length"
    with store._sf() as session:
        assert store._chain_verifies(session, TENANT), (
            "the forged record must verify from inside the store — that is the whole problem")


def test_the_journal_catches_the_fork_the_store_cannot_see(
    store: SqlStore, journal: HeadJournal
) -> None:
    _rechain_from_the_true_anchor(store, MATTER, at_seq=2, detail="corrigé après coup")
    recs = {r.scope: r for r in store.reconcile_heads()}
    forked = recs[MATTER_CHAIN]
    assert forked.forked, "the rewritten chain was not detected"
    assert not forked.truncated, "a rewrite is not a truncation and must not be reported as one"
    assert forked.journal_chain and forked.live_chain
    assert forked.journal_chain != forked.live_chain
    assert forked.witnessed_seq > 0, "the comparison must name the sequence it was taken at"


def test_a_fork_is_recorded_as_a_persistent_marker_of_its_own_kind(store: SqlStore) -> None:
    _rechain_from_the_true_anchor(store, MATTER, at_seq=2, detail="corrigé après coup")
    store.reconcile_heads()
    status = store.truncation_status(TENANT)
    assert status.active and status.kind == TruncationMarker.KIND_FORKED
    assert MATTER in status.forks
    # A fork loses no ACTS. Folding it into entries_lost would print a reassuring number under a
    # heading that does not apply to it.
    assert status.entries_lost == 0 and status.chains == ""


def test_an_untampered_record_is_neither_forked_nor_truncated(store: SqlStore) -> None:
    recs = store.reconcile_heads()
    assert recs and not any(r.diverged for r in recs)
    assert not store.truncation_status(TENANT).active


def test_a_fork_and_a_truncation_together_are_reported_as_both(
    store: SqlStore, journal: HeadJournal
) -> None:
    """A restore rolls the whole database back, so one detection can find each on different chains.
    The marker names both rather than reporting whichever sorted last."""
    _rechain_from_the_true_anchor(store, MATTER, at_seq=2, detail="corrigé après coup")
    # the tenant chain, meanwhile, is claimed by the journal to have run further than it does
    journal.record(HeadEntry(TENANT_CHAIN, 99, "z" * 64, "2999-01-01T00:00:00.000000", "0", "s"))
    store.reconcile_heads()
    status = store.truncation_status(TENANT)
    assert status.kind == TruncationMarker.KIND_BOTH
    assert MATTER in status.forks and TENANT_CHAIN.split("\x1f")[0] in status.chains


# ── the evidence is not overwritten by the next boot ───────────────────────────────────────────

def test_recording_the_current_heads_skips_a_tenant_under_dispute(store: SqlStore) -> None:
    """``record_current_heads`` runs immediately after the boot reconcile. Writing the live head of
    a record already found discontinuous would enter the disputed value AS the outside witness,
    after which the next boot compares it against a copy of itself and finds nothing."""
    _rechain_from_the_true_anchor(store, MATTER, at_seq=2, detail="corrigé après coup")
    store.reconcile_heads()
    assert store.truncation_status(TENANT).active
    assert store.record_current_heads() == 0, "the disputed heads must not be journalled"
    # and the finding survives a second reconciliation rather than being answered by its own copy
    store.reconcile_heads()
    assert store.truncation_status(TENANT).active
    assert any(r.forked for r in store.reconcile_heads())


# ── an unwitnessed acknowledgement cannot lower the bar ────────────────────────────────────────

def test_a_clearance_the_journal_never_witnessed_does_not_reset_the_baseline(
    store: SqlStore, journal: HeadJournal
) -> None:
    """``truncation_marker`` travels inside the backup, so a forger can supply one — and the
    post-override baseline used to be derived from its ``cleared_at`` with ``default=0``. A
    future-dated clearance produced no post-clear journal lines, the reference collapsed to zero,
    nothing is below zero, and that chain became permanently unfalsifiable."""
    journal.record(HeadEntry(MATTER_CHAIN, 500, "y" * 64, "2026-01-01T00:00:00.000000", "0", "s"))
    with store._sf() as session, session.begin():
        session.merge(TruncationMarker(
            tenant=TENANT, detected_at=datetime.now(UTC), journal_seq=1, live_seq=1,
            kind=TruncationMarker.KIND_TRUNCATED, chains="", entries_lost=0,
            cleared_by="forger", reason="acquitté", cleared_at=datetime(2999, 1, 1, tzinfo=UTC)))
    recs = {r.scope: r for r in store.reconcile_heads()}
    assert recs[MATTER_CHAIN].truncated, (
        "an acknowledgement the journal never witnessed must not lower the bar to zero")


# ── the seed from an untrusted backup ──────────────────────────────────────────────────────────

def test_a_backup_head_tail_never_overwrites_a_witness_the_journal_already_holds(
    store: SqlStore, journal: HeadJournal
) -> None:
    """The head tail comes from the backup file, which is exactly the artefact a forger controls,
    and ``witness_upto`` answers with the LAST line at a sequence. Seeding a scope the journal
    already witnesses would let the attacker choose the value they are compared against."""
    backup = store.backup_tenant(TENANT)
    honest = journal.latest(MATTER_CHAIN)
    assert honest is not None
    poisoned = dict(vars(honest))
    poisoned["chain"] = "f" * 64
    backup.head_tail.append(poisoned)
    store._seed_journal_from_backup(backup, journal)
    assert journal.latest(MATTER_CHAIN).chain == honest.chain, (
        "the supplied head replaced the witness it was going to be compared against")


def test_a_head_tail_with_a_wrong_typed_sequence_cannot_brick_the_boot(
    store: SqlStore, journal: HeadJournal
) -> None:
    """A dataclass does not check types and the journal is append-only. One line carrying
    ``"seq": "9999"`` used to be appended straight from an untrusted backup and then raise
    ``TypeError`` comparing str to int in EVERY later reconciliation — including the one in the boot
    path — with no way to remove the line."""
    journal.record(HeadEntry("autre-cabinet", 1, "a" * 64, "2026-01-01T00:00:00.000000", "0", "s"))
    with journal.path.open("a", encoding="utf-8") as fh:
        fh.write('{"scope": "autre-cabinet", "seq": "9999", "chain": "b", '
                 '"recorded_at": "x", "app_version": "0", "schema_version": "s"}\n')
    assert [e.seq for e in journal.entries() if e.scope == "autre-cabinet"] == [1], (
        "the poisoned line must be skipped on read — it can never be removed")
    store.reconcile_heads()  # must not raise


# ── the alarm survives the restart that used to clear it ───────────────────────────────────────

def test_a_head_the_journal_could_not_record_is_persisted_and_counted(
    store: SqlStore, journal: HeadJournal
) -> None:
    """``journal_degraded`` was a boolean in one process's memory: it cleared on the next deploy,
    the import worker could never raise it, and clearing it required nothing at all. A head we could
    not record is exactly the point a later truncation becomes undetectable."""
    assert store.journal_gap_status(TENANT).gaps == 0
    journal.path.chmod(0o400)
    journal.path.parent.chmod(0o500)
    try:
        store.save(IngestionResult(pieces=[_piece("p9")]), WALL, actor="Me Dupont",
                   matter=MATTER, tenant=TENANT)
    finally:
        journal.path.parent.chmod(0o700)
        journal.path.chmod(0o600)
    gaps = store.journal_gap_status(TENANT)
    assert gaps.gaps >= 1 and gaps.last_scope and gaps.last_seq > 0
    assert store.journal_degraded
    # …and it is a ROW, so a fresh process still sees it
    fresh = SqlStore(store._sf, head_journal=journal)
    assert not fresh.journal_degraded, "the flag is per-process, which is why the row exists"
    assert fresh.journal_gap_status(TENANT).gaps >= 1


# ── the comparison is taken at EVERY witnessed point, not only the newest ──────────────────────

def test_a_fork_survives_the_commits_that_come_after_it(
    store: SqlStore, journal: HeadJournal
) -> None:
    """Found by review. Comparing only the newest journal line made the detection survive exactly
    ONE reconciliation: the forged record goes on writing, every commit journals a head at a higher
    sequence, and the next comparison then takes a line the forgery itself produced — which matches.
    The disagreement is looked for at the earliest witnessed point instead, where a rewrite of
    history shows up and nothing written afterwards can paper over it."""
    _rechain_from_the_true_anchor(store, MATTER, at_seq=2, detail="corrigé après coup")
    assert any(r.forked for r in store.reconcile_heads())
    # the record goes on living: more acts, more journalled heads, all of them post-forgery
    for i in range(3, 6):
        store.save(IngestionResult(pieces=[_piece(f"p{i}")]), WALL, actor="Me Dupont",
                   matter=MATTER, tenant=TENANT)
    later = {r.scope: r for r in store.reconcile_heads()}
    assert later[MATTER_CHAIN].forked, (
        "the fork was laundered by the heads the forged record journalled after it")
    assert later[MATTER_CHAIN].witnessed_seq <= 2, (
        "the disagreement must be reported where it starts, not where it was last looked for")


def test_an_acknowledged_fork_stops_firing(store: SqlStore) -> None:
    """The override is the one way out (AD-35), and it has to actually work: a signed statement that
    *the record as it stands is the record* must not be answered forever by the lines it was signed
    to settle."""
    _rechain_from_the_true_anchor(store, MATTER, at_seq=2, detail="corrigé après coup")
    store.reconcile_heads()
    store.clear_truncation(TENANT, "le patron", "registre reconstitué après incident, vérifié")
    assert not store.truncation_status(TENANT).active
    store.reconcile_heads()
    assert not store.truncation_status(TENANT).active, "an acknowledged fork was re-flagged"


def test_the_cover_note_names_a_fork_instead_of_counting_zero_missing_acts(
    store: SqlStore,
) -> None:
    """A fork loses no acts, so the note that counted them printed *"0 acte(s) manquant(s)"* on a
    document whose record had been rewritten — a zero a reader would take for reassurance."""
    from apx.adapters.store_postgres.store import _discontinuity_note_fr

    _rechain_from_the_true_anchor(store, MATTER, at_seq=2, detail="corrigé après coup")
    store.reconcile_heads()
    note = _discontinuity_note_fr(store.truncation_status(TENANT))
    assert "réécrit" in note and "manquant" not in note
    assert "0 " not in note


def test_an_entry_removed_at_a_witnessed_point_is_a_disagreement_not_a_silence(
    store: SqlStore,
) -> None:
    """Found by review. The guard skipped a MISSING live value on the reasoning that a removed entry
    "is a truncation and is reported as one" — but the truncation test compares the head ROW's
    sequence, which deleting from the middle leaves exactly where it was. An act the witness saw,
    removed, was therefore reported as nothing at all: the guard named one table and the comparison
    it deferred to read another."""
    rows = _entries(store, MATTER)
    victim = rows[len(rows) // 2]
    with store._sf() as session, session.begin():
        session.execute(
            AuditRecord.__table__.delete().where(AuditRecord.__table__.c.id == victim.id))
    recs = {r.scope: r for r in store.reconcile_heads()}
    assert recs[MATTER_CHAIN].diverged, "an entry the witness saw was removed and nothing said so"
    assert recs[MATTER_CHAIN].witnessed_seq == victim.seq
    assert recs[MATTER_CHAIN].live_chain == "", "the record holds nothing there — and says so"
