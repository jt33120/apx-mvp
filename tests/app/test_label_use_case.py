"""The labelling app use-case forwards to the recorder port, and the real store satisfies it
(Story 4.5, FR-40/AD-4): a caller depends on core, never on the store adapter."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestionResult
from apx.core.app.label import assign_taxonomy_label, revert_taxonomy_label


class _FakeRecorder:
    """A pure-core stand-in for the store — records the forwarded call, returns a seq."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def assign_label(self, *, tenant, matter, actor, piece_id, label, scopes,  # noqa: ANN001,ANN003
                     expected_seq=None) -> int:
        self.calls.append(
            ("assign", tenant, matter, actor, piece_id, label, frozenset(scopes), expected_seq))
        return 7

    def revert_label(self, *, tenant, matter, actor, piece_id, to_seq, scopes) -> int:  # noqa: ANN001
        self.calls.append(("revert", tenant, matter, actor, piece_id, to_seq, frozenset(scopes)))
        return 8


def test_assign_forwards_every_argument_and_returns_the_seq() -> None:
    rec = _FakeRecorder()
    seq = assign_taxonomy_label(
        rec, tenant="t", matter="m", actor="a", piece_id="p", label="Contrats", scopes={"w"},
        expected_seq=3)
    assert seq == 7
    assert rec.calls == [("assign", "t", "m", "a", "p", "Contrats", frozenset({"w"}), 3)]


def test_revert_forwards_every_argument_and_returns_the_seq() -> None:
    rec = _FakeRecorder()
    seq = revert_taxonomy_label(
        rec, tenant="t", matter="m", actor="a", piece_id="p", to_seq=1, scopes={"w"})
    assert seq == 8
    assert rec.calls == [("revert", "t", "m", "a", "p", 1, frozenset({"w"}))]


@pytest.fixture
def store() -> SqlStore:
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    s = SqlStore(sessionmaker(bind=e, future=True))
    s.save(IngestionResult(), scope="w", actor="setup", matter="m", tenant="t", audit=False)
    s.set_config("t", "admin", "taxonomy", ["Contrats", "Jurisprudence"])
    return s


def test_the_real_store_satisfies_the_recorder_port_end_to_end(store: SqlStore) -> None:
    # the use-case takes the store AS a TaxonomyLabelRecorder (structural typing) and persists —
    # proving SqlStore satisfies the port and the API can depend on core, not the adapter (AD-4).
    seq = assign_taxonomy_label(
        store, tenant="t", matter="m", actor="me", piece_id="p1", label="Contrats", scopes={"w"})
    assert seq == 1
    cur = store.read_current_label(tenant="t", matter="m", piece_id="p1", scopes={"w"})
    assert cur.label == "Contrats" and cur.source == "human"
    reverted = revert_taxonomy_label(
        store, tenant="t", matter="m", actor="me", piece_id="p1", to_seq=1, scopes={"w"})
    assert reverted == 2  # a reversal through the seam is a new append-only entry
