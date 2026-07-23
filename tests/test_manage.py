"""The operational CLI: bootstrap a user (the first admin) into the store."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore
from apx.manage import _create_user, build_parser, ensure_admin


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def test_create_user_cli_bootstraps_an_admin(store: SqlStore) -> None:
    args = build_parser().parse_args([
        "create-user", "--tenant", "t", "--email", "Patron@Cabinet.fr", "--name", "Le Patron",
        "--admin", "--scope", "pole-assurance", "--scope", "pole-penal",
    ])
    uid = _create_user(store, args, "s3cret")

    user = store.authenticate("t", "patron@cabinet.fr", "s3cret")  # email normalised
    assert user is not None and user.id == uid
    assert store.identity(uid) == (True, {"pole-assurance", "pole-penal"})


def test_create_parser_requires_a_subcommand() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_ensure_admin_is_idempotent(store: SqlStore, monkeypatch) -> None:
    monkeypatch.setenv("APX_BOOTSTRAP_ADMIN_EMAIL", "boot@c.fr")
    monkeypatch.setenv("APX_BOOTSTRAP_ADMIN_PASSWORD", "pw")
    monkeypatch.setenv("APX_BOOTSTRAP_ADMIN_TENANT", "t")
    monkeypatch.setenv("APX_BOOTSTRAP_ADMIN_SCOPES", "w1, w2")

    assert "created" in ensure_admin(store)
    user = store.authenticate("t", "boot@c.fr", "pw")
    assert user is not None and store.identity(user.id) == (True, {"w1", "w2"})
    assert "already exists" in ensure_admin(store)  # a second boot changes nothing


def test_ensure_admin_is_a_noop_without_env(store: SqlStore, monkeypatch) -> None:
    monkeypatch.delenv("APX_BOOTSTRAP_ADMIN_EMAIL", raising=False)
    assert "nothing to do" in ensure_admin(store)
