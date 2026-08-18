"""A deferral opens the queue it defers onto (Story 7.4, AD-6) — the product's front door.

Found while mapping the terrain for the Epic-4 write surface, and it outranked that story.

``PsycopgConnector.pool`` raises ``AppNotOpen`` until ``open_async`` has been called. Across the
whole of ``apx/`` that call existed in exactly one place — ``manage worker``, a **different
process**. So on any real PostgreSQL deployment the API's ``defer_async`` raised before it touched
the network, the upload route's ``except Exception`` turned it into HTTP 503 *« file d'import
indisponible »*, and **every submission failed**. The one gesture the product opens with.

The reason it survived eleven epics is the interesting half. ``_connector()`` picks the connector
from ``DATABASE_URL`` when the queue module is imported; the suite runs on SQLite; SQLite yields
``testing.InMemoryConnector``, which is the one implementation with no such guard. The defect
existed only in the configuration no test uses — so a green suite was not evidence about it either
way, and could not become evidence by adding more tests of the same kind.

These tests therefore assert the two halves separately: the library behaviour that makes the failure
real, and the property that now prevents it.
"""

from __future__ import annotations

import asyncio

import pytest
from procrastinate import exceptions
from procrastinate.psycopg_connector import PsycopgConnector

from apx.adapters.store_postgres import queue as queue_module


class _SpyApp:
    """Stands in for the Procrastinate App so the property can be asserted without a database."""

    def __init__(self) -> None:
        self.opened = 0
        self.closed = 0

    async def open_async(self) -> None:
        self.opened += 1

    async def close_async(self) -> None:
        self.closed += 1


@pytest.fixture
def spy(monkeypatch) -> _SpyApp:  # noqa: ANN001
    app = _SpyApp()
    monkeypatch.setattr(queue_module, "app", app)
    monkeypatch.setattr(queue_module, "_opened", False)
    return app


# ── the mechanism, pinned so the fix cannot be read as superstition ───────────────────────────

def test_the_real_connector_refuses_to_defer_before_it_is_opened() -> None:
    """The library behaviour the whole story rests on, asserted with no network and no database:
    the pool is not lazily created, it is absent, and reaching for it raises."""
    connector = PsycopgConnector(conninfo="postgresql://apx@localhost/apx")
    with pytest.raises(exceptions.AppNotOpen):
        _ = connector.pool


def test_the_test_connector_does_not_have_that_guard() -> None:
    """And why eleven epics of green tests said nothing about it. This is not a criticism of the
    in-memory connector — it is the reason a suite that never runs the production configuration
    cannot be evidence about the production configuration."""
    from procrastinate import testing

    assert testing.InMemoryConnector().jobs == {}      # usable with no open at all


# ── the property ──────────────────────────────────────────────────────────────────────────────

def test_enqueuing_opens_the_queue(spy: _SpyApp) -> None:
    """The defect, reversed. Before this story ``enqueue_import`` went straight to ``defer_async``
    and the pool was whatever another process had left behind."""
    asyncio.run(queue_module.ensure_open())
    assert spy.opened == 1


def test_the_enqueue_helper_itself_opens_before_it_defers(spy: _SpyApp) -> None:
    """The property on the function the route actually calls, not on the helper underneath it — an
    enqueue that opened nothing is exactly what shipped."""
    asyncio.run(queue_module.enqueue_import("job-x"))
    assert spy.opened == 1


def test_a_second_deferral_does_not_open_it_again(spy: _SpyApp) -> None:
    """Once per process. A pool per upload would exhaust PostgreSQL's connection limit on the one
    path that is expected to be used in bursts."""
    async def _twice() -> None:
        await queue_module.ensure_open()
        await queue_module.ensure_open()

    asyncio.run(_twice())
    assert spy.opened == 1


def test_concurrent_deferrals_open_it_exactly_once(spy: _SpyApp) -> None:
    """Two uploads arriving together are the ordinary case, not the corner one — the guard is a
    lock and a re-check inside it, not a bare flag."""
    async def _together() -> None:
        await asyncio.gather(*(queue_module.ensure_open() for _ in range(8)))

    asyncio.run(_together())
    assert spy.opened == 1


def test_closing_releases_it_and_is_idempotent(spy: _SpyApp) -> None:
    async def _cycle() -> None:
        await queue_module.ensure_open()
        await queue_module.close_queue()
        await queue_module.close_queue()      # a process that never deferred closes nothing

    asyncio.run(_cycle())
    assert (spy.opened, spy.closed) == (1, 1)


def test_the_api_opens_the_queue_at_boot(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    """Deferring opens it, so this is not what makes the upload path work. It is what makes a queue
    the API cannot reach a failure at container start rather than a 503 handed to the first lawyer
    who drops a folder on it."""
    from fastapi.testclient import TestClient

    from apx.api.app import app
    from tests.api.test_ingest_api import _prepare

    _prepare(tmp_path, monkeypatch)
    monkeypatch.setattr(queue_module, "_opened", False)
    with TestClient(app):
        assert queue_module._opened is True
