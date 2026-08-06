"""The pin app use-case forwards to the recorder port, and the real store satisfies it
(Story 4.11, FR-43/AD-4): a caller depends on core, never on the store adapter."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.pin import pin_piece, read_current_pins, remove_pin
from apx.core.domain.triage_sets import Pin, PinSide


class _FakeRecorder:
    """A pure-core stand-in for the store — records the forwarded call."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def pin_piece(self, *, tenant, matter, actor, piece_id, side, reason,  # noqa: ANN001,ANN003
                 scopes, expected_seq=None) -> int:
        self.calls.append(
            ("pin", tenant, matter, actor, piece_id, side, reason, frozenset(scopes), expected_seq))
        return 5

    def remove_pin(self, *, tenant, matter, actor, piece_id, scopes,  # noqa: ANN001,ANN003
                  expected_seq=None) -> int:
        self.calls.append(("remove", tenant, matter, actor, piece_id, frozenset(scopes)))
        return 6

    def read_current_pins(self, *, tenant, matter, scopes):  # noqa: ANN001,ANN003
        self.calls.append(("read", tenant, matter, frozenset(scopes)))
        return (Pin("c", PinSide.RETAIN),)


def test_pin_piece_forwards_every_argument_and_returns_the_seq() -> None:
    rec = _FakeRecorder()
    seq = pin_piece(rec, tenant="t", matter="m", actor="a", piece_id="c", side=PinSide.RETAIN,
                    reason="décisif", scopes={"w"}, expected_seq=2)
    assert seq == 5
    assert rec.calls == [
        ("pin", "t", "m", "a", "c", PinSide.RETAIN, "décisif", frozenset({"w"}), 2)]


def test_remove_pin_forwards_every_argument() -> None:
    rec = _FakeRecorder()
    assert remove_pin(rec, tenant="t", matter="m", actor="a", piece_id="c", scopes={"w"}) == 6
    assert rec.calls == [("remove", "t", "m", "a", "c", frozenset({"w"}))]


def test_read_current_pins_forwards_and_returns_the_pins() -> None:
    rec = _FakeRecorder()
    pins = read_current_pins(rec, tenant="t", matter="m", scopes={"w"})
    assert pins == (Pin("c", PinSide.RETAIN),)
    assert rec.calls == [("read", "t", "m", frozenset({"w"}))]


def test_the_real_store_satisfies_the_recorder_port() -> None:
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    store = SqlStore(sessionmaker(bind=e, future=True))
    assert callable(store.pin_piece) and callable(store.remove_pin)
    assert callable(store.read_current_pins)
