"""Worker entrypoint boundary (AD-6). Exposes the Procrastinate ``App`` — now with the real
PostgreSQL connector and the registered ingestion task (Story 2.2) — for the worker process
(``python -m apx.manage worker``). The queue itself is sealed inside
``apx.adapters.store_postgres.queue``: the only module that touches Procrastinate's connector
and job tables (AD-17). This edge just re-exports the app so the worker CLI has one import.
"""

from __future__ import annotations

from apx.adapters.store_postgres.queue import app

__all__ = ["app"]
