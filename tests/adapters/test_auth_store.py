"""Owned identity in the store: users, password auth, authoritative scope grants."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def test_create_authenticate_and_scopes(store: SqlStore) -> None:
    uid = store.create_user("cabinet", "Me.Durand@Cabinet.fr", "s3cret!", "Me Durand",
                            {"pole-assurance", "pole-penal"})
    u = store.authenticate("cabinet", "me.durand@cabinet.fr", "s3cret!")  # email case-insensitive
    assert u is not None and u.id == uid and u.display_name == "Me Durand"
    assert store.scopes_for(uid) == {"pole-assurance", "pole-penal"}


def test_wrong_password_unknown_user_and_other_tenant_fail(store: SqlStore) -> None:
    store.create_user("cabinet", "a@b.fr", "right", "A", {"w"})
    assert store.authenticate("cabinet", "a@b.fr", "wrong") is None
    assert store.authenticate("cabinet", "ghost@b.fr", "right") is None
    assert store.authenticate("autre-cabinet", "a@b.fr", "right") is None  # tenant-scoped


def test_identity_resolves_admin_flag_and_scopes(store: SqlStore) -> None:
    admin = store.create_user("t", "admin@c.fr", "pw", "Admin", {"w1"}, is_admin=True)
    regular = store.create_user("t", "reg@c.fr", "pw", "Reg", {"w2"})
    assert store.identity(admin) == (True, {"w1"})
    assert store.identity(regular) == (False, {"w2"})


def test_cockpit_lists_users_and_grants_and_revokes(store: SqlStore) -> None:
    uid = store.create_user("t", "a@c.fr", "pw", "A", {"w1"})
    store.create_user("t", "b@c.fr", "pw", "B", set(), is_admin=True)
    roster = {u.email: u for u in store.list_users("t")}
    assert set(roster) == {"a@c.fr", "b@c.fr"}
    assert roster["a@c.fr"].scopes == ("w1",) and roster["a@c.fr"].is_admin is False
    assert roster["b@c.fr"].is_admin is True

    store.grant_scope("t", "admin", uid, "w2")
    assert store.scopes_for(uid) == {"w1", "w2"}
    store.revoke_scope("t", "admin", uid, "w1")
    assert store.scopes_for(uid) == {"w2"}


def test_managing_a_user_in_another_tenant_is_rejected(store: SqlStore) -> None:
    uid = store.create_user("t", "a@c.fr", "pw", "A", set())
    with pytest.raises(ValueError):
        store.grant_scope("autre-cabinet", "admin", uid, "w1")  # the user is not in that tenant


def test_change_password(store: SqlStore) -> None:
    uid = store.create_user("t", "a@c.fr", "old-pass", "A", {"w"})
    assert store.verify_user_password(uid, "old-pass") is True
    assert store.verify_user_password(uid, "nope") is False

    store.set_password(uid, "new-secret")
    assert store.authenticate("t", "a@c.fr", "new-secret") is not None
    assert store.authenticate("t", "a@c.fr", "old-pass") is None  # the old one no longer works
