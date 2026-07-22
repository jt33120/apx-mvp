"""Smoke test: the entrypoint boundary objects import and construct.

import-linter analyses the graph statically (grimp parses the AST; it does not
execute modules), so a broken *runtime* import in an entrypoint would ship green
with no other test importing it. This closes that gap for the two boundaries 1.1
ships — the FastAPI app and the Procrastinate worker app — and nothing more.
"""

from __future__ import annotations


def test_api_app_imports_and_has_no_routes() -> None:
    from apx.api.app import app

    # 1.1 ships the boundary only: zero routes. FastAPI mounts a couple of internal
    # routes (docs/openapi); assert no *user* route was added.
    user_paths = [
        r.path
        for r in app.routes
        if getattr(r, "path", "").startswith("/api")
    ]
    assert user_paths == [], f"story 1.1 ships no routes; found {user_paths}"


def test_worker_app_imports_with_no_apx_tasks() -> None:
    from apx.worker.app import app

    # Procrastinate registers its own built-in maintenance tasks; 1.1 must add
    # none of its own. A task we defined would live under the apx namespace.
    ours = [name for name in app.tasks if name.startswith("apx")]
    assert ours == [], f"story 1.1 registers no worker tasks; found {ours}"
