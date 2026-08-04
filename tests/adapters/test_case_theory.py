"""The optional case theory — versioned, audited, append-only, scope-checked (Story 4.1, FR-37).

``append_case_theory_version`` is the ONE owning use case (AD-37): each distinct write is a new
version recorded in the audit record ATOMIC with it (AD-22); an unchanged text is a no-op; a
withdrawal is a NULL-text version that never hard-deletes a prior one (AD-7). Reads are scope
pre-filtered and non-disclosing (FR-14). The version id is the deterministic identity a future
ranking version names (AD-23).
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.backfill import case_theory_version_id
from apx.adapters.store_postgres.models import AuditRecord, Base, CaseTheoryVersion, MatterScope
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestionResult


@pytest.fixture
def engine():  # noqa: ANN201
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    return e


@pytest.fixture
def store(engine) -> SqlStore:  # noqa: ANN001
    s = SqlStore(sessionmaker(bind=engine, future=True))
    # a matter under wall "w", created silently (no ingest audit noise) — the upload-init save shape
    s.save(IngestionResult(), scope="w", actor="setup", matter="m", tenant="t", audit=False)
    return s


def _actions(store: SqlStore) -> list[str]:
    with store._sf() as s:
        return list(s.scalars(
            select(AuditRecord.action).where(AuditRecord.tenant == "t").order_by(AuditRecord.seq)))


def test_a_first_write_creates_version_1_and_one_audit_entry(store: SqlStore) -> None:
    state = store.append_case_theory_version(
        tenant="t", matter="m", actor="me.durand", text="contestation d'un licenciement")
    assert state.present and not state.withdrawn
    assert state.current.version_no == 1 and state.current.text == "contestation d'un licenciement"
    trail = store.read_audit("m", "t", {"w"})
    assert [e.action for e in trail.entries] == ["case_theory_written"]
    assert trail.entries[0].actor == "me.durand" and trail.verified  # actor + chain
    with store._sf() as s:  # the denormalised cache tracks the latest active text
        assert s.get(MatterScope, {"tenant": "t", "matter": "m"}).case_theory \
            == "contestation d'un licenciement"


def test_a_rewrite_appends_a_new_version_and_keeps_the_prior_readable(store: SqlStore) -> None:
    store.append_case_theory_version(tenant="t", matter="m", actor="a", text="v1")
    state = store.append_case_theory_version(tenant="t", matter="m", actor="b", text="v2")
    assert state.current.version_no == 2 and state.current.text == "v2"
    versions = store.list_case_theory_versions(tenant="t", matter="m", scopes={"w"})
    assert [(v.version_no, v.text) for v in versions] == [(1, "v1"), (2, "v2")]  # prior retained
    assert _actions(store) == ["case_theory_written", "case_theory_written"]


def test_an_identical_rewrite_is_an_idempotent_no_op(store: SqlStore) -> None:
    store.append_case_theory_version(tenant="t", matter="m", actor="a", text="same")
    # the whitespace-padded restatement normalises equal to the current text → a no-op
    store.append_case_theory_version(tenant="t", matter="m", actor="a", text="  same  ")
    versions = store.list_case_theory_versions(tenant="t", matter="m", scopes={"w"})
    assert [v.version_no for v in versions] == [1]     # no second version
    assert _actions(store) == ["case_theory_written"]  # no phantom audit entry


def test_withdrawal_is_append_only_and_prior_versions_remain_readable(store: SqlStore) -> None:
    store.append_case_theory_version(tenant="t", matter="m", actor="a", text="v1")
    state = store.append_case_theory_version(tenant="t", matter="m", actor="a", text=None)
    assert not state.present and state.withdrawn and state.current.version_no == 2
    cur = store.read_case_theory(tenant="t", matter="m", scopes={"w"})
    assert not cur.present and cur.withdrawn          # the current read reports withdrawn
    versions = store.list_case_theory_versions(tenant="t", matter="m", scopes={"w"})
    assert [(v.version_no, v.text) for v in versions] == [(1, "v1"), (2, None)]  # v1 still readable
    assert _actions(store) == ["case_theory_written", "case_theory_withdrawn"]
    with store._sf() as s:  # the cache is NULL after a withdrawal
        assert s.get(MatterScope, {"tenant": "t", "matter": "m"}).case_theory is None


def test_withdrawing_a_never_set_theory_is_a_no_op(store: SqlStore) -> None:
    state = store.append_case_theory_version(tenant="t", matter="m", actor="a", text=None)
    assert not state.present and not state.withdrawn and state.current is None
    assert store.list_case_theory_versions(tenant="t", matter="m", scopes={"w"}) == []
    assert _actions(store) == []  # nothing written


def test_the_version_id_is_deterministic_and_matches_the_stored_row(store: SqlStore) -> None:
    store.append_case_theory_version(tenant="t", matter="m", actor="a", text="théorie")
    expected = case_theory_version_id("t", "m", 1, "théorie")
    with store._sf() as s:
        row = s.scalar(select(CaseTheoryVersion))
    assert row.id == expected == case_theory_version_id("t", "m", 1, "théorie")  # stable id


def test_a_write_to_an_unknown_matter_raises(store: SqlStore) -> None:
    with pytest.raises(ValueError, match="unknown matter"):
        store.append_case_theory_version(tenant="t", matter="ghost", actor="a", text="x")


def test_reads_are_scope_gated_and_non_disclosing(store: SqlStore) -> None:
    store.append_case_theory_version(tenant="t", matter="m", actor="a", text="secret")
    # a scope not holding the matter's wall is indistinguishable from an absent matter (FR-14)
    assert store.read_case_theory(tenant="t", matter="m", scopes={"other"}) is None
    assert store.list_case_theory_versions(tenant="t", matter="m", scopes={"other"}) is None
    assert store.read_case_theory(tenant="t", matter="absent", scopes={"w"}) is None
    assert store.read_case_theory(tenant="t", matter="m", scopes={"w"}).current.text == "secret"


def test_a_write_only_touches_the_version_and_its_audit_entry(store: SqlStore) -> None:
    # the "re-rank is never automatic" guarantee: a write's ONLY effects are the version row, the
    # cache update and ONE audit entry — there is no ranking artefact to recompute (none exists).
    store.append_case_theory_version(tenant="t", matter="m", actor="a", text="x")
    with store._sf() as s:
        assert s.scalar(select(func.count()).select_from(CaseTheoryVersion)) == 1
        assert s.scalar(select(func.count()).select_from(AuditRecord)) == 1
