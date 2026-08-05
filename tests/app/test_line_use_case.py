"""The line-placement app use-case forwards to the recorder port, and the real store satisfies it
(Story 4.8, FR-17/AD-4): a caller depends on core, never on the store adapter."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.line import move_line, place_line, price_line_move, read_current_line
from apx.core.domain.line import LinePlacementView
from apx.core.domain.line_projection import PricedMove


class _FakeRecorder:
    """A pure-core stand-in for the store — records the forwarded call, returns a view."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self._view = LinePlacementView(
            version_id="v" * 64, version_no=1, last_retained_piece_id="p", basis="intrinsic:x",
            seq=1, at=datetime(2026, 8, 5, tzinfo=UTC))

    def place_line(self, *, tenant, matter, actor, scopes, version_no=None):  # noqa: ANN001,ANN003
        self.calls.append(
            ("place", tenant, matter, actor, frozenset(scopes), version_no))
        return self._view

    def read_current_line(self, *, tenant, matter, scopes, version_no=None):  # noqa: ANN001,ANN003
        self.calls.append(("read", tenant, matter, frozenset(scopes), version_no))
        return self._view

    def price_line_move(self, *, tenant, matter, scopes,  # noqa: ANN001,ANN003
                        candidate_last_retained_piece_id, version_no=None):
        self.calls.append(
            ("price", tenant, matter, frozenset(scopes), candidate_last_retained_piece_id))
        return PricedMove(pieces_to_read_delta=3, current_prevalence=0.03,
                          candidate_prevalence=0.004, discarded_empty=False,
                          prevalence_available=True)

    def move_line(self, *, tenant, matter, actor, scopes,  # noqa: ANN001,ANN003
                 last_retained_piece_id, expected_seq, priced_statement, version_no=None):
        self.calls.append(
            ("move", tenant, matter, actor, last_retained_piece_id, expected_seq, priced_statement))
        return self._view


def test_place_line_forwards_every_argument_and_returns_the_view() -> None:
    rec = _FakeRecorder()
    view = place_line(rec, tenant="t", matter="m", actor="a", scopes={"w"}, version_no=2)
    assert view is rec._view
    assert rec.calls == [("place", "t", "m", "a", frozenset({"w"}), 2)]


def test_read_current_line_forwards_every_argument() -> None:
    rec = _FakeRecorder()
    view = read_current_line(rec, tenant="t", matter="m", scopes={"w"})
    assert view is rec._view
    assert rec.calls == [("read", "t", "m", frozenset({"w"}), None)]


def test_price_line_move_forwards_and_returns_the_projection() -> None:
    rec = _FakeRecorder()
    move = price_line_move(
        rec, tenant="t", matter="m", scopes={"w"}, candidate_last_retained_piece_id="p")
    assert move.pieces_to_read_delta == 3 and move.candidate_prevalence == 0.004
    assert rec.calls == [("price", "t", "m", frozenset({"w"}), "p")]


def test_move_line_forwards_every_argument() -> None:
    rec = _FakeRecorder()
    view = move_line(
        rec, tenant="t", matter="m", actor="a", scopes={"w"}, last_retained_piece_id="p",
        expected_seq=2, priced_statement="shown")
    assert view is rec._view
    assert rec.calls == [("move", "t", "m", "a", "p", 2, "shown")]


def test_the_real_store_satisfies_the_recorder_port() -> None:
    # the store is a structural LinePlacementRecorder — the app seam can drive it directly (AD-4)
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    store = SqlStore(sessionmaker(bind=e, future=True))
    assert callable(store.place_line) and callable(store.read_current_line)
    assert callable(store.price_line_move) and callable(store.move_line)
