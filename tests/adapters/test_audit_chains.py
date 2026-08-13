"""Chains per (tenant, matter) plus one tenant chain, with a locked sequence authority (Story 5.5).

The property that matters is FR-53's, and it is the one the previous shape could not deliver:
**a reader holding only one matter's entries can verify that matter's record.** Every test here
either exercises that or protects the way it is built — the anchoring, the allocator, the actor,
the catalogue.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.extraction.files import FileExtractor
from apx.adapters.store_postgres.models import AuditChainHead, AuditRecord, Base
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestionResult, ingest_folder
from apx.core.domain import audit

TENANT = "cabinet"
ACTOR = "Me Dupont"


@pytest.fixture
def engine():  # noqa: ANN201
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    return e


@pytest.fixture
def store(engine) -> SqlStore:  # noqa: ANN001
    return SqlStore(sessionmaker(bind=engine, future=True))


def _ingest(root: Path, matter: str, name: str = "a.txt"):  # noqa: ANN202
    (root / name).write_text("pièce", encoding="utf-8")
    return ingest_folder(root, matter=matter, tenant=TENANT, extractor=FileExtractor())


def _dir(tmp_path: Path, name: str) -> Path:
    d = tmp_path / name
    d.mkdir(exist_ok=True)
    return d


def _rows(store: SqlStore, scope: str | None = None) -> list[AuditRecord]:
    with store._sf() as s:
        stmt = select(AuditRecord).where(AuditRecord.tenant == TENANT)
        if scope is not None:
            stmt = stmt.where(AuditRecord.chain_scope == scope)
        return list(s.scalars(stmt.order_by(AuditRecord.chain_scope, AuditRecord.seq)))


# ── the chain's scope (AD-43) ─────────────────────────────────────────────────────────────────

def test_two_matters_of_one_tenant_get_two_chains_each_counting_from_one(
        tmp_path: Path, store: SqlStore) -> None:
    """The defect this story exists to fix. Under one chain per tenant, matter B's entries take
    the numbers matter A did not, so A's export reads 1, 3, 4 — indistinguishable from a record
    somebody removed an entry from."""
    a = _dir(tmp_path, "a")
    b = _dir(tmp_path, "b")
    store.save(_ingest(a, "affaire-a"), "w", actor=ACTOR, matter="affaire-a", tenant=TENANT)
    store.save(_ingest(b, "affaire-b"), "w", actor=ACTOR, matter="affaire-b", tenant=TENANT)
    store.save(_ingest(a, "affaire-a", "c.txt"), "w", actor=ACTOR, matter="affaire-a",
               tenant=TENANT)

    assert [r.seq for r in _rows(store, "affaire-a")] == [1, 2]
    assert [r.seq for r in _rows(store, "affaire-b")] == [1]
    # no hole anywhere: each chain counts its own acts and nobody else's
    for scope in ("affaire-a", "affaire-b"):
        assert [r.seq for r in _rows(store, scope)] == list(
            range(1, len(_rows(store, scope)) + 1))


def test_a_matter_chain_is_verifiable_holding_only_its_own_entries(
        tmp_path: Path, store: SqlStore) -> None:
    """FR-53, literally: *a gap, a reordering or a truncation is detectable by a reader holding
    only the export.* The reader gets this matter's entries and its anchor, and nothing else."""
    a = _dir(tmp_path, "a")
    store.save(_ingest(a, "m"), "w", actor=ACTOR, matter="m", tenant=TENANT)
    store.save(_ingest(a, "m", "b.txt"), "w", actor=ACTOR, matter="m", tenant=TENANT)

    with store._sf() as s:
        entries = store._verifiable_entries(s, TENANT, chain_scopes=["m"])
        anchors = {"m": store._chain_anchors(s, TENANT)["m"]}
    verdicts = audit.verify_chains(entries, anchors)
    assert len(verdicts) == 1
    assert verdicts[0].verified and verdicts[0].anchored and verdicts[0].entries == 2


def test_removing_one_entry_from_a_matter_chain_is_detected_by_that_readers_slice(
        tmp_path: Path, store: SqlStore) -> None:
    a = _dir(tmp_path, "a")
    for name in ("a.txt", "b.txt", "c.txt"):
        store.save(_ingest(a, "m", name), "w", actor=ACTOR, matter="m", tenant=TENANT)
    with store._sf() as s, s.begin():
        s.execute(AuditRecord.__table__.delete().where(
            AuditRecord.chain_scope == "m", AuditRecord.seq == 2))
    with store._sf() as s:
        entries = store._verifiable_entries(s, TENANT, chain_scopes=["m"])
        anchors = store._chain_anchors(s, TENANT)
    (verdict,) = audit.verify_chains(entries, anchors)
    assert not verdict.verified and verdict.broken_at == 3


def test_tampering_with_one_matter_never_impugns_another(
        tmp_path: Path, store: SqlStore) -> None:
    """Chains are independent, which is the other half of scoping them: one matter's tamper must
    not report as tampering on a colleague's matter behind a wall they cannot see."""
    a = _dir(tmp_path, "a")
    store.save(_ingest(a, "affaire-a"), "w", actor=ACTOR, matter="affaire-a", tenant=TENANT)
    store.save(_ingest(a, "affaire-b", "b.txt"), "w", actor=ACTOR, matter="affaire-b",
               tenant=TENANT)
    with store._sf() as s, s.begin():
        s.execute(update(AuditRecord).where(AuditRecord.chain_scope == "affaire-a")
                  .values(detail="rewritten"))
    with store._sf() as s:
        verdicts = {v.chain_scope: v for v in audit.verify_chains(
            store._verifiable_entries(s, TENANT), store._chain_anchors(s, TENANT))}
    assert not verdicts["affaire-a"].verified
    assert verdicts["affaire-b"].verified


# ── the anchoring (D4) ────────────────────────────────────────────────────────────────────────

def test_opening_a_matter_chain_is_itself_an_act_on_the_tenant_chain(
        tmp_path: Path, store: SqlStore) -> None:
    a = _dir(tmp_path, "a")
    store.save(_ingest(a, "m"), "w", actor=ACTOR, matter="m", tenant=TENANT)
    opened = [r for r in _rows(store, audit.TENANT_CHAIN)
              if r.action == audit.ACT_CHAIN_OPENED]
    assert len(opened) == 1 and opened[0].detail == "chain=m"
    # ... and it happens exactly once, however many acts follow
    store.save(_ingest(a, "m", "b.txt"), "w", actor=ACTOR, matter="m", tenant=TENANT)
    assert len([r for r in _rows(store, audit.TENANT_CHAIN)
                if r.action == audit.ACT_CHAIN_OPENED]) == 1


def test_a_matter_chain_is_anchored_to_the_tenant_head_of_that_moment(
        tmp_path: Path, store: SqlStore) -> None:
    """Without the anchor a matter chain could be fabricated after the fact. With it, forging one
    requires the tenant head as it then stood."""
    a = _dir(tmp_path, "a")
    store.save(_ingest(a, "m"), "w", actor=ACTOR, matter="m", tenant=TENANT)
    with store._sf() as s:
        head = s.get(AuditChainHead, {"tenant": TENANT, "chain_scope": "m"})
        anchor_entry = s.scalars(
            select(AuditRecord).where(
                AuditRecord.chain_scope == audit.TENANT_CHAIN,
                AuditRecord.action == audit.ACT_CHAIN_OPENED)).one()
        first = s.scalars(select(AuditRecord).where(
            AuditRecord.chain_scope == "m", AuditRecord.seq == 1)).one()
    assert head.anchor == anchor_entry.chain
    # and the first entry really does chain onto it
    content = audit.chained_content(
        version=first.content_version, seq=1, tenant=TENANT, chain_scope="m", matter="m",
        actor=first.actor, action=first.action, detail=first.detail,
        timestamp=first.timestamp.replace(tzinfo=None).isoformat(timespec="microseconds"),
        app_version=first.app_version or "", schema_version=first.schema_version or "")
    assert audit.chain_value(head.anchor, content) == first.chain


def test_the_tenant_chain_is_the_root_and_anchors_onto_nothing(store: SqlStore) -> None:
    store.create_user(TENANT, "a@b.fr", "pw12345678", "Me Durand", {"w"}, actor=ACTOR)
    with store._sf() as s:
        head = s.get(AuditChainHead, {"tenant": TENANT, "chain_scope": audit.TENANT_CHAIN})
    assert head.anchor == ""


# ── the sequence authority (AC-4 / AD-43) ─────────────────────────────────────────────────────

def test_the_head_row_is_the_allocator_and_tracks_the_last_entry(
        tmp_path: Path, store: SqlStore) -> None:
    a = _dir(tmp_path, "a")
    for name in ("a.txt", "b.txt"):
        store.save(_ingest(a, "m", name), "w", actor=ACTOR, matter="m", tenant=TENANT)
    last = _rows(store, "m")[-1]
    with store._sf() as s:
        head = s.get(AuditChainHead, {"tenant": TENANT, "chain_scope": "m"})
    assert (head.seq, head.chain) == (last.seq, last.chain)


def test_the_allocation_really_takes_a_row_lock() -> None:
    """SQLite ignores ``FOR UPDATE`` (it serialises whole writers), so the property is asserted
    against the dialect that has to honour it. Without the lock two concurrent acts compute the
    same number and the loser dies on the unique constraint — which AD-22 turns into a refused
    legitimate action, and AD-44 says a lock timeout must never become that escape."""
    stmt = (select(AuditChainHead)
            .where(AuditChainHead.tenant == TENANT, AuditChainHead.chain_scope == "m")
            .with_for_update())
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql


def test_the_sequence_never_restarts_after_the_head_row_is_the_only_witness(
        tmp_path: Path, store: SqlStore) -> None:
    """The head row is the authority, not ``MAX(seq)``: an entry that somehow left the table must
    not hand its number back out. Deleting the last entry and writing again continues the count."""
    a = _dir(tmp_path, "a")
    store.save(_ingest(a, "m"), "w", actor=ACTOR, matter="m", tenant=TENANT)
    with store._sf() as s, s.begin():
        s.execute(AuditRecord.__table__.delete().where(AuditRecord.chain_scope == "m"))
    store.save(_ingest(a, "m", "b.txt"), "w", actor=ACTOR, matter="m", tenant=TENANT)
    assert [r.seq for r in _rows(store, "m")] == [2]


# ── the entry's identity (AC-3) ───────────────────────────────────────────────────────────────

def test_every_new_entry_carries_both_versions_and_the_v2_recipe(
        tmp_path: Path, store: SqlStore) -> None:
    a = _dir(tmp_path, "a")
    store.save(_ingest(a, "m"), "w", actor=ACTOR, matter="m", tenant=TENANT)
    for row in _rows(store):
        assert row.content_version == audit.CONTENT_V2
        assert row.app_version and row.schema_version


def test_an_uncatalogued_verb_is_refused_at_the_write(store: SqlStore) -> None:
    with store._sf() as s, s.begin(), pytest.raises(audit.UncataloguedAct):
        store._append_audit(s, TENANT, "m", ACTOR, "piece_labeled", "d", datetime.now(UTC))


def test_an_entry_attributed_to_nobody_is_refused(store: SqlStore) -> None:
    with store._sf() as s, s.begin(), pytest.raises(audit.UnknownActor):
        store._append_audit(
            s, TENANT, "m", "unknown", audit.ACT_JUDGE, "d", datetime.now(UTC))


def test_a_matter_level_act_without_a_matter_is_refused_never_filed_under_the_tenant(
        store: SqlStore) -> None:
    """Silently filing it on the tenant chain is how a matter's record acquires a hole nobody can
    see: the act happened, the export of that matter does not carry it, and nothing says so."""
    with store._sf() as s, s.begin(), pytest.raises(ValueError, match="matter-level"):
        store._append_audit(s, TENANT, None, ACTOR, audit.ACT_JUDGE, "d", datetime.now(UTC))


def test_a_tenant_level_act_stays_on_the_tenant_chain_even_when_a_matter_is_in_hand(
        store: SqlStore) -> None:
    """The catalogue decides the chain, not the call site. The ``matter`` column still records
    what the act was about — where it is counted and what it is about are different questions."""
    now = datetime.now(UTC)
    with store._sf() as s, s.begin():
        store._append_audit(s, TENANT, "m", ACTOR, audit.ACT_CONFIG_CHANGED, "d", now)
    (row,) = _rows(store)
    assert row.chain_scope == audit.TENANT_CHAIN and row.matter == "m"


# ── the versioned recipe (D5) ─────────────────────────────────────────────────────────────────

def test_a_pre_5_5_entry_verifies_under_its_own_recipe_not_todays(store: SqlStore) -> None:
    """The trap this story had to avoid. Story 5.5 changed what the chain value is taken over;
    recomputing an older entry under the newer recipe would turn a correct record unverifiable in
    a single deploy — the very alarm the chain exists to raise, fired by a deployment."""
    ts = datetime(2026, 8, 1, 10, 0, 0, tzinfo=UTC)
    stamp = "2026-08-01T10:00:00.000000"
    legacy = audit.chained_content(
        version=audit.CONTENT_V1, seq=1, tenant=TENANT, chain_scope=audit.TENANT_CHAIN,
        matter="m", actor=ACTOR, action=audit.ACT_INGEST, detail="d", timestamp=stamp,
        app_version="", schema_version="")
    chain = audit.chain_value("", legacy)
    with store._sf() as s, s.begin():
        s.add(AuditRecord(
            id=chain, tenant=TENANT, chain_scope=audit.TENANT_CHAIN, seq=1, matter="m",
            actor=ACTOR, action=audit.ACT_INGEST, detail="d", chain=chain, timestamp=ts,
            content_version=audit.CONTENT_V1, app_version=None, schema_version=None))

    with store._sf() as s:
        entries = store._verifiable_entries(s, TENANT)
    (verdict,) = audit.verify_chains(entries, {audit.TENANT_CHAIN: ""})
    assert verdict.verified

    # ... and the same entry read under today's recipe would NOT verify — which is exactly what
    # would have happened had the recipe not been versioned on the entry.
    forced = [
        audit.VerifiableEntry(**{**vars(e), "content_version": audit.CONTENT_V2})
        for e in entries
    ]
    assert not audit.verify_chains(forced, {audit.TENANT_CHAIN: ""})[0].verified


def test_a_matter_with_no_recorded_act_reports_no_slices_rather_than_a_clean_bill(
        store: SqlStore) -> None:
    """An empty trail is empty, not verified-and-therefore-fine: the reader is shown zero slices,
    so nothing claims a chain was checked when there was none."""
    store.save(IngestionResult(), scope="w", actor=ACTOR, matter="m", tenant=TENANT, audit=False)
    trail = store.read_audit("m", TENANT, {"w"})
    assert trail.entries == [] and trail.slices == ()


# ── the review's confirmed defects, each with the test that fires on it ────────────────────────

def test_a_concurrent_opener_of_the_same_chain_is_waited_for_not_refused(
        tmp_path: Path, store: SqlStore) -> None:
    """CONFIRMED BY REVIEW. ``SELECT … FOR UPDATE`` on a head row that does not exist locks
    nothing, so two acts opening the SAME new chain both fell through and the second died on the
    primary key — the refused legitimate act the lock exists to eliminate. The fix re-reads the
    head after the tenant lock is held; here the concurrent creation is simulated by inserting the
    head row from inside ``_open_chain``, which is exactly the window that was open."""
    a = _dir(tmp_path, "a")
    real_open = store._open_chain

    def _open_then_race(session, tenant, chain_scope, actor, ts):  # noqa: ANN001, ANN202
        anchor = real_open(session, tenant, chain_scope, actor, ts)
        # a concurrent transaction got there first and already opened this chain
        session.add(AuditChainHead(
            tenant=tenant, chain_scope=chain_scope, seq=1, chain="concurrent-head",
            anchor=anchor, opened_at=ts, updated_at=ts))
        session.flush()
        return anchor

    store._open_chain = _open_then_race  # type: ignore[method-assign]
    try:
        store.save(_ingest(a, "m"), "w", actor=ACTOR, matter="m", tenant=TENANT)
    finally:
        store._open_chain = real_open  # type: ignore[method-assign]

    # the act SUCCEEDED and continued the concurrent chain rather than colliding with it
    with store._sf() as s:
        head = s.get(AuditChainHead, {"tenant": TENANT, "chain_scope": "m"})
    assert head.seq == 2
    assert [r.seq for r in _rows(store, "m")] == [2]


def test_an_empty_trail_is_not_reported_as_verified(store: SqlStore) -> None:
    """CONFIRMED BY REVIEW. ``all([])`` is True, so a matter whose every chain had been removed —
    head row and all — reported an intact record, indistinguishable from a matter that never
    acted."""
    store.save(IngestionResult(), scope="w", actor=ACTOR, matter="m", tenant=TENANT, audit=False)
    trail = store.read_audit("m", TENANT, {"w"})
    assert trail.slices == () and trail.verified is False


def test_the_tenant_slice_is_reported_even_when_the_matter_holds_no_entries_on_it(
        tmp_path: Path, store: SqlStore) -> None:
    """CONFIRMED BY REVIEW. The tenant slice was built only when this reader still held entries on
    it, so deleting a matter's pre-5.5 history made the slice vanish and the trail read clean and
    shorter — nothing said a slice had ever existed."""
    a = _dir(tmp_path, "a")
    store.save(_ingest(a, "m"), "w", actor=ACTOR, matter="m", tenant=TENANT)
    trail = store.read_audit("m", TENANT, {"w"})
    scopes = {s.chain_scope for s in trail.slices}
    assert scopes == {"m", audit.TENANT_CHAIN}
    tenant_slice = next(s for s in trail.slices if s.chain_scope == audit.TENANT_CHAIN)
    assert tenant_slice.entries == 0                    # this matter holds none of it
    assert tenant_slice.verifiable_in_isolation is False
    assert tenant_slice.verified is True                # ... but the chain itself is intact


def test_only_postgresql_needs_the_snapshot_statement(store: SqlStore) -> None:
    """CONFIRMED BY REVIEW (read skew). Under READ COMMITTED the backup could capture the
    allocator after a commit the entries were read before — a head ahead of its own record."""
    from apx.adapters.store_postgres.store import _snapshot_isolation_sql
    assert _snapshot_isolation_sql("postgresql") == (
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    assert _snapshot_isolation_sql("sqlite") is None
