"""The failure register (Story 2.6; FR-5, AD-37, AD-7, AD-38, FR-49).

Against the real SQLite store: an entry carries the full field set; a retry is a conditional
commit that resolves-on-success while KEEPING history and dropping the open count, refreshes on
still-failing, and never clobbers an entry that moved; a password-protected entry is retryable (not
override-only); a bulk retry writes ONE audit entry over the filtered set; the export is
scope-filtered and an undetermined-matter entry is visible only to the tenant admin.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import AuditRecord, Base, Failure
from apx.adapters.store_postgres.store import ScopeDenied, SqlStore
from apx.core.app.ingest import IngestedFailure, IngestedPiece, IngestionResult
from apx.core.domain.dedup import text_key
from apx.core.domain.failures import ErrorClass
from apx.core.domain.identity import content_hash, piece_id

TENANT, WALL = "t", "wall"


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def _fail(path: str, *, cls: ErrorClass = ErrorClass.EXTRACTION_ERROR, custodian: str = "Dupont",
          matter: str = "m") -> IngestedFailure:
    return IngestedFailure(
        filename=path.rsplit("/", 1)[-1], submitted_path=path, matter=matter, tenant=TENANT,
        error_class=cls, detail="x", custodian=custodian)


def _piece(content: str, *, prov: str, matter: str = "m") -> IngestedPiece:
    ch = content_hash(content.encode())
    return IngestedPiece(
        id=piece_id(TENANT, ch, matter), matter=matter, tenant=TENANT, content_hash=ch,
        text_key=text_key(content), provenance_path=prov, custodian="Dupont",
        extraction_method="text", extractor_version="v", schema_version="s",
        ingestion_timestamp=datetime.now(UTC), full_text=content, text_version="v")


def _seed(
    store: SqlStore, *failures: IngestedFailure, matter: str = "m", scope: str = WALL
) -> None:
    store.save(IngestionResult(failures=list(failures)), scope=scope, matter=matter, tenant=TENANT)


# ── AC1: the full field set, cardinality, scope-checked ───────────────────────────────────────
def test_register_entry_carries_the_full_field_set_scope_checked(store: SqlStore) -> None:
    _seed(store, _fail("/dossier/a.pdf", cls=ErrorClass.PASSWORD_PROTECTED, custodian="Me Martin"))
    entries = store.register("m", TENANT, {WALL})
    assert len(entries) == 1
    e = entries[0]
    assert e.filename == "a.pdf" and e.submitted_path == "/dossier/a.pdf"
    assert e.matter == "m" and e.custodian == "Me Martin"          # custodian decrypted
    assert e.error_class == "password-protected" and e.cardinality == "one"
    assert e.resolution_state == "open" and e.retryable and e.timestamp
    with pytest.raises(ScopeDenied):
        store.register("m", TENANT, {"other-wall"})                # fail closed on the wrong wall


def test_a_container_entry_has_cardinality_unknown(store: SqlStore) -> None:
    _seed(store, _fail("/big.zip", cls=ErrorClass.CONTAINER_UNOPENABLE))
    assert store.register("m", TENANT, {WALL})[0].cardinality == "unknown"  # AD-38


# ── AC2: retry is a conditional commit — resolve keeps history, drops the open count ───────────
def test_retry_resolves_on_success_keeps_history_and_drops_the_open_count(store: SqlStore) -> None:
    _seed(store, _fail("/a.pdf"))
    entry_id = store.register("m", TENANT, {WALL})[0].id
    before = store.inventory("m", TENANT, {WALL}).failures

    out = store.retry_failure(
        entry_id, lambda: IngestionResult(pieces=[_piece("recovered", prov="/a.pdf")]),
        TENANT, {WALL}, actor="avocat")

    assert out.outcome == "resolved"
    reg = store.register("m", TENANT, {WALL})
    assert len(reg) == 1 and reg[0].resolution_state == "resolved"   # KEPT — never removed (AD-7)
    inv = store.inventory("m", TENANT, {WALL})
    assert inv.failures == before - 1 and inv.in_corpus == 1         # open-only; pièce recovered


def test_retry_that_still_fails_keeps_open_and_refreshes_the_class(store: SqlStore) -> None:
    _seed(store, _fail("/a.pdf", cls=ErrorClass.EXTRACTION_ERROR))
    entry_id = store.register("m", TENANT, {WALL})[0].id
    out = store.retry_failure(
        entry_id,
        lambda: IngestionResult(failures=[_fail("/a.pdf", cls=ErrorClass.PASSWORD_PROTECTED)]),
        TENANT, {WALL}, actor="avocat")
    assert out.outcome == "still-failing"
    e = store.register("m", TENANT, {WALL})[0]
    assert e.resolution_state == "open" and e.error_class == "password-protected"  # class refreshed


def test_retry_is_a_conditional_commit_and_never_clobbers_a_moved_entry(store: SqlStore) -> None:
    # AD-37: a retry against a non-open entry does NOT silently resolve it (the override race).
    _seed(store, _fail("/a.pdf"))
    entry_id = store.register("m", TENANT, {WALL})[0].id
    ok = lambda: IngestionResult(pieces=[_piece("ok", prov="/a.pdf")])  # noqa: E731
    store.retry_failure(entry_id, ok, TENANT, {WALL}, actor="a")  # first retry resolves it
    # a second retry observes it is no longer open → precondition-not-met, writes nothing new
    out = store.retry_failure(entry_id, ok, TENANT, {WALL}, actor="a")
    assert out.outcome == "precondition-not-met" and out.resolution_state == "resolved"


def test_retry_phase3_reobserves_a_change_that_lands_during_reingest(store: SqlStore) -> None:
    # AD-37: a state change that lands DURING the slow phase-2 re-ingest (not before it) must be
    # caught by the phase-3 re-observe, not the redundant phase-1 early-out. The reingest thunk
    # models a concurrent actor resolving the entry mid-flight; the outer retry must NOT clobber it.
    _seed(store, _fail("/a.pdf"))
    entry_id = store.register("m", TENANT, {WALL})[0].id

    def _reingest_while_another_actor_resolves_it() -> IngestionResult:
        store.retry_failure(  # a concurrent resolve lands during phase 2 (which holds no tx)
            entry_id, lambda: IngestionResult(pieces=[_piece("first", prov="/a.pdf")]),
            TENANT, {WALL}, actor="other")
        return IngestionResult(pieces=[_piece("second", prov="/a.pdf")])

    out = store.retry_failure(
        entry_id, _reingest_while_another_actor_resolves_it, TENANT, {WALL}, actor="me")
    assert out.outcome == "precondition-not-met"        # phase-3 caught the mid-flight resolve


def test_two_tenants_same_matter_and_path_do_not_clobber(store: SqlStore) -> None:
    # AD-12: a register id is tenant-qualified, so tenant t1's entry survives tenant t2's ingest of
    # the SAME matter-name + path — the Chinese wall, never a cross-tenant overwrite (AD-7).
    for ten, cust in (("t1", "Alice"), ("t2", "Bob")):
        store.save(IngestionResult(failures=[IngestedFailure(
            filename="a.pdf", submitted_path="/a.pdf", matter="m", tenant=ten,
            error_class=ErrorClass.EXTRACTION_ERROR, detail="x", custodian=cust)]),
            scope="wall", matter="m", tenant=ten)
    with store._sf() as s:
        assert s.scalar(select(func.count()).select_from(Failure)) == 2   # two rows, not one
    assert store.register("m", "t1", {"wall"})[0].custodian == "Alice"    # t1's survives intact
    assert store.register("m", "t2", {"wall"})[0].custodian == "Bob"


def test_retry_records_a_co_present_member_failure_and_resolves_only_on_own_path(
    store: SqlStore,
) -> None:
    # AD-37/FR-5: a container retry that opens yields member pièces AND member failures; the member
    # failure must be RECORDED (never dropped), and the container entry resolves because its own
    # path succeeded (no fresh failure for it).
    _seed(store, _fail("/box.zip", cls=ErrorClass.CONTAINER_UNOPENABLE))
    entry_id = store.register("m", TENANT, {WALL})[0].id
    out = store.retry_failure(
        entry_id,
        lambda: IngestionResult(
            pieces=[_piece("member-a", prov="/box.zip/a.txt")],
            failures=[_fail("/box.zip/b.exe", cls=ErrorClass.UNSUPPORTED_FORMAT)]),
        TENANT, {WALL}, actor="avocat")
    assert out.outcome == "resolved"                                       # the container opened
    reg = {e.submitted_path: e for e in store.register("m", TENANT, {WALL})}
    assert reg["/box.zip"].resolution_state == "resolved"
    assert reg["/box.zip/b.exe"].error_class == "unsupported-format"       # member failure recorded


# ── AC3: a password-protected entry is retryable (a credential-supply action), not override-only ─
def test_password_protected_is_retryable_never_override_only(store: SqlStore) -> None:
    _seed(store, _fail("/locked.pdf", cls=ErrorClass.PASSWORD_PROTECTED))
    entry_id = store.register("m", TENANT, {WALL})[0].id
    # A password-protected entry has a non-override EXIT: a retry. The app builds the `reingest`
    # thunk (it is where a supplied credential would be threaded to the re-run); here the thunk
    # returns a recovered pièce, standing for "the credential opened it". The register contract is
    # that this path resolves it — it is never resolvable ONLY by an override (the FR-5 defect).
    out = store.retry_failure(
        entry_id, lambda: IngestionResult(pieces=[_piece("clair", prov="/locked.pdf")]),
        TENANT, {WALL}, actor="avocat")
    assert out.outcome == "resolved"   # resolvable by retry, not by override only


# ── AC4: bulk retry over a filtered set → ONE audit entry ─────────────────────────────────────
def test_bulk_retry_writes_exactly_one_audit_entry_over_the_set(store: SqlStore) -> None:
    _seed(store, _fail("/a.pdf"), _fail("/b.pdf"), _fail("/c.pdf"),
          _fail("/keep.zip", cls=ErrorClass.CONTAINER_UNOPENABLE))
    # retry only the extraction-error entries; each reingest succeeds
    def _reingest(e):  # noqa: ANN001, ANN202 — a per-entry thunk that "recovers" the pièce
        return lambda: IngestionResult(pieces=[_piece("ok", prov=e.submitted_path)])

    out = store.bulk_retry(
        TENANT, {WALL}, error_class="extraction-error", actor="avocat", reingest_for=_reingest)
    assert out.attempted == 3 and out.resolved == 3 and out.skipped == 0
    with store._sf() as s:
        n = s.scalar(select(func.count()).select_from(AuditRecord).where(
            AuditRecord.tenant == TENANT, AuditRecord.action == "bulk-retry"))
    assert n == 1                                     # ONE audit entry for the set, not per pièce
    # the container entry (filtered out) is untouched — still open
    assert any(e.error_class == "container-unopenable" and e.resolution_state == "open"
               for e in store.register("m", TENANT, {WALL}))


# ── AC5: export is scope-filtered; an undetermined-matter entry is admin-only ─────────────────
def test_export_is_scope_filtered_and_records_one_audit_entry(store: SqlStore) -> None:
    _seed(store, _fail("/a.pdf", matter="m-a"), matter="m-a", scope="wall-a")
    _seed(store, _fail("/b.pdf", matter="m-b"), matter="m-b", scope="wall-b")
    exp = store.export_register(TENANT, {"wall-a"}, actor="avocat", is_admin=False)
    assert {e.submitted_path for e in exp.lines} == {"/a.pdf"}      # only the held wall
    with store._sf() as s:
        n = s.scalar(select(func.count()).select_from(AuditRecord).where(
            AuditRecord.action == "export-register"))
    assert n == 1


def test_an_undetermined_matter_entry_is_visible_only_to_the_admin(store: SqlStore) -> None:
    _seed(store, _fail("/known.pdf"), matter="m", scope=WALL)
    # an entry that could not be attributed to a matter (matter IS NULL) — inserted directly
    with store._sf() as s, s.begin():
        s.add(Failure(
            id="undet-1", tenant=TENANT, matter=None, filename="mystery.bin",
            submitted_path="/mystery.bin", error_class="unknown", cardinality="one",
            resolution_state="open", timestamp=datetime.now(UTC)))
    scoped = store.register_all(TENANT, {WALL}, is_admin=False)
    admin = store.register_all(TENANT, {WALL}, is_admin=True)
    assert all(e.matter is not None for e in scoped)               # non-admin never sees it
    assert any(e.matter is None and e.filename == "mystery.bin" for e in admin)  # admin does
