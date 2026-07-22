"""Smoke test: the entrypoint boundary objects import and construct.

import-linter analyses the graph statically (grimp parses the AST; it does not
execute modules), so a broken *runtime* import in an entrypoint would ship green
with no other test importing it. This closes that gap for the two boundaries 1.1
ships — the FastAPI app and the Procrastinate worker app — and nothing more.
"""

from __future__ import annotations


def test_api_app_imports_and_exposes_the_slice_routes() -> None:
    from apx.api.app import app

    # Slice A adds the inventory path. (Story 1.1 shipped the empty boundary; the
    # slice legitimately wires routes onto it.) Assert the app imports and the
    # expected routes are present — an import regression or a dropped route fails.
    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/health" in paths
    assert "/api/ingest" in paths


def test_worker_app_imports_with_no_apx_tasks() -> None:
    from apx.worker.app import app

    # Procrastinate registers its own built-in maintenance tasks; 1.1 must add
    # none of its own. A task we defined would live under the apx namespace.
    ours = [name for name in app.tasks if name.startswith("apx")]
    assert ours == [], f"story 1.1 registers no worker tasks; found {ours}"
