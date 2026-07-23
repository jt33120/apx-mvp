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
