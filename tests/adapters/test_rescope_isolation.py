"""Grant-time authorisation & scope administration (story 1.6). The mutating adversarial
suite (AC4): re-scoping a matter MOVES the wall — it holds in its NEW position immediately
(the next query) and its OLD position NEVER after the move. Plus: every mutation is audited
with actor/subject/scope/authority (AC1), a re-scope is reversible and rejects a no-op (AC3),
and holding the administrative grant does not widen a data read (AC2 — no implicit superuser).
Scope resolves live (AD-13), so a single matter_scope UPDATE is the whole operation.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import AuditRecord, Base
from apx.adapters.store_postgres.store import ScopeDenied, SqlStore
from apx.core.app.ingest import IngestedPiece, IngestionResult

TENANT, MATTER, OLD, NEW = "cabinet", "m", "wall-old", "wall-new"


def _piece(pid: str) -> IngestedPiece:
    return IngestedPiece(
        id=pid, matter=MATTER, tenant=TENANT, content_hash=pid, text_key=pid,
        provenance_path=f"/{pid}.txt", custodian="c", extraction_method="text",
        extractor_version="v", schema_version="s", ingestion_timestamp=datetime.now(UTC),
        full_text="le contrat", text_version="v",
    )


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    s = SqlStore(sessionmaker(bind=engine, future=True))
    s.save(IngestionResult(pieces=[_piece("a"), _piece("b")]), scope=OLD, actor="admin")
    return s


def test_rescope_moves_the_wall_immediately_and_never_backwards(store: SqlStore) -> None:
    # before: the wall holds in its OLD position — old sees, a new-holder is denied
    assert store.inventory(MATTER, TENANT, {OLD}).in_corpus == 2
    assert [m.matter for m in store.matters(TENANT, {NEW})] == []
    with pytest.raises(ScopeDenied):
        store.inventory(MATTER, TENANT, {NEW})

    store.rescope_matter(TENANT, "admin", MATTER, NEW)  # one audited op, no corpus touched

    # after, on the NEXT query (nothing propagated): the wall has MOVED
    assert store.inventory(MATTER, TENANT, {NEW}).in_corpus == 2       # new sees, immediately
    assert [m.matter for m in store.matters(TENANT, {NEW})] == [MATTER]
    with pytest.raises(ScopeDenied):
        store.inventory(MATTER, TENANT, {OLD})                          # old never holds after
    assert [m.matter for m in store.matters(TENANT, {OLD})] == []


def test_rescope_rejects_a_no_op_and_an_unknown_matter(store: SqlStore) -> None:
    with pytest.raises(ValueError, match="already in that scope"):
        store.rescope_matter(TENANT, "admin", MATTER, OLD)  # same scope — never a silent write
    with pytest.raises(ValueError, match="unknown matter"):
        store.rescope_matter(TENANT, "admin", "ghost", NEW)


def test_rescope_is_reversible(store: SqlStore) -> None:
    store.rescope_matter(TENANT, "admin", MATTER, NEW)
    store.rescope_matter(TENANT, "admin", MATTER, OLD)  # move it back
    assert store.inventory(MATTER, TENANT, {OLD}).in_corpus == 2
    with pytest.raises(ScopeDenied):
        store.inventory(MATTER, TENANT, {NEW})


def _audit(store: SqlStore) -> list[AuditRecord]:
    with store._sf() as s:
        return list(s.execute(
            select(AuditRecord).where(AuditRecord.tenant == TENANT).order_by(AuditRecord.seq)
        ).scalars().all())


def test_scope_mutations_are_audited_with_actor_subject_scope(store: SqlStore) -> None:
    uid = store.create_user(TENANT, "a@a.test", "password1", "Avocat A", set())
    store.grant_scope(TENANT, "boss", uid, OLD)
    store.revoke_scope(TENANT, "boss", uid, OLD)
    store.rescope_matter(TENANT, "boss", MATTER, NEW)
    store.set_user_admin(TENANT, "boss", uid, True)
    by_action = {r.action: r for r in _audit(store)}
    # each privileged act is on the record, on the authority of "boss", naming its subject
    for action in ("grant_scope", "revoke_scope", "rescope_matter", "grant_admin"):
        assert action in by_action, f"{action} was not audited"
        assert by_action[action].actor == "boss"        # on the authority of the admin
        assert "subject=" in by_action[action].detail   # naming its subject
    assert f"scope={OLD}->{NEW}" in by_action["rescope_matter"].detail  # before -> after


def test_the_administrative_grant_is_not_an_implicit_superuser(store: SqlStore) -> None:
    # an admin with NO rbac scope reads an empty corpus (AD-12) — the grant administers, it
    # does not widen a data read.
    admin = store.create_user(TENANT, "admin@c.fr", "password1", "Admin", set(), is_admin=True)
    is_admin, scopes = store.identity(admin)
    assert is_admin is True and scopes == set()
    assert store.matters(TENANT, scopes) == []          # sees no matter despite being admin
    with pytest.raises(ScopeDenied):
        store.inventory(MATTER, TENANT, scopes)
