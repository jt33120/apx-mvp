"""Opaque server-side sessions (story 1.5, AD-15): create, resolve LIVE, expire (absolute
and idle, with a sliding window), delete on sign-out, invalidate all on a password change,
and a revoked scope gone on the next resolve (not at next login). SQLite everywhere.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import AuditRecord, Base
from apx.adapters.store_postgres.store import SqlStore

_ABS = timedelta(hours=8)
_IDLE = timedelta(minutes=30)
_T0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def _user(store: SqlStore, *, admin: bool = False, scopes: Iterable[str] = ("wall-a",)) -> str:
    return store.create_user("cabinet", "a@a.test", "pw", "Avocat A", set(scopes), is_admin=admin)


def test_create_and_resolve_yields_a_live_identity(store: SqlStore) -> None:
    uid = _user(store)
    sid = store.create_session(uid, "cabinet", absolute_ttl=_ABS)
    who = store.resolve_session(sid, idle_ttl=_IDLE)
    assert who is not None
    assert who.user_id == uid and who.tenant == "cabinet" and who.actor == "Avocat A"
    assert who.scopes == {"wall-a"} and who.is_admin is False


def test_an_unknown_session_id_resolves_to_none(store: SqlStore) -> None:
    assert store.resolve_session("not-a-real-id", idle_ttl=_IDLE) is None


def test_absolute_expiry_refuses_and_reaps(store: SqlStore) -> None:
    uid = _user(store)
    sid = store.create_session(uid, "cabinet", absolute_ttl=_ABS, now=_T0)
    assert store.resolve_session(sid, idle_ttl=_IDLE, now=_T0 + timedelta(hours=9)) is None
    # reaped on the failed resolve — gone even back at t0
    assert store.resolve_session(sid, idle_ttl=_IDLE, now=_T0) is None


def test_idle_expiry_refuses(store: SqlStore) -> None:
    uid = _user(store)
    sid = store.create_session(uid, "cabinet", absolute_ttl=_ABS, now=_T0)
    assert store.resolve_session(sid, idle_ttl=_IDLE, now=_T0 + timedelta(minutes=31)) is None


def test_the_idle_window_slides_on_activity(store: SqlStore) -> None:
    uid = _user(store)
    sid = store.create_session(uid, "cabinet", absolute_ttl=_ABS, now=_T0)
    # active at +20min (touches last_seen); then +40min from start is only 20min idle -> ok
    assert store.resolve_session(sid, idle_ttl=_IDLE, now=_T0 + timedelta(minutes=20)) is not None
    assert store.resolve_session(sid, idle_ttl=_IDLE, now=_T0 + timedelta(minutes=40)) is not None


def test_activity_cannot_extend_a_session_past_its_absolute_expiry(store: SqlStore) -> None:
    uid = _user(store)
    sid = store.create_session(uid, "cabinet", absolute_ttl=_ABS, now=_T0)
    # active every 20min keeps the idle window open — but the 8h absolute cap is hard
    for minutes in range(20, int(_ABS.total_seconds() // 60), 20):
        assert store.resolve_session(sid, idle_ttl=_IDLE, now=_T0 + timedelta(minutes=minutes))
    # just past the absolute cap: dead, despite continuous activity
    assert store.resolve_session(sid, idle_ttl=_IDLE, now=_T0 + _ABS + timedelta(seconds=1)) is None


def test_sign_out_deletes_the_session_and_the_id_is_not_reusable(store: SqlStore) -> None:
    uid = _user(store)
    sid = store.create_session(uid, "cabinet", absolute_ttl=_ABS)
    store.delete_session(sid)
    assert store.resolve_session(sid, idle_ttl=_IDLE) is None


def test_password_change_invalidates_all_of_a_users_sessions(store: SqlStore) -> None:
    uid = _user(store)
    a = store.create_session(uid, "cabinet", absolute_ttl=_ABS)
    b = store.create_session(uid, "cabinet", absolute_ttl=_ABS)
    store.delete_user_sessions(uid)
    assert store.resolve_session(a, idle_ttl=_IDLE) is None
    assert store.resolve_session(b, idle_ttl=_IDLE) is None


def test_a_revoked_scope_is_gone_from_a_live_session_on_the_next_request(store: SqlStore) -> None:
    uid = _user(store, scopes=("wall-a", "wall-b"))
    sid = store.create_session(uid, "cabinet", absolute_ttl=_ABS)
    first = store.resolve_session(sid, idle_ttl=_IDLE)
    assert first is not None and first.scopes == {"wall-a", "wall-b"}
    store.revoke_scope("cabinet", uid, "wall-b")
    # the SAME session, next request: wall-b is gone (scopes resolved live) — not at next login
    again = store.resolve_session(sid, idle_ttl=_IDLE)
    assert again is not None and again.scopes == {"wall-a"}


def test_session_ids_are_opaque_and_unique(store: SqlStore) -> None:
    uid = _user(store)
    ids = {store.create_session(uid, "cabinet", absolute_ttl=_ABS) for _ in range(5)}
    assert len(ids) == 5 and all(len(i) >= 32 for i in ids)  # unguessable, non-colliding


def test_auth_failures_are_recorded_in_the_audit(store: SqlStore) -> None:
    # a failed login / lockout is durably audited (FR-48), not only throttled in memory
    _user(store)  # the tenant must exist (have users) — else record_auth_event no-ops
    store.record_auth_event("cabinet", "system:auth", "login_failed", "email=x ip=1.2.3.4")
    store.record_auth_event("cabinet", "system:auth", "login_locked_out", "ip=1.2.3.4")
    with store._sf() as s:  # the test inspects the durable, matterless audit rows
        rows = s.execute(
            select(AuditRecord).where(AuditRecord.tenant == "cabinet").order_by(AuditRecord.seq)
        ).scalars().all()
    assert [r.action for r in rows] == ["login_failed", "login_locked_out"]
    assert all(r.matter is None and r.actor == "system:auth" for r in rows)


def test_auth_events_for_an_unknown_tenant_are_not_recorded(store: SqlStore) -> None:
    # a login-spray with arbitrary tenant names cannot seed audit chains for non-existent firms
    store.record_auth_event("ghost-firm", "system:auth", "login_failed", "email=x ip=1.2.3.4")
    with store._sf() as s:
        count = s.scalar(
            select(func.count()).select_from(AuditRecord).where(AuditRecord.tenant == "ghost-firm")
        )
    assert count == 0
