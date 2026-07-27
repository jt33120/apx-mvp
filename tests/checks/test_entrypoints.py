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


def test_worker_app_exposes_the_ingestion_task() -> None:
    from apx.worker.app import app

    # Story 2.2 wires the resumable ingestion task onto the worker boundary (Story 1.1 shipped
    # zero). A task we define lives under the apx namespace; the queue submodule owns it.
    ours = [name for name in app.tasks if name.startswith("apx")]
    assert ours == ["apx.run_import"], f"expected exactly the ingestion task; found {ours}"
