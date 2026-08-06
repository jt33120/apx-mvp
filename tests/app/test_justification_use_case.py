"""The justification app use-case forwards to the recorder port, and the real store satisfies it
(Story 4.6, FR-41/AD-4): a caller depends on core, never on the store adapter."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.justification import (
    read_justification,
    record_justification,
    reject_justification,
    restore_justification,
)
from apx.core.domain.justification import EvidenceExtract, JustificationBasis


class _FakeStore:
    """A pure-core stand-in for the store — records the forwarded call."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def record_justification(  # noqa: ANN001,ANN003
        self, *, tenant, matter, actor, piece_id, sentence, basis, evidence,
        source_language=None, scopes, version_no=None,
    ) -> None:
        self.calls.append(
            ("record", tenant, matter, actor, piece_id, sentence, basis, evidence, source_language,
             frozenset(scopes), version_no))

    def read_justification(self, *, tenant, matter, scopes, piece_id,  # noqa: ANN001,ANN003
                           version_no=None, interface_language=None):
        self.calls.append(("read", tenant, matter, frozenset(scopes), piece_id, interface_language))
        return None

    def reject_justification(self, *, tenant, matter, actor, piece_id, scopes,  # noqa: ANN001,ANN003
                             reason=None, expected_seq=None) -> int:
        self.calls.append(("reject", tenant, matter, actor, piece_id, reason, expected_seq))
        return 3

    def restore_justification(self, *, tenant, matter, actor, piece_id, scopes,  # noqa: ANN001,ANN003
                              reason=None, expected_seq=None) -> int:
        self.calls.append(("restore", tenant, matter, actor, piece_id, reason, expected_seq))
        return 4


def test_record_forwards_every_argument() -> None:
    store = _FakeStore()
    basis = JustificationBasis.case_theory("v")
    evidence = (EvidenceExtract("c1", "x"),)
    record_justification(
        store, tenant="t", matter="m", actor="a", piece_id="p", sentence="s", basis=basis,
        evidence=evidence, source_language="fr", scopes={"w"}, version_no=2)
    assert store.calls == [
        ("record", "t", "m", "a", "p", "s", basis, evidence, "fr", frozenset({"w"}), 2)]


def test_reject_and_restore_forward_and_return_the_seq() -> None:
    store = _FakeStore()
    assert reject_justification(
        store, tenant="t", matter="m", actor="a", piece_id="p", scopes={"w"}, reason="wrong") == 3
    assert restore_justification(
        store, tenant="t", matter="m", actor="a", piece_id="p", scopes={"w"}) == 4
    assert store.calls[0] == ("reject", "t", "m", "a", "p", "wrong", None)
    assert store.calls[1] == ("restore", "t", "m", "a", "p", None, None)


def test_read_forwards_and_returns() -> None:
    store = _FakeStore()
    assert read_justification(
        store, tenant="t", matter="m", scopes={"w"}, piece_id="p", interface_language="en") is None
    assert store.calls == [("read", "t", "m", frozenset({"w"}), "p", "en")]


def test_the_real_store_satisfies_the_port() -> None:
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    store = SqlStore(sessionmaker(bind=e, future=True))
    assert callable(store.record_justification) and callable(store.read_justification)
    assert callable(store.reject_justification) and callable(store.restore_justification)
