"""Adversarial cross-tenant isolation (story 1.4, AC3/AC4/AC5). Two tenants, each with a
matter, a corpus (sharing a common word so a leak would inflate a count), users and an
audit trail. Acting as tenant A, NO read surface may return tenant B's data, counts or
metadata; a foreign matter, an unknown tenant, or no scope fails closed. Runs on in-memory
SQLite everywhere — the wall is DDL-independent, so this is the full proof, not a subset.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import ScopeDenied, SqlStore
from apx.core.app.ingest import IngestedPiece, IngestionResult

A_TENANT, A_MATTER, A_SCOPE = "cabinet-a", "m-a", "wall-a"
B_TENANT, B_MATTER, B_SCOPE = "cabinet-b", "m-b", "wall-b"
_SHARED = "contrat"  # present in BOTH corpora — a tenant leak would inflate A's counts


def _piece(pid: str, tenant: str, matter: str, text: str) -> IngestedPiece:
    return IngestedPiece(
        id=pid, matter=matter, tenant=tenant, content_hash=pid, text_key=pid,
        provenance_path=f"/{tenant}/{pid}.txt", custodian="c", extraction_method="text",
        extractor_version="v", schema_version="s", ingestion_timestamp=datetime.now(UTC),
        full_text=text, text_version="v",
    )


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    s = SqlStore(sessionmaker(bind=engine, future=True))
    # tenant A — one matter, one pièce with the shared word.
    s.save(IngestionResult(pieces=[
        _piece("a1", A_TENANT, A_MATTER, "un contrat de bail commercial"),
        _piece("a2", A_TENANT, A_MATTER, "assignation devant le tribunal"),
    ]), scope=A_SCOPE, actor="a-admin")
    # tenant B — a different matter, TWO pièces with the shared word (a leak would show).
    s.save(IngestionResult(pieces=[
        _piece("b1", B_TENANT, B_MATTER, "un contrat de prestation"),
        _piece("b2", B_TENANT, B_MATTER, "un autre contrat, secret, de B"),
    ]), scope=B_SCOPE, actor="b-admin")
    s.create_user(A_TENANT, "a@a.test", "pw", "Avocat A", {A_SCOPE})
    s.create_user(B_TENANT, "b@b.test", "pw", "Avocat B", {B_SCOPE})
    return s


# ── positive isolation: acting as A, only A's world is visible ──


def test_matters_lists_only_the_callers_tenant(store: SqlStore) -> None:
    assert [m.matter for m in store.matters(A_TENANT, {A_SCOPE})] == [A_MATTER]


def test_search_total_and_hits_are_tenant_bound(store: SqlStore) -> None:
    # "contrat" is in 1 A pièce and 2 B pièces; A must see exactly its own — a leak → 3.
    res = store.search(A_TENANT, {A_SCOPE}, _SHARED)
    assert res.total == 1
    assert all(h.matter == A_MATTER for h in res.hits)
    assert all("secret" not in h.snippet for h in res.hits)


def test_inventory_counts_exclude_the_other_tenant(store: SqlStore) -> None:
    assert store.inventory(A_MATTER, A_TENANT, {A_SCOPE}).in_corpus == 2  # a1+a2, never b1/b2


def test_list_users_is_tenant_bound(store: SqlStore) -> None:
    assert [u.email for u in store.list_users(A_TENANT)] == ["a@a.test"]


def test_read_audit_verifies_only_its_own_tenant_chain(store: SqlStore) -> None:
    # A's per-tenant chain recomputes cleanly end to end; reading B's matter is denied
    # (covered by the parametrized denial suite), so A never sees B's audit trail.
    trail = store.read_audit(A_MATTER, A_TENANT, {A_SCOPE})
    assert trail.verified and len(trail.entries) >= 1


def test_scopes_for_returns_only_that_users_own_walls(store: SqlStore) -> None:
    a_user = store.authenticate(A_TENANT, "a@a.test", "pw")
    assert a_user is not None and store.scopes_for(a_user.id) == {A_SCOPE}


# ── denial: A cannot touch B's matter, on any scope (tenant is applied FIRST) ──

_SCOPED_READS: list[tuple[str, Callable[[SqlStore, str, str, set[str]], object]]] = [
    ("inventory", lambda s, m, t, sc: s.inventory(m, t, sc)),
    ("deduplicate", lambda s, m, t, sc: s.deduplicate(m, t, sc)),
    ("representatives", lambda s, m, t, sc: s.representatives(m, t, sc)),
    ("labels", lambda s, m, t, sc: s.labels(m, t, sc)),
    ("read_audit", lambda s, m, t, sc: s.read_audit(m, t, sc)),
    ("sample_discards", lambda s, m, t, sc: s.sample_discards(m, t, sc, 5)),
]
_IDS = [n for n, _ in _SCOPED_READS]


@pytest.mark.parametrize("name,call", _SCOPED_READS, ids=_IDS)
def test_a_scoped_read_of_a_foreign_matter_is_denied(
    store: SqlStore, name: str, call: Callable[..., object]
) -> None:
    # A holds A's scope and asks about B's matter — denied, never B's rows.
    with pytest.raises(ScopeDenied):
        call(store, B_MATTER, A_TENANT, {A_SCOPE})


@pytest.mark.parametrize("name,call", _SCOPED_READS, ids=_IDS)
def test_tenant_is_applied_before_scope_even_holding_bs_scope(
    store: SqlStore, name: str, call: Callable[..., object]
) -> None:
    # A's tenant + B's scope against B's matter STILL denies: the tenant term is not
    # optional and not a post-filter (AD-12 tenant-first).
    with pytest.raises(ScopeDenied):
        call(store, B_MATTER, A_TENANT, {B_SCOPE})


# ── fail closed: an unknown tenant, or no scope, sees nothing ──


def test_an_unknown_tenant_sees_no_matters_and_no_search(store: SqlStore) -> None:
    assert store.matters("ghost", {A_SCOPE}) == []
    assert store.search("ghost", {A_SCOPE}, _SHARED).total == 0


def test_no_scope_yields_an_empty_world(store: SqlStore) -> None:
    assert store.matters(A_TENANT, set()) == []
    assert store.search(A_TENANT, set(), _SHARED).total == 0
