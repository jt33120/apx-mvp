"""The line-placement app use-case forwards to the recorder port, and the real store satisfies it
(Story 4.8, FR-17/AD-4): a caller depends on core, never on the store adapter."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.line import place_line, read_current_line
from apx.core.domain.line import LinePlacementView


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


def test_the_real_store_satisfies_the_recorder_port() -> None:
    # the store is a structural LinePlacementRecorder — the app seam can drive it directly (AD-4)
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    store = SqlStore(sessionmaker(bind=e, future=True))
    assert callable(store.place_line) and callable(store.read_current_line)
