"""The *failure register* override — FR-5's other exit (Story 5.6; FR-25, AD-37, AD-22, AD-7).

Against the real SQLite store. An entry leaves ``open`` because a person decided it should and said
why in one line: the reason is mandatory and a blank one writes **nothing at all**; the commit is
conditional on an observed ``open``, so an entry that moved is refused rather than re-closed; the
state change, the append-only ledger row and the audit entry commit together; the reason is in the
record verbatim and encrypted at rest; the act is scope-checked and admin-only for an undetermined
*matter*; and a later retry never silently resolves what the override closed.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import AuditRecord, Base, Failure, RegisterOverride
from apx.adapters.store_postgres.store import ScopeDenied, SqlStore
from apx.core.app.ingest import IngestedFailure, IngestedPiece, IngestionResult
from apx.core.app.register_override import override_register_entry
from apx.core.domain import audit as AUDIT
from apx.core.domain.dedup import text_key
from apx.core.domain.failures import ErrorClass
from apx.core.domain.identity import content_hash, piece_id
from apx.core.domain.override import MissingOverrideReason, reason_from_detail

TENANT, WALL = "t", "wall"
REASON = "source détruite chez le client, jamais rendue lisible — écartée en connaissance de cause"


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def _fail(path: str, *, cls: ErrorClass = ErrorClass.EXTRACTION_ERROR,
          matter: str = "m") -> IngestedFailure:
    return IngestedFailure(
        filename=path.rsplit("/", 1)[-1], submitted_path=path, matter=matter, tenant=TENANT,
        error_class=cls, detail="x", custodian="Dupont")


def _piece(content: str, *, prov: str, matter: str = "m") -> IngestedPiece:
    ch = content_hash(content.encode())
    return IngestedPiece(
        id=piece_id(TENANT, ch, matter), matter=matter, tenant=TENANT, content_hash=ch,
        text_key=text_key(content), provenance_path=prov, custodian="Dupont",
        extraction_method="text", extractor_version="v", schema_version="s",
        ingestion_timestamp=datetime.now(UTC), full_text=content, text_version="v")


def _seed_one(
    store: SqlStore, *, matter: str = "m", scope: str = WALL, path: str = "/a.pdf",
) -> str:
    store.save(IngestionResult(failures=[_fail(path, matter=matter)]),
               actor="Me Dupont", scope=scope, matter=matter, tenant=TENANT)
    return store.register(matter, TENANT, {scope})[0].id


def _counts(store: SqlStore) -> tuple[int, int]:
    """(audit entries, override ledger rows) — what "nothing was written" is measured against."""
    with store._sf() as s:
        audits = s.scalar(select(func.count()).select_from(AuditRecord)) or 0
        rows = s.scalar(select(func.count()).select_from(RegisterOverride)) or 0
    return audits, rows


# ── AC-4: the transition, and what commits with it ────────────────────────────────────────────
def test_the_entry_leaves_open_and_stays_in_the_register(store: SqlStore) -> None:
    entry_id = _seed_one(store)
    state = store.override_register_entry(
        entry_id=entry_id, tenant=TENANT, actor="Me Dupont", reason=REASON, scopes={WALL})
    assert state == "overridden"
    reg = store.register("m", TENANT, {WALL})
    assert len(reg) == 1                                    # KEPT — nothing is removed (AD-7)
    assert reg[0].resolution_state == "overridden"
    assert not reg[0].retryable                             # no longer offered for retry


def test_the_denominator_names_the_override_instead_of_shrinking(store: SqlStore) -> None:
    # SM-3's identity has THREE terms since this story. An override drops the open count and adds
    # nothing to the corpus, so without the third term the identity would break and
    # `require_consistent` would raise on the matter's next retry — and "fixing" it by shrinking
    # `submitted_pieces` would have made an override a way to shrink the *denominator*, which is
    # the single thing AD-38 exists to prevent.
    entry_id = _seed_one(store)
    before = store.inventory("m", TENANT, {WALL})
    store.override_register_entry(
        entry_id=entry_id, tenant=TENANT, actor="Me Dupont", reason=REASON, scopes={WALL})
    after = store.inventory("m", TENANT, {WALL})
    assert after.open_register_entries == before.open_register_entries - 1
    assert after.overridden_register_entries == before.overridden_register_entries + 1
    assert after.in_corpus == before.in_corpus              # the document is still not indexed
    assert after.submitted_pieces == before.submitted_pieces  # the denominator is PERMANENT
    after.require_consistent()                              # SM-3 still holds — no raise


def test_a_piece_submitted_after_an_override_still_raises_the_watermark(store: SqlStore) -> None:
    # the other half of the same defect: the submission watermark is a max over the known
    # population, so a sum missing the overridden entries is short by exactly that many — and a
    # genuinely new pièce arriving after an override would not raise it at all, leaving the next
    # consistency check to report the NEW pièce as lost. Invisible until a matter has both.
    entry_id = _seed_one(store, path="/a.pdf")
    store.override_register_entry(
        entry_id=entry_id, tenant=TENANT, actor="Me Dupont", reason=REASON, scopes={WALL})
    before = store.inventory("m", TENANT, {WALL})
    store.save(IngestionResult(failures=[_fail("/b.pdf")]),
               actor="Me Dupont", scope=WALL, matter="m", tenant=TENANT)
    after = store.inventory("m", TENANT, {WALL})
    assert after.submitted_pieces == before.submitted_pieces + 1
    after.require_consistent()


def test_a_retry_after_an_override_does_not_trip_the_inventory_guarantee(store: SqlStore) -> None:
    # the concrete failure the third term prevents: `retry_failure` asserts the SM-3 identity at
    # the end of every retry, so a two-entry matter with one overridden entry would have raised on
    # the next retry of the other one — long after the override, and nowhere near it
    first = _seed_one(store, path="/a.pdf")
    store.save(IngestionResult(failures=[_fail("/b.pdf")]),
               actor="Me Dupont", scope=WALL, matter="m", tenant=TENANT)
    second = next(e.id for e in store.register("m", TENANT, {WALL})
                  if e.submitted_path == "/b.pdf")
    store.override_register_entry(
        entry_id=first, tenant=TENANT, actor="Me Dupont", reason=REASON, scopes={WALL})
    out = store.retry_failure(
        second, lambda: IngestionResult(pieces=[_piece("recovered", prov="/b.pdf")]),
        TENANT, {WALL}, actor="avocat")
    assert out.outcome == "resolved"
    store.inventory("m", TENANT, {WALL}).require_consistent()


def test_the_reason_the_ledger_row_and_the_audit_entry_commit_together(store: SqlStore) -> None:
    entry_id = _seed_one(store)
    store.override_register_entry(
        entry_id=entry_id, tenant=TENANT, actor="Me Dupont", reason=REASON, scopes={WALL})
    with store._sf() as s:
        row = s.scalars(select(RegisterOverride)).one()
        entry = s.scalars(
            select(AuditRecord).where(AuditRecord.action == AUDIT.ACT_REGISTER_OVERRIDE)).one()
    assert row.entry_id == entry_id and row.actor == "Me Dupont" and row.reason == REASON
    assert reason_from_detail(entry.detail) == REASON       # verbatim, in the record (FR-25)
    assert entry.actor == "Me Dupont" and entry.timestamp is not None


def test_the_reason_and_the_actor_are_encrypted_at_rest(store: SqlStore) -> None:
    entry_id = _seed_one(store)
    store.override_register_entry(
        entry_id=entry_id, tenant=TENANT, actor="Me Dupont", reason=REASON, scopes={WALL})
    with store._sf() as s:
        raw = s.execute(text("SELECT actor, reason FROM register_override")).one()
    assert REASON not in raw[1] and "Me Dupont" not in raw[0]   # AD-31: ciphertext on disk


def test_the_override_is_counted_on_the_tenant_chain(store: SqlStore) -> None:
    # D1: a register entry's matter may be undetermined, so filing the ones that have a matter on
    # the matter chain and the ones that do not on the tenant chain would put one verb in two
    # places by a rule no reader of the export could see (the bulk-retry precedent).
    entry_id = _seed_one(store)
    store.override_register_entry(
        entry_id=entry_id, tenant=TENANT, actor="Me Dupont", reason=REASON, scopes={WALL})
    with store._sf() as s:
        entry = s.scalars(
            select(AuditRecord).where(AuditRecord.action == AUDIT.ACT_REGISTER_OVERRIDE)).one()
    assert entry.chain_scope == AUDIT.TENANT_CHAIN
    assert entry.matter == "m"                              # what the act was ABOUT, still recorded


# ── AC-6: the failure path — refused, and nothing written ─────────────────────────────────────
@pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
def test_a_blank_reason_is_refused_and_writes_nothing(store: SqlStore, blank: str) -> None:
    entry_id = _seed_one(store)
    before = _counts(store)
    with pytest.raises(MissingOverrideReason):
        store.override_register_entry(
            entry_id=entry_id, tenant=TENANT, actor="Me Dupont", reason=blank, scopes={WALL})
    assert _counts(store) == before                          # no audit entry, no ledger row
    assert store.register("m", TENANT, {WALL})[0].resolution_state == "open"


def test_a_blank_reason_is_refused_through_the_use_case_seam_too(store: SqlStore) -> None:
    entry_id = _seed_one(store)
    with pytest.raises(MissingOverrideReason):
        override_register_entry(
            store, entry_id=entry_id, tenant=TENANT, actor="Me Dupont", reason="  ",
            scopes={WALL})
    assert store.register("m", TENANT, {WALL})[0].resolution_state == "open"


# ── AC-4: the conditional commit (AD-37) ──────────────────────────────────────────────────────
def test_an_already_resolved_entry_is_refused_never_re_closed(store: SqlStore) -> None:
    entry_id = _seed_one(store)
    store.retry_failure(
        entry_id, lambda: IngestionResult(pieces=[_piece("recovered", prov="/a.pdf")]),
        TENANT, {WALL}, actor="avocat")
    before = _counts(store)
    with pytest.raises(ValueError, match="not open"):
        store.override_register_entry(
            entry_id=entry_id, tenant=TENANT, actor="Me Dupont", reason=REASON, scopes={WALL})
    assert _counts(store) == before
    assert store.register("m", TENANT, {WALL})[0].resolution_state == "resolved"


def test_overriding_twice_is_refused_rather_than_silently_repeated(store: SqlStore) -> None:
    entry_id = _seed_one(store)
    store.override_register_entry(
        entry_id=entry_id, tenant=TENANT, actor="Me Dupont", reason=REASON, scopes={WALL})
    with pytest.raises(ValueError, match="not open"):
        store.override_register_entry(
            entry_id=entry_id, tenant=TENANT, actor="Me Martin", reason="je ne suis pas d'accord",
            scopes={WALL})
    with store._sf() as s:
        assert s.scalar(select(func.count()).select_from(RegisterOverride)) == 1


def test_a_retry_never_silently_resolves_what_an_override_closed(store: SqlStore) -> None:
    # AD-37's other direction, and the half this story can assert today: the document becoming
    # readable later does NOT undo a decision a named person took and argued for. Reversing an
    # override is a NEW act (Story 5.7's reversible drawer), never an erasure of this one.
    entry_id = _seed_one(store)
    store.override_register_entry(
        entry_id=entry_id, tenant=TENANT, actor="Me Dupont", reason=REASON, scopes={WALL})
    out = store.retry_failure(
        entry_id, lambda: IngestionResult(pieces=[_piece("readable now", prov="/a.pdf")]),
        TENANT, {WALL}, actor="avocat")
    assert out.outcome == "precondition-not-met" and out.resolution_state == "overridden"
    assert store.register("m", TENANT, {WALL})[0].resolution_state == "overridden"


def test_a_bulk_retry_skips_an_overridden_entry(store: SqlStore) -> None:
    entry_id = _seed_one(store)
    store.override_register_entry(
        entry_id=entry_id, tenant=TENANT, actor="Me Dupont", reason=REASON, scopes={WALL})
    outcome = store.bulk_retry(
        TENANT, {WALL},
        reingest_for=lambda e: (lambda: IngestionResult(pieces=[_piece("x", prov="/a.pdf")])),
        actor="avocat")
    assert outcome.resolved == 0                             # not a candidate: it is not open
    assert store.register("m", TENANT, {WALL})[0].resolution_state == "overridden"


def test_an_absent_entry_answers_exactly_like_a_walled_one(store: SqlStore) -> None:
    # non-disclosing: a caller must not be able to learn, one id at a time, which entries exist
    # behind a wall it does not hold. Absent and denied are the SAME refusal.
    walled = _seed_one(store, matter="m-b", scope="wall-b")
    with pytest.raises(ScopeDenied):
        store.override_register_entry(
            entry_id="nope", tenant=TENANT, actor="Me Dupont", reason=REASON, scopes={WALL})
    with pytest.raises(ScopeDenied):
        store.override_register_entry(
            entry_id=walled, tenant=TENANT, actor="Me Dupont", reason=REASON, scopes={WALL})


# ── AC-4: authorisation (FR-49 / AD-12) ───────────────────────────────────────────────────────
def test_the_wrong_wall_is_refused_without_disclosing(store: SqlStore) -> None:
    entry_id = _seed_one(store)
    with pytest.raises(ScopeDenied):
        store.override_register_entry(
            entry_id=entry_id, tenant=TENANT, actor="Me Martin", reason=REASON,
            scopes={"other-wall"})
    assert store.register("m", TENANT, {WALL})[0].resolution_state == "open"


def test_another_tenant_is_refused(store: SqlStore) -> None:
    entry_id = _seed_one(store)
    with pytest.raises(ScopeDenied):
        store.override_register_entry(
            entry_id=entry_id, tenant="other-tenant", actor="Me Martin", reason=REASON,
            scopes={WALL})


def test_an_undetermined_matter_entry_is_admin_only(store: SqlStore) -> None:
    with store._sf() as s, s.begin():
        s.add(Failure(
            id="undet-1", tenant=TENANT, matter=None, filename="mystery.bin",
            submitted_path="/mystery.bin", error_class="unknown", cardinality="one",
            resolution_state="open", timestamp=datetime.now(UTC)))
    with pytest.raises(ScopeDenied):
        store.override_register_entry(
            entry_id="undet-1", tenant=TENANT, actor="avocat", reason=REASON, scopes={WALL})
    state = store.override_register_entry(
        entry_id="undet-1", tenant=TENANT, actor="admin", reason=REASON, scopes=set(),
        is_admin=True)
    assert state == "overridden"
    with store._sf() as s:
        entry = s.scalars(
            select(AuditRecord).where(AuditRecord.action == AUDIT.ACT_REGISTER_OVERRIDE)).one()
    assert entry.matter is None and entry.chain_scope == AUDIT.TENANT_CHAIN
