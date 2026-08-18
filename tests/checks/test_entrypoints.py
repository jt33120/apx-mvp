"""Smoke test: the entrypoint boundary objects import and construct.

import-linter analyses the graph statically (grimp parses the AST; it does not
execute modules), so a broken *runtime* import in an entrypoint would ship green
with no other test importing it. This closes that gap for the two boundaries 1.1
ships — the FastAPI app and the Procrastinate worker app — and nothing more.
"""

from __future__ import annotations

from procrastinate.tasks import Task


def test_api_app_imports_and_exposes_the_slice_routes() -> None:
    from apx.api.app import app

    # Slice A adds the inventory path. (Story 1.1 shipped the empty boundary; the
    # slice legitimately wires routes onto it.) Assert the app imports and the
    # expected routes are present — an import regression or a dropped route fails.
    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/health" in paths
    assert "/api/ingest" in paths


def test_worker_app_exposes_every_task_the_queue_defines() -> None:
    """Every task the sealed queue package defines is reachable from the worker boundary.

    Story 2.2 wired the first one (Story 1.1 shipped zero) and this asserted the name. Story 7.6
    added the ranking task and the assertion had to change — so it now states the PROPERTY instead
    of the inventory, because the inventory is what a second task breaks and the property is what a
    second task must satisfy.

    There is no task discovery here: ``apx/worker/app.py`` is a bare re-export of the queue app, so
    a task defined in a submodule that ``queue/__init__.py`` never imports is **never registered**,
    and every job deferred onto it dies at dispatch with an unknown-task error. Comparing the two
    sets is what would catch that; comparing against a hand-written list would not."""
    from apx.adapters.store_postgres import queue as queue_module
    from apx.worker.app import app

    ours = {name for name in app.tasks if name.startswith("apx")}
    defined = {
        t.name for t in vars(queue_module).values()
        if isinstance(t, Task) and t.name.startswith("apx")}
    assert defined, "the queue package defines no task at all — this check cannot be passing"
    assert ours == defined, (
        f"the worker boundary exposes {sorted(ours)} and the queue defines {sorted(defined)} — a "
        "task the worker cannot see is a queue that accepts jobs nothing will ever run")
