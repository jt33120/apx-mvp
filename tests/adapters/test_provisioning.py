"""Provisioning a tenant through the surface (story 1.9, AD-25): one audited act establishes the
tenant's first administrative grant, its scopes and its taxonomy — and fails closed if the tenant
already has an administrator (no silent takeover of a live firm). SQLite everywhere.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import AuditRecord, Base
from apx.adapters.store_postgres.store import SqlStore, TenantAlreadyProvisioned

TENANT = "cabinet"


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def test_provision_establishes_the_first_admin_with_scopes_and_taxonomy(store: SqlStore) -> None:
    uid = store.provision_tenant(
        TENANT, "patron@cabinet.fr", "un-mot-de-passe", "Le Patron",
        scopes={"pole-assurance", "pole-penal"}, taxonomy=["conclusions", "pièce adverse"],
    )
    # the first admin can see and grant (is_admin) and holds the scopes
    is_admin, scopes = store.identity(uid)
    assert is_admin is True
    assert scopes == {"pole-assurance", "pole-penal"}
    # the taxonomy is seeded as an audited configuration value
    assert store.get_config(TENANT, "taxonomy") == ["conclusions", "pièce adverse"]
    # and every value is traceable to the surface (nothing looks like a direct edit)
    assert all(p.audited for p in store.config_provenance(TENANT))


def test_provision_is_one_audited_act(store: SqlStore) -> None:
    store.provision_tenant(TENANT, "p@c.fr", "pw12345678", "P", scopes={"w"}, taxonomy=["x"])
    with store._sf() as s:
        rows = s.execute(
            select(AuditRecord.seq, AuditRecord.action).where(AuditRecord.tenant == TENANT)
            .order_by(AuditRecord.seq)
        ).all()
    seqs = [seq for seq, _ in rows]
    actions = [action for _, action in rows]
    # three appends in ONE transaction get monotonic, gap-free per-tenant seqs (1, 2, 3)
    assert seqs == [1, 2, 3]
    assert actions == ["tenant_provisioned", "create_user", "config_changed"]


def test_provision_fails_closed_if_an_admin_already_exists(store: SqlStore) -> None:
    store.provision_tenant(TENANT, "first@c.fr", "pw12345678", "First", scopes=set(), taxonomy=[])
    with pytest.raises(TenantAlreadyProvisioned):
        store.provision_tenant(
            TENANT, "usurper@c.fr", "pw12345678", "Usurper", scopes=set(), taxonomy=[])
    # the usurper was never created — the tenant still has exactly its first admin
    users = store.list_users(TENANT)
    assert [u.email for u in users] == ["first@c.fr"]


def test_provision_with_empty_taxonomy_seeds_no_setting_row(store: SqlStore) -> None:
    store.provision_tenant(TENANT, "p@c.fr", "pw12345678", "P", scopes={"w"}, taxonomy=[])
    assert store.get_config(TENANT, "taxonomy") == []      # the schema default
    with store._sf() as s:
        # no phantom config_changed for an empty taxonomy
        assert not s.execute(
            select(AuditRecord).where(AuditRecord.action == "config_changed")).first()


def test_provision_second_tenant_is_independent(store: SqlStore) -> None:
    a = store.provision_tenant("cab-a", "a@a.fr", "pw12345678", "A", scopes={"w"}, taxonomy=["ta"])
    b = store.provision_tenant("cab-b", "b@b.fr", "pw12345678", "B", scopes={"w"}, taxonomy=["tb"])
    assert a != b
    assert store.get_config("cab-a", "taxonomy") == ["ta"]
    assert store.get_config("cab-b", "taxonomy") == ["tb"]  # config is per tenant
